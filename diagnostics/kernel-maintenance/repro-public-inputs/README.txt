The public inputs in this directory describe the locally verified raw
kernel compilation profile. Two separate empty build HOME and temporary
directories produced identical vmlinux, zImage, 464 unstripped modules, 63
DTBs and 26 generated graphics headers. Every tracked source path was
verified in each build. See evidence/2026-11-14-kernel-deterministic-pair.json
and the complete native package identities in
 evidence/2026-11-14-kernel-build-toolchain.json.

Use the exact source commit and archive checksum in build-identity.json.
The source commit remains local until approved publication; do not assume
its public download URL is already available. The checked toolchain is
Alpine clang 22.1.3 / LLD 22.1.3 in the declared native build-root package set.
The existing rootless-native-build instructions describe preparation of
that environment. The host build directories and old build root remain
separate; the old root is mounted read-only.

Inside the native environment, use this fixed source directory:
/home/pmos/build/src/fx0-linux-SOURCE_COMMIT
Replace SOURCE_COMMIT with the exact commit from build-identity.json.
This internal path is part of the debug-information build profile.

Set the values from build-identity.json before running make. The timestamp
is UTC and uses the native date parser's accepted YYYY-MM-DD HH:MM:SS form.
Use a clean environment, LC_ALL=C, LANG=C, TZ=UTC, ARCH=arm, LLVM=1 and an empty
LOCALVERSION. Copy recipe.config to .config and run make olddefconfig.
Then run the ordinary kernel build with
 CONFIG_MODULE_SIG_KEY=/tmp/repro-inputs/module-signing-public.pem
where that path is a read-only copy of this public certificate. Use the
same internal path in both fresh environments. No private key is supplied.
The certificate is public; the PEM contains no private key.

This stage compiles raw modules without signing or installing them. The
normal modules_install signing stage needs a retained matching signer.
A public certificate cannot perform that operation. Standard APK builds,
repository signing, physical boot and update/recovery qualification are
separate remaining work. The accepted phone was not changed by these
host builds.

The additional standard-r2-build-identity.json describes the separately
qualified full abuild pair. It uses build version3, postmarketos host identity
and the new recipe epoch. The original raw-pair identity remains unchanged.
Signed outputs require the retained external credentials. The included public
certificate is sufficient for the separate verified raw-kernel pair and for
signature verification. Public-certificate-only compilation with this new
standard profile has not been separately compared with its signed-build
unstripped outputs.
