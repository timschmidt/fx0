# Maintained LTS full integration build

The complete integration kernel at f670355ca51442d59800b6500ba18dda33f250bb
links from a tracked-source export with all 102 changed runtime C files bound
to their ELF source checksums. It builds 455 unsigned ARM modules and 65 DTBs.
All 447 prior module paths remain. Eight additions cover NFC/NCI/NXP transport,
WCD9306/regmap and ICM42600. ABI and dependency metadata pass for all 455 staged
modules. The two cfg80211 test files retain the separately reviewed KUnit proof.

Two independent clean builds produce identical kernel, modules, DTBs, config
and build metadata. The first Python extraction normalized one PowerPC self-test
symlink without changing its target. The second preserves every one of 91,290
tracked paths exactly, including all 85 symlinks. A further complete run of this
portable public-input recipe reproduces every expected artifact and dependency
report. Modified configuration is rejected before compilation begins.

All runs use read-only source/public inputs, cleared environments and isolated
network/device namespaces. Home, boot, run, sys and workstation USB are absent.
No private signing key is read, hashed, copied, mounted or generated. The public
certificate stays registered for verification, but automatic signing is off.
The staged modules are unsigned; trusted normal APK signing/update/recovery and
installation are not qualified by this packet. No firmware or driver executes.

The full audit retains 219 compiler/documentation warnings, all identical to
earlier full-build diagnostics, and 361 DT warnings across the 65 compiled boards.
The controllers' initial diagnostic arrays recognized colon-style warnings;
the final audit also counts DTC's parenthesized warning format. No zero-warning
claim is made. Nineteen target-family DTBs exactly match earlier full-schema
qualified bytes; that schema evidence is reused, without a new schema run.
The broader warning/security/style gates and physical acceptance remain open.

To replay, export the recorded kernel commit into a new directory using Git
archive and GNU tar, preserving literal symlink text. Install LLVM 21, public
Rust 1.98.1, bubblewrap, Python, Make, OpenSSL, kmod and the standard kernel build
tools. The exact config, toolchain metadata and expected hashes are in inputs.
Run:

```
python3 -B rebuild.py --source /path/to/exported/linux \
  --inputs inputs --output /path/to/new/output \
  --rust-toolchain /path/to/1.98.1-x86_64-unknown-linux-gnu --jobs 4
```

The source and review branches remain local and unpublished. This is the full
integration compile profile, including opt-in CPU/system-sleep support. It does
not promote those variants into the normal installed image or qualify the normal
APK, hardware recovery, original r2 fault, final currency or the seven bringup
requirements. The paired quaternion reader still needs its normal-package update.
Original authorship/provenance is preserved; Codex prepared this qualification.
Human DCO, owner/security and subsystem review remain pending. No maintainer was
contacted and nothing was installed or published.
