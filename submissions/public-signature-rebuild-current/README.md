# Reproduce the experimental kernel with public signing inputs

This private review draft rebuilds the pinned experimental source at
`fc5120c4e0f2ab4790cb62f1f4c40aea74697a18` without access to the development
private key. Its inputs contain the verification certificate and already
issued detached CMS signatures. They cannot sign changed module contents.
Publication of the source and these inputs remains pending owner review.

Three fresh isolated runs reproduce the same vmlinux, zImage, System.map,
Module.symvers, 459 raw modules, 459 signed compressed modules, 14 dependency
metadata files and 66 DTBs. The generic kernel config remains byte identical,
including MODULE_SIG_ALL=y. The kernel's actual `sign-file -s` operation
attaches the issued signatures during normal `modules_install`; each CMS
signature, ELF32 ARM release and dependency set is checked. Embedded CMS
certificates are ignored in favor of the explicit verification certificate.
Certificate-chain validation is disabled for this development certificate.

Bubblewrap clears the environment and isolates the network, PID namespace
and devices. Read-only build tools/system configuration, a read-only source export and
read-only public inputs and a new writable output are exposed. Home directories, the
development private key, host USB devices, host boot files, `/run` and `/sys`
are unavailable. The network namespace contains loopback only. No phone,
Wi-Fi scan or network configuration action is performed.

## Rebuild

The tools used include Fedora clang/LLVM/LLD 21.1.8-6.fc43, Rust 1.98.1 with LLVM 22.1.8,
Python 3, make, GCC, bison, flex, Perl, OpenSSL, zstd, kmod and bubblewrap.
Rust is disabled in this kernel, but its probed version affects the saved
configuration metadata. Supply the installed public Rust toolchain directory;
the runner mounts that directory read-only without exposing its home parent.

Create a plain `git archive --format=tar` of the exact source commit, without
a prefix. Its expected SHA256 is
`b7722b0ecf00a1a00f35f474c121fcfb08663679f0d330e45261dfbce300dbac`.
The source archive is not included in this small packet. A GitHub-generated
server archive is a separate representation requiring its own checksum and
qualification; it is not substituted silently.

```sh
mkdir /path/to/source
tar --extract --no-same-owner --file /path/to/source.tar --directory /path/to/source
python3 -B verify-source-export.py --archive /path/to/source.tar --source /path/to/source --expected-archive-sha256 b7722b0ecf00a1a00f35f474c121fcfb08663679f0d330e45261dfbce300dbac --report /path/to/new-source-report.json
python3 -B rebuild.py --source /path/to/source --inputs public-inputs --output /path/to/new-run --rust-toolchain /path/to/rust-1.98.1 --jobs 4
python3 -B test-attachments.py --inputs public-inputs --build-output /path/to/new-run/out --output /path/to/new-attachment-tests
```

The literal GNU tar export passes all 97,382 source paths, including file
bytes, executable flags and symlink targets. Earlier Python 3.14 extractions
normalized one redundant `./` in a PowerPC test symlink. The strict comparison
failure is preserved. A separate whole-tree audit confirms identical regular
files and identical resolved symlink targets for those earlier exports.
The archive-exact run reproduces the same build outputs as those runs.

The ten attachment checks include actual kernel attachment and rejection of
double attachment, unissued content, changed payloads, changed signatures,
valid-format corrupted CMS, invalid paths and inconsistent expected hashes.
Rejected inputs leave the module unchanged. Compiled test fixtures are
generated locally from the completed rebuild and are not distributed here.

## Qualification scope

The first isolated attempt stopped before compilation because the system Rust
compiler differed from the pinned config metadata. Its failure and the
corrected toolchain provenance are retained. This is not hidden as a pass.

All 66 configured DTBs compile and reproduce. The unfiltered schema run uses
the complete 5,964-entry processed schema and reports diagnostics on 38 other
boards. Its global silent-validation gate failed. All 21 previously qualified
Fx0/related DTBs remain byte identical and have no diagnostics in that run.
The full log is preserved; regression/inheritance analysis for the additional
board diagnostics remains open. Shared-platform qualification is not claimed.

This packet establishes experimental host artifact reproduction using public
certificate/signature inputs. It does not qualify a maintained-LTS image,
native APK build/signing recipe, public-server source archive, installation,
kernel/userspace updates, recovery or physical hardware behavior. All seven
original bringup requirements remain in scope. The maintained-LTS backport
work is recorded in the adjacent review packet.

The new replay tools/tests carry GPL-2.0-only identifiers. The two original
Fx0 verification helpers retain the MIT license in `licenses/fx0-tools-MIT.txt`.
Kernel materials retain their own notices. No private key, boot image,
initramfs, opaque firmware or device-record body is included. Codex prepared
the new tools and review material; human review remains pending.

The portable test controller also passes an actual corrupt-signature failure
check: it records terminal failure, reaps its namespace child and never emits
a success receipt. Build-tool fingerprints and package identities are saved
in `evidence/toolchain-provenance-01.json`.
