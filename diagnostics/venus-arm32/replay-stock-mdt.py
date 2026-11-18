# SPDX-License-Identifier: GPL-2.0-only
"""Replay the maintained Venus metadata loader against a verified stock image."""

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


PREFIX = r"""
#include <assert.h>
#include <errno.h>
#include <linux/elf.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
typedef uint32_t phys_addr_t;
#define PHYS_ADDR_MAX UINT32_MAX
#define GFP_KERNEL 0
#define SZ_4K 4096U
#define ALIGN(x, a) (((x) + (a) - 1) & ~((a) - 1))
#define QCOM_MDT_TYPE_MASK (7U << 24)
#define QCOM_MDT_TYPE_HASH (2U << 24)
#define QCOM_MDT_RELOCATABLE (1U << 27)
#define ERR_PTR(x) ((void *)(intptr_t)(x))
#define PTR_ERR(x) ((intptr_t)(x))
#define IS_ERR(x) ((uintptr_t)(x) >= (uintptr_t)-4095L)
#define kmalloc(n, flags) malloc(n)
#define kfree(ptr) free(ptr)
#define dev_err(...) ((void)0)
struct firmware { size_t size; const unsigned char *data; };
struct device { int unused; };
struct qcom_scm_pas_metadata { int unused; };
static const unsigned char *original;
static size_t original_size;
static unsigned int state;
static int metadata_error, relocation_error;
static size_t size_add(size_t a, size_t b)
{
	size_t n;
	return __builtin_add_overflow(a, b, &n) ? SIZE_MAX : n;
}
static size_t size_mul(size_t a, size_t b)
{
	size_t n;
	return __builtin_mul_overflow(a, b, &n) ? SIZE_MAX : n;
}
static ssize_t mdt_load_split_segment(void *ptr, const struct elf32_phdr *phdrs,
				      unsigned int segment, const char *name,
				      struct device *dev)
{
	return -ENOENT;
}
static int qcom_scm_pas_init_image(int id, void *metadata, size_t length,
				   struct qcom_scm_pas_metadata *ctx)
{
	assert(!state && id == 9 && length == original_size);
	assert(!memcmp(original, metadata, length));
	state = 1;
	return metadata_error;
}
static int qcom_scm_pas_mem_setup(int id, phys_addr_t address, size_t length)
{
	assert(state == 1 && id == 9 && address == 0x0f500000 && length == 0x500000);
	state = 2;
	return relocation_error;
}
"""
SUFFIX = r"""
int main(void)
{
	unsigned char data[1024] __attribute__((aligned(4)));
	const char *name = "qcom/msm8226/venus.mdt";
	size_t length = fread(data, 1, sizeof(data), stdin);
	struct firmware fw = { length, data };
	struct device dev = {};
	void *metadata;

	assert(length == 412 && feof(stdin));
	assert(qcom_mdt_get_size(&fw) == 0x500000 && qcom_mdt_bins_are_split(&fw));
	metadata = qcom_mdt_read_metadata(&fw, &length, name, &dev);
	assert(!IS_ERR(metadata) && length == fw.size && !memcmp(data, metadata, length));
	free(metadata);
	original = data;
	original_size = length;
	assert(qcom_mdt_pas_init(&dev, &fw, name, 9, 0x0f500000, NULL) == 0 && state == 2);
	state = 0;
	metadata_error = -EIO;
	assert(qcom_mdt_pas_init(&dev, &fw, name, 9, 0x0f500000, NULL) == -EIO && state == 1);
	state = 0;
	metadata_error = 0;
	relocation_error = -ETIMEDOUT;
	assert(qcom_mdt_pas_init(&dev, &fw, name, 9, 0x0f500000, NULL) == -ETIMEDOUT && state == 2);
	puts("native layout, metadata copy and both SCM error checks passed");
	return 0;
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="maintained Linux source tree")
    parser.add_argument("manifest", type=Path, help="verified stock system image manifest")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    diagnostics = Path(__file__).resolve().parent
    stock = load_module(diagnostics / "inspect-stock-firmware.py")
    extractor = load_module(diagnostics / "check-aperture.py")
    source = (args.source / "drivers/soc/qcom/mdt_loader.c").read_text()
    source = re.sub(r"/\*\*.*?\*/", "", source, flags=re.S)
    names = (
        "mdt_header_valid", "mdt_phdr_loadable", "qcom_mdt_get_size",
        "qcom_mdt_read_metadata", "qcom_mdt_pas_init", "qcom_mdt_bins_are_split",
    )
    fragments = {name: extractor.function(source, name) for name in names}
    args.output.mkdir(parents=True, exist_ok=True)
    program = args.output / "load-metadata.c"
    binary = args.output / "load-metadata"
    program.write_text(PREFIX + "\n".join(fragments.values()) + SUFFIX)
    subprocess.run(
        ["clang-21", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
         "-fsanitize=undefined", "-fno-sanitize-recover=all", str(program), "-o", str(binary)],
        check=True, timeout=30,
    )
    manifest = json.loads(args.manifest.read_text())
    entry, = [entry for entry in manifest["images"] if entry["name"] == "system"]
    assert entry["file"] == "system.img" and entry["bytes"] == 1 << 30
    with args.manifest.with_name(entry["file"]).open("rb") as image:
        assert hashlib.file_digest(image, "sha256").hexdigest() == entry["sha256"]
        raw = stock.debugfs(image, "cat /etc/firmware/venus.mdt")
        assert stock.describe_mdt(raw, stock.file_sizes(image))["resident_span_bytes"] == 0x500000
        replay = subprocess.run([str(binary.resolve())], input=raw, capture_output=True,
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
        "result": replay.stdout.decode().strip(),
    }
    (args.output / "stock-mdt-model.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
