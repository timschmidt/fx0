#!/usr/bin/env python3
"""Run the MSM8226 topology, clock requests and SMD QoS code in a host fixture."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess


def section(text, start, end):
    return text[text.index(start):text.index(end, text.index(start))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    root = args.source / "drivers/interconnect/qcom"

    header = (root / "icc-rpm.h").read_text()
    backend = (root / "icc-rpm.c").read_text()
    provider = (root / "msm8226.c").read_text()
    core = (root.parent / "core.c").read_text()
    fixture = Path(__file__).with_name("interconnect-fixture.c").read_text()
    bindings = args.source / "include/dt-bindings/interconnect/qcom,msm8226.h"
    default_stride = re.search(r"^\s*qp->noc_qos_stride = (.*);$", backend, re.M)[1]
    clock_setter = re.search(r"^\s*qp->set_bus_clk_rate = (.*);$", backend, re.M)[1]
    get_bw = re.search(r"^\s*provider->get_bw = (.*);$", backend, re.M)[1]
    clock_data = (args.source / "drivers/clk/qcom/mmcc-msm8974.c").read_text()
    clock_table = section(clock_data, "static const struct freq_tbl ftbl_mmss_axi_clk_msm8226[]",
                          "static const struct freq_tbl ftbl_mmss_axi_clk[]")
    rates = re.findall(r"\bF\(\s*(\d+)\s*,", clock_table)
    assert rates and rates[-1] == "266666666"
    fragments = [
        bindings.read_text(),
        section(header, "#define RPM_BUS_MASTER_REQ", "extern const"),
        "\n".join(line for line in backend.splitlines()
                  if line.startswith(("#define NOC_QOS_", "#define M_BKE_", "#define ICC_BUS_CLK_MIN_RATE"))),
        "static const unsigned long hardware_rates[] = {" + ", ".join(rates) + "};",
        section(provider, "enum {", "static const struct of_device_id"),
        section(backend, "static int qcom_icc_bimc_set_qos_health",
                "static int qcom_icc_qos_set"),
        section(backend, "static int qcom_icc_rpm_set",
                "int qnoc_probe("),
        section(core, "void icc_node_add(", "EXPORT_SYMBOL_GPL(icc_node_add);"),
        "#define DEFAULT_STRIDE(desc) (" + default_stride + ")",
        "#define CLOCK_SETTER(desc) (" + clock_setter + ")",
        "#define INITIAL_BW(desc) (" + get_bw + ")",
    ]
    source = fixture.replace("/* EXTRACTED KERNEL SOURCE */", "\n".join(fragments))
    controls = {
        "incorrect_mmss_stride": (".noc_qos_stride = 0x80", ".noc_qos_stride = 0x1000"),
        "incorrect_bimc_offset": (".qos_offset = 0x8000", ".qos_offset = 0"),
        "incorrect_rpm_slave": (".slv_rpm_id = 0", ".slv_rpm_id = 9"),
        "missing_gateway": ("mmss_bimc_links[] = { MSM8226_MASTER_BIMC_MMSS }",
                            "mmss_bimc_links[] = { MSM8226_SLAVE_EBI_CH0 }"),
        "legacy_default_changed": ("NOC_QOS_PORT_STRIDE\t\t0x1000",
                                   "NOC_QOS_PORT_STRIDE\t\t0x80"),
        "ddr_clock_handoff_replaced": (".type = QCOM_ICC_BIMC,",
                                       ".type = QCOM_ICC_BIMC, .bus_clk_desc = &bimc_clk,"),
        "probe_applies_synthetic_maximum": ("#define INITIAL_BW(desc) (desc->get_bw)",
                                            "#define INITIAL_BW(desc) NULL"),
        "mmss_overwrites_peer_rate": (".set_bus_clk_rate = msm8226_set_mmss_rate,",
                                      ".set_bus_clk_rate = clk_set_rate,"),
        "unsatisfiable_mmss_rate_accepted": ("if ((unsigned long)actual < rate)", "if (false)"),
    }
    result = {}
    for name, mutation in {"baseline": None, **controls}.items():
        candidate = args.output / f"{name}.c"
        binary = args.output / name
        if mutation:
            assert source.count(mutation[0]) == 1, name
        candidate.write_text(source.replace(*mutation) if mutation else source)
        subprocess.run([
            os.environ.get("CC", "clang"), "-std=gnu11", "-Wall", "-Wextra",
            "-Werror", "-Wno-pointer-sign", "-Wno-unused-parameter", "-fsanitize=undefined",
            "-fno-sanitize-recover=all",
            str(candidate), "-o", str(binary),
        ], check=True)
        run = subprocess.run([str(binary)], capture_output=True, text=True)
        assert run.returncode == (1 if mutation else 0), (name, run.stderr)
        result[name] = run.stderr.strip() if mutation else run.stdout.strip()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
