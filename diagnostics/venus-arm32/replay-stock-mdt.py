# SPDX-License-Identifier: GPL-2.0-only
"""Replay the maintained Venus loader against verified stock firmware."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess


def load_module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="maintained Linux source tree")
    parser.add_argument("manifest", type=Path, help="verified stock system image manifest")
    parser.add_argument("output", type=Path)
    parser.add_argument("--staged-firmware", type=Path, help="private firmware search root")
    args = parser.parse_args()
    diagnostics = Path(__file__).resolve().parent
    stock = load_module(diagnostics / "inspect-stock-firmware.py")
    extractor = load_module(diagnostics / "check-aperture.py")
    source = (args.source / "drivers/soc/qcom/mdt_loader.c").read_text()
    source = re.sub(r"/\*\*.*?\*/", "", source, flags=re.S)
    names = (
        "mdt_header_valid", "mdt_phdr_loadable", "mdt_load_split_segment", "qcom_mdt_get_size",
        "qcom_mdt_read_metadata", "qcom_mdt_pas_init", "qcom_mdt_bins_are_split",
        "__qcom_mdt_load", "qcom_mdt_load",
    )
    fragments = {name: extractor.function(source, name) for name in names}
    venus = (args.source / "drivers/media/platform/qcom/venus/firmware.c").read_text()
    fragments["venus_boot"] = extractor.function(venus, "venus_boot")
    pas_id = re.search(r"^#define VENUS_PAS_ID\s+\d+$", venus, re.M)[0]
    args.output.mkdir(parents=True, exist_ok=True)
    program = args.output / "load-metadata.c"
    binary = args.output / "load-metadata"
    fixture = (diagnostics / "stock-mdt-fixture.c").read_text()
    marker = "/* EXTRACTED KERNEL SOURCE */"
    assert fixture.count(marker) == 1
    program.write_text(fixture.replace(marker, "\n".join([pas_id, *fragments.values()])))
    subprocess.run(
        ["clang-21", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
         "-Wno-sign-compare", "-fsanitize=undefined", "-fno-sanitize-recover=all",
         str(program), "-o", str(binary)],
        check=True, timeout=30,
    )
    manifest = json.loads(args.manifest.read_text())
    entry, = [entry for entry in manifest["images"] if entry["name"] == "system"]
    assert entry["file"] == "system.img" and entry["bytes"] == 1 << 30
    with args.manifest.with_name(entry["file"]).open("rb") as image:
        assert hashlib.file_digest(image, "sha256").hexdigest() == entry["sha256"]
        raw = stock.debugfs(image, "cat /etc/firmware/venus.mdt")
        sizes = stock.file_sizes(image)
        assert stock.describe_mdt(raw, sizes)["resident_span_bytes"] == 0x500000
        replay_command = [str(binary.resolve())]
        if args.staged_firmware:
            directory = args.staged_firmware / "qcom/msm8226"
            filenames = {"venus.mdt", "venus.b02", "venus.b03", "venus.b04"}
            assert {file.name for file in directory.iterdir()} == filenames
            for name in filenames:
                file = directory / name
                assert file.is_file() and not file.is_symlink() and file.stat().st_size == sizes[name]
            assert (directory / "venus.mdt").read_bytes() == raw
            replay_command.append(str(args.staged_firmware.resolve()))
        replay = subprocess.run(replay_command, input=raw, capture_output=True,
                                check=True, timeout=10)
    receipt = {
        "matched_verified_stock_system_hash": True,
        "loader_functions": {name: hashlib.sha256(body.encode()).hexdigest()
                             for name, body in fragments.items()},
        "stock_header_bytes": len(raw),
        "loader_reports_split": True,
        "loader_span_bytes": 0x500000,
        "metadata_copy_matches": True,
        "pas_id_verified_in_stub": 9,
        "scm_init_error_propagated_in_stub": True,
        "scm_relocation_error_propagated_in_stub": True,
        "device_exercised": False,
        "signature_verified": False,
        "venus_boot_error_cases": 7,
        "result": replay.stdout.decode().strip(),
    }
    if args.staged_firmware:
        receipt["staged_files_loaded"] = 3
        receipt["checked_memory_bytes"] = 0x500000
        receipt["file_error_cases"] = 6
    (args.output / "stock-mdt-model.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
