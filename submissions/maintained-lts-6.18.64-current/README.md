# Maintained Linux 6.18.64 integration and reader preparation

The official 6.18 LTS release is 6.18.64 as checked on 2026-11-17. Its signed
tag 084d543c1adb9b29550aae1cce61378982f94d1d points to
fd7cfd39c88596fec816639ad83cbf3e9d316372. Verification uses Greg Kroah-Hartman's
documented fingerprint 647F28654894E3BD457199BE38DBBDC86092693E; a modified
tag body is rejected. The source was fetched directly from kernel.org.

Merge c3e72d14babc2e875b89cadde5ed57bb54b11a0b retains all 695 stable commits
and the exact 162-path custom source delta, path by path, without conflicts or
manual resolutions. Only MAINTAINERS and BAM DMA overlap custom paths. The BAM
callback synchronization is retained alongside upstream explicit IRQ ownership
and firmware-described trigger handling. Original authors, dates and genuine
upstream trailers remain in history; no human sign-off is invented.

The integration kernel links with 455 unsigned modules and 65 DTBs. Its portable
public-input rebuild reproduces all kernel artifacts, modules and DTBs exactly.
All 455 module ABIs/dependency metadata pass; ELF checks bind 102 changed runtime
C files. Another 108 ARM/ARM64/ARM64 RT object checks pass without diagnostics.
The two cfg80211 test files retain their separate KUnit evidence. Nineteen DTBs
match earlier full-schema-qualified bytes exactly; schema evidence is reused.

The reader defaults to the corrected timestamp at byte 16, with an explicit
--legacy-r1-timestamp option for byte 24. Both retain 32-byte scans. Seven host
tests and eighteen synthetic decode records pass; two wrong-slot controls each
fail nine records. Capture delegates to the decoder, and restoration is unchanged.
No capture, main device enumeration or firmware/device operation was executed.
The reader has not been deployed or packaged onto the phone. From the full
review repository, its portable checker can be replayed with
`python3 qualification-tools/check-reader.py --repo /path/to/repo --output /new/output`
when called from this packet directory.

Retain 219 compiler/documentation warning lines and 361 DT warning lines.
The compiler/documentation lines exactly match the prior 6.18.63 build. The
broader warning/security/style gates, normal signed APK/update/recovery, final
currency and hardware acceptance remain open. The tested 6.18.63 integration
at f670355ca51442d59800b6500ba18dda33f250bb remains frozen as a fallback.

Export this kernel commit with Git archive and GNU tar, preserving literal
symlinks. With LLVM 21, public Rust 1.98.1, bubblewrap and standard kernel build
tools installed, run:

```
python3 -B rebuild.py --source /path/to/exported/linux \
  --inputs inputs --output /path/to/new/output \
  --rust-toolchain /path/to/1.98.1-x86_64-unknown-linux-gnu --jobs 4
```

The recipe verifies the complete 91,291-path source manifest before building.
Its namespace has no workstation network, home, boot, run, sys or USB. Only a
public certificate is supplied; private signing keys are never accessed or
generated, and modules remain unsigned. No phone or network setting changes,
publication or maintainer contact occurred. Source and review publication need
separate approval before the normal package can fetch the new public source URL.
All seven bringup requirements remain open. Codex prepared this merge and
qualification; human DCO, owner/security and subsystem review remain pending.
