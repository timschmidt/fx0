# Reproducible QMI string generation

The RMTFS OPEN buffer correction now has a matching generator patch. The pinned
generator, direct schema generation and RMTFS's actual Makefile regeneration
rule produce the same corrected header. Sixteen normal wire-byte/round-trip
cases pass on host Clang ASan/UBSan/leak detection and static ARM/QEMU.
No daemon or phone operation is performed.

The generator is [linux-msm/qmic 4574736](https://github.com/linux-msm/qmic/tree/4574736afce75aa5eec1e1069a19563410167c9f).
All 28 retained source/test/license files match upstream Git blob hashes and
sizes. Explicit base64 file retrieval preserves exact bytes. The initial blob
fetch returned normalized text rather than Git JSON; those bytes were not used.
The source has seven existing compiler warnings, retained in both build logs.

The [generator patch](qmic-string-fields.patch) changes only `kernel.c`.
Kernel-style output (`qmic -k`) allocates 257 bytes for a string whose descriptor
permits 256 wire bytes, in both messages and nested structures. It also emits
the validity field and OPT_FLAG descriptor for an optional string, matching the
schema's optional status. Required string descriptors keep their wire maximum.
The accessor generator is unchanged. Preserve the [upstream BSD license](qmic-LICENSE).

Regenerating the actual RMTFS schema produces a `qmi_rmtfs.c` byte-for-byte
identical to the retained upstream file. Its header keeps the 257-byte OPEN
path and emits two count fields as `uint32_t`, as the pinned current generator
already does. The older checked-in RMTFS header used `size_t` for those fields.
All consumers must be rebuilt together. Normal IOVEC requests and FORCE_SYNC
indications verify both count fields against independently constructed wire
bytes on 32- and 64-bit hosts.

The [ordinary schema fixture](../../tests/fixtures/qmic-strings.qmi) includes
required/optional message strings, a nested string followed by a scalar,
an array of string-bearing structures and a response string. The
[harness](../../tests/qmic-strings-harness.c) statically checks capacities,
compares the entire encoded message with independent bytes, then decodes and
checks fields, counts, optional markers and NUL termination. It covers top-level
lengths 0/1/255/256, nested lengths 0/1/255, optional presence/absence, RMTFS OPEN,
IOVEC and FORCE_SYNC. Repeated generation is deterministic; host and ARM runs
use identical generated source bytes. The generator itself runs on the host;
the generated C is compiled and executed on both architectures.

```sh
# Prepare a private checkout at the pinned qmic commit.
patch --batch --fuzz=0 -p1 -d /private/qmic-candidate \
  -i "$PWD/diagnostics/modem-control/qmic-string-fields.patch"
make -C /private/qmic-candidate
python3 diagnostics/modem-control/check-qmic-strings.py \
  --qmic /private/qmic-candidate/qmic \
  --rmtfs-schema /private/rmtfs/qmi_rmtfs.qmi \
  --string-schema tests/fixtures/qmic-strings.qmi \
  --qrtr /private/qrtr-with-qmi-fixes \
  --harness tests/qmic-strings-harness.c \
  --cflags-json '["-O1","-g","-fsanitize=address,undefined","-fno-omit-frame-pointer","-no-pie"]' \
  --output local/qmic-strings-replay
```

Use a fresh output path and the [previously corrected QRTR codec](rmtfs-qmi.md).
The checker accepts JSON argv prefixes for an isolated generator, cross compiler
and emulator. Recorded runs isolate networking, expose synthetic /dev, mount
public compiler/sysroot directories read-only and write only a fresh workspace.
The actual RMTFS check uses its original `make -B qmi_rmtfs.c` recipe with the
patched generator on PATH; exact no-fuzz patch replay also passes.

Initial fixture names used reserved grammar keywords and were corrected; both
rejected fixture versions and diagnostics are retained. An initial Makefile
sandbox omitted /bin/sh; its terminal failure is retained and a fresh run with
read-only /bin succeeds. No failed run is counted as qualification.

This closes the pinned RMTFS source regeneration check, not distribution package
integration or full daemon qualification. Legacy nested-string encoding still
uses a one-byte prefix when the declared maximum is 256, so a 256-byte nested
string is not represented correctly. Nested coverage stops at 255; RMTFS's only
string is its top-level OPEN path. General generator/codec compatibility, clean
libudev provenance, rebuilt full-daemon validation, shared-memory spans and
lifecycle/physical operation remain open. The newest phone UI gate remains
pending. See [evidence](../../evidence/2026-11-09-qmic-generation.json) and the
[unsent draft](../../submissions/qmic/README.md).
