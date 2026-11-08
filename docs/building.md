# Building Fx0 diagnostic images

Current installed phone: restored **6.18.59-r50**, with working display/touch,
taint zero and the original four CPU rates. The source reconstruction below
uses its running configuration and the pinned pre-DMP integration commit.
The CPU/CPR profile remains unqualified and uninstalled.

## Reconstruct r50 and the CPU/CPR source candidate

[`manifests/kernel-integration.json`](../manifests/kernel-integration.json)
pins the base commit, configuration hash and ordered patch hashes. The `r50`
profile applies ten patches; `cpr` applies the same DMP/display series plus all
27 CPU patches, 32 patches total. Both start at
`4b800b920c7db82e8012a580a17cc2d8ff9d5e66`. Do not use the older temporary
CPU validation checkout as the complete image source: that base lacks the
standalone power-collapse state and includes later experiments.

Use a fresh checkout for each profile. For example, after obtaining the
public development repository or cloning an existing local object store:

```sh
git -C worktrees/linux-fx0-integration checkout --detach 4b800b920c7db82e8012a580a17cc2d8ff9d5e66
python3 scripts/prepare_kernel_integration.py \
  --source worktrees/linux-fx0-integration --profile r50 \
  --report local/kernel-reconstruction/r50-prepared.json
```

The preparer refuses a different base, dirty/untracked files, changed inputs
or an existing report. It checks all hashes and simulates the entire series
in workspace scratch before applying it. A patch conflict is detected before
any source edit. Filesystem write failures can still leave a partial tree for
inspection; the tool never resets or deletes the caller's checkout.
The receipt records every resulting changed-file hash. It performs no build,
packaging or device operation.

The reference configuration is a byte-exact copy of running r50's
`/proc/config.gz` output, with Clang CFI retained. Compiler/Rust probe metadata
can change under `olddefconfig`; review the diff. The current host uses Clang
21.1.8 from Fedora build 6 rather than build 4; LLD 18.1.8 is explicitly selected.
The rebuilt r50 DTB matches the installed build record's SHA-256
`1658cb8cee4e8800c6163f76b5153f2a50eeae8bfbfcfbe2dd818ff3d3a87eda`.
This does not establish an identical kernel binary: timestamps, tool revisions,
paths and a newly generated private module-signing key affect that artifact.

```sh
mkdir -p build/fx0-r50-reconstruction local/kernel-reconstruction/tmp
cp configs/linux-6.18.59-fx0-r50.armv7 build/fx0-r50-reconstruction/.config
export TMPDIR="$PWD/local/kernel-reconstruction/tmp"
export CCACHE_DISABLE=1
make -C worktrees/linux-fx0-integration O="$PWD/build/fx0-r50-reconstruction" \
  ARCH=arm LLVM=1 CC=/usr/bin/clang LD=/usr/bin/ld.lld-18 \
  HOSTCC=/usr/bin/gcc HOSTLD=/usr/bin/ld LOCALVERSION= olddefconfig
make -C worktrees/linux-fx0-integration O="$PWD/build/fx0-r50-reconstruction" \
  ARCH=arm LLVM=1 CC=/usr/bin/clang LD=/usr/bin/ld.lld-18 \
  HOSTCC=/usr/bin/gcc HOSTLD=/usr/bin/ld LOCALVERSION= \
  KBUILD_BUILD_USER=fx0 KBUILD_BUILD_HOST=reconstruction \
  KBUILD_BUILD_TIMESTAMP='2026-11-08 12:00:00 UTC' \
  KBUILD_BUILD_VERSION=51-postmarketos-qcom-msm8226 \
  -j4 zImage modules qcom/qcom-msm8926-lg-madai.dtb
```

Workspace `TMPDIR` avoids the host's separate `/tmp` quota. Keep the generated
module-signing key private and retain it for incremental rebuilds. Verify the
complete linked kernel, modules and signatures before constructing an image;
object compilation alone is insufficient.

For the separate `worktrees/linux-fx0-cpr` checkout, run the preparer with
`--profile cpr` and a distinct report. Use a separate build directory and merge
[`configs/msm8926-cpr-qualification.fragment`](../configs/msm8926-cpr-qualification.fragment):

```sh
mkdir -p build/fx0-cpr-reconstruction
worktrees/linux-fx0-cpr/scripts/kconfig/merge_config.sh -m \
  -O build/fx0-cpr-reconstruction \
  configs/linux-6.18.59-fx0-r50.armv7 configs/msm8926-cpr-qualification.fragment
```

Then use the same explicit compiler/linker settings for `olddefconfig` and
builds. This enables built-in CPR/CPUfreq with the separate
`6.18.59-fx0-cpr-qual` module release. The qualification DTB is
`qcom/qcom-msm8926-lg-madai-cpr.dtb`; select it explicitly for that trial.
The ordinary board DTB retains four CPU rates. The candidate still contains
the unqualified L2/S2 controller integration, so first trials remain RAM-only
with verified r50 recovery. No physical CPU/CPR pass follows from preparation
or compilation. Preserve the inherited peripheral implementation; audio tests
remain excluded.

The source tests can now select the complete checkout explicitly:
`FX0_KERNEL_SOURCE="$PWD/worktrees/linux-fx0-cpr"`. Binding tests additionally use
`FX0_CPU_BUILD` and `FX0_DT_SCHEMA_CACHE`. The reconstruction run passes 109
CPU, rail, transport, binding, DMP and preparation checks with no skips, plus
three diagnostic-image placement checks. Both complete kernel/module builds
pass; each produces 464 modules. Module staging strips, signs and compresses
these files. The verifier checks every signature against the certificate
embedded in its kernel, checks release/ARM architecture and rejects modified
payload/signature controls. A module signed for the other build is rejected.

For example, after staging r50 modules with `INSTALL_MOD_PATH` set to a new
private workspace directory:

```sh
python3 scripts/verify_kernel_modules.py \
  --modules local/kernel-reconstruction/r50-stage/lib/modules/6.18.59-fx0-dmp \
  --release 6.18.59-fx0-dmp \
  --certificate build/fx0-r50-reconstruction/certs/signing_key.x509 \
  --expected-count 464 --report local/kernel-reconstruction/r50-module-verification.json
```

The r50-source RAM baseline passes two physical boots and returns to installed
r50 each time. The second captures the 180-second return message, continuous
USB serial logs and 22 HTTP status/dmesg pairs. Both keep four CPUs online,
taint zero, only pseudo-filesystems mounted and the original boot-partition
hash. No package or boot payload changed. Its moduleless initramfs does not
load `CONFIG_CPUFREQ_DT=m`, so no CPUfreq policy is expected there. CCF reports
an inherited 800 MHz clock; the CPR candidate requires a safe handoff before
attachment and has not been booted. See [RAM evidence](../evidence/2026-11-08-r50-ram-baseline.json)
and the earlier [host rebuild evidence](../evidence/2026-11-08-kernel-reconstruction.json).

For another attended RAM baseline, first verify the intended device is in
lk2nd fastboot and identify its physical USB port and serial. Start the USB
address helper in another terminal before booting:

```sh
python3 scripts/connect_fx0_ram_usb.py --usb-port 1-14 \
  --report local/ram-next/USB-network.json
python3 scripts/boot_fx0_ram.py --serial '<device serial>' \
  --image local/kernel-reconstruction/fx0-r50-reconstructed-ram.img \
  --sha256 349ab28ce8d8c48a9699d67e9b84ed53e9038baeac896f3a8fd923c96b1d853b \
  --output local/ram-next/transfer
```

Use the actual physical port rather than copying `1-14` blindly. The helper
matches that port, diagnostic VID/PID, gadget serial and host MAC; it creates
an in-memory, non-autoconnect NetworkManager connection at `172.16.42.2/24`
without gateway/DNS, then deletes its own UUID on detach. The RAM gadget has
no DHCP server. Default-route/resolver before/after snapshots are private.

The boot tool validates the image, probes lk2nd identity, stages it, reads it
back byte for byte and sends one standard `boot` command. Keep its logs and
the USB serial/HTTP observer running through return and verify the native
boot identity/hash afterward. The equivalent stage/readback/boot procedure
was used twice; the consolidated wrapper has eight host tests but has not
itself run on hardware. Transfers exhibited roughly 30-second USB pauses:
an earlier 40-second host timeout interrupted a download, requiring a
phone-only USB reset before retry. Do not kill an active transfer or send
another boot solely because an observation deadline expires. Diagnose the
current device state first. Do not retrieve `oem log` between image readback
and `boot`: lk2nd uses the same staging buffer for that log.

### Startup-clock source draft

[`manifests/kernel-startup.json`](../manifests/kernel-startup.json) preserves
the 32-patch checkpoint and adds separate binding, driver and DT patches for
the inherited-clock handoff. Prepare a fresh checkout with `--profile cpr
--manifest manifests/kernel-startup.json` and a new receipt path. The current
isolated source is `worktrees/linux-fx0-startup`; its build directory is
`build/fx0-cpr-startup`, with local version `-fx0-cpr-startup`.

The helper retains the programmed boot APC target, establishes the MX floor,
takes one logical APC enable reference and requests 300 MHz. It then checks
the APCS command/configuration registers twice for a settled source-4/HID-3
mux, together with the expected 600 MHz auxiliary clock and 300 MHz CCF rate.
Errors retain the acquired floor/references and leave attachment incomplete.

The ARM W=1 CPR object, ordinary/qualification DTBs, schema document and 16
targeted host tests pass. The complete 35-patch series reproduces all 41 changed
files; the ordinary DTB matches the earlier CPU candidate. This draft has no
complete kernel/module link or RAM boot. Before building a deployment candidate,
finish runtime clock-error guards so a failed frequency reduction cannot cause
an unsafe APC reduction. Run the startup-specific tests with dtschema:

```sh
TMPDIR="$PWD/local/kernel-reconstruction/tmp" \
  /tmp/fx0-storage/dtschema-venv/bin/python -m unittest discover \
  -s tests -p 'test_cpr_startup*.py' -v
```

See [startup evidence](../evidence/2026-11-08-msm8926-startup-clock-candidate.json).

### Runtime CPU-clock source candidate

[`manifests/kernel-runtime.json`](../manifests/kernel-runtime.json) adds four
patches to the startup draft, 39 total. Prepare a fresh checkout with
`--profile cpr --manifest manifests/kernel-runtime.json`. The current source
is `worktrees/linux-fx0-runtime`; use separate output `build/fx0-cpr-runtime`
and local version `-fx0-cpr-runtime`. All 48 changed files reproduce exactly.
The earlier complete r50, 32-patch and 35-patch checkpoints remain available.

Before every MSM8926 APC change, CPR refreshes GPLL0 and the CPU PLL, then
reads the CPU mux without its rate cache. It refuses an unknown clock or a
rate above the requested corner. The qualification DTB explicitly supplies
both parents as well as the CPU/reference clocks. MSM8226 provider probes
enable uncached PLL/mux reads and stop execution on CPU clock programming
errors. This stop is intentional: CCF can discard callback errors, allowing
a failed PLL or mux transition to continue. Successful CPU PLL and mux
programming also requires register readback before reparenting can proceed.
Other SoCs retain their ordinary error-return policy.

The six affected ARM objects and both DTBs compile with W=1. All 114 selected
source/DMP/calibration/rail/binding/preparation checks pass with no skips.
Four earlier fixtures are replaced by current runtime fixtures,
including the actual supplier, provider probes and attach callback. Five
unsafe source mutations compile but fail the executing tests. The modeled
clock tests cover 129 I/O/unstable-state cases, plus timeouts, lost writes,
stale PLL/topology, ARM32 rate overflow and startup integration.

The full kernel/module build passes. All 464 stripped, signed and compressed
ARM modules verify against the exact certificate embedded in the linked kernel;
modified contents/signatures and the other build's certificate are rejected.
The PLL object uses ARM's provided `__do_div64` rather than an unavailable
compiler division helper. The linked kernel introduces no undefined symbols
relative to the twice-booted r50 reconstruction. No RAM controller result or
analog rail/frequency measurement is implied. The first
controller RAM bootstrap should load no modules: CPUFREQ_DT remains a module,
so no governor can request higher OPPs during that initial trial. Loading it
later requires a separately controlled governor/limit setup and observation.
The first checked image is `local/cpu-runtime/fx0-runtime-l2-s2-ram.img`, using
the ordinary DTB with CPR absent and a 180-second return timer. Its SHA-256 is
`5c732301ff18ea6ed43deff7ea10d18fef3dfe558575dc19f803092a2d80352e`.
Image payload/header, gzip/newc, GNU cpio listing and init syntax pass. That
default-compressed image remains unbooted because its USB download stalls.
A read-only r50 preflight confirms the original boot hash/limits,
taint zero, running systemd startup and Sway. Two read-only clock snapshots
confirm the APCS command/status layout and CPU PLL mode/lock bit under r50.
See [runtime evidence](../evidence/2026-11-08-msm8926-runtime-clock-candidate.json).

The first L2/S2 RAM trial now passes using the same kernel, DTB, command line
and uncompressed initramfs with gzip level 1. Generate this encoding by adding
`--gzip-level 1` to `make_diagnostic_image.py`; default level 9 is unchanged.
The exact booted image is 6,275,072 bytes with SHA-256
`2b1fcff1dd28f1f2b14b4b5b3f466d1dae2678ff4fc2acd333c8d85a0fc3f74f`.
Both encodings reproduce byte for byte with the updated CLI; the earlier
builder source is archived privately and its hash retained in the build record.

The RAM kernel runs four CPUs with taint zero, binds L2 SPM and exposes the
always-on APC provider at a reported 1.15 V target. It mounts only pseudo
filesystems and loads no modules. Twenty-two HTTP status/log pairs and serial
logs capture the timed return at 181.611751 kernel seconds. Fresh installed
r50 returns with the original boot hash/limits, Sway and sensor proxy. A later
check of the same boot reaches running systemd startup with no failed services
or pending jobs. Physical display/touch confirmation for this new return is
pending. No CPR feedback, DVFS or analog voltage/frequency pass is implied.

The separate moduleless CPR-bootstrap image uses the qualification DTB and the exact
compressed initramfs and command line from the successful L2 trial. Its built-in
calibration driver attaches the CPU domains before registering the unloaded
`cpufreq-dt` device; the intended test holds APC's boot target, establishes the
MX floor and normalizes the inherited clock to 300 MHz. Feedback remains gated
on a later positive performance-state request. See
[preparation evidence](../evidence/2026-11-08-cpr-bootstrap-preparation.json).

Its first RAM trial now reaches diagnostics but the provider probe returns
`-EINVAL` under the broad calibration message. CPU remains at the inherited
800 MHz, APC reports its 1.15 V programmed target, no CPUfreq policy is present,
and the 300 MHz/MX/domain startup gate fails. Twenty-two HTTP status/log pairs
and serial capture the 181.623794-second return. Installed r50 returns with
running systemd, original hash/four rates and owner-confirmed display/touch;
host routes/DNS and the temporary network profile are restored. See
[first CPR trial](../evidence/2026-11-08-cpr-bootstrap-first-ram.json).

The isolated 40-patch diagnostic candidate adds failure-stage messages while
retaining errno, cleanup, output publication and clock/voltage guards. Its
116 selected checks, warning-free ARM CPR object, checkpatch and independent
tree replay pass. Its separate `-fx0-cpr-probe` built-in RAM kernel and both DTBs
link successfully. One observed RAM boot identifies the reference-source check
as the failing stage. A read-only native word at APCS+0x64 is 1; the stock driver
defines bit0=1 as AHB and explicitly selects bit0=0 for 19.2 MHz XO. The next
integration work is controlled XO selection with CPR stopped and verified
readback, retaining all failure guards. See
[diagnostic preparation](../evidence/2026-11-08-cpr-probe-diagnostics-preparation.json).

The serial collector's first open races udev permissions and fails before any
snapshot command. HTTP captures 22 status/log pairs, and systemd's archived
pstore recovers the diagnostic kernel identity, reference-check failure and
181.601496-second timer message. The newest r50 return retains the original
hash/rates, running systemd, Sway and sensor proxy; the owner confirms its
display/touch too. Host network state is restored. Uncaptured RAM taint, clock
and regulator snapshots are not copied from the previous trial. See
[reference diagnosis](../evidence/2026-11-08-cpr-reference-first-diagnostic.json).

The next observer template retries only an initial `PermissionError`, for at
most ten seconds, while rechecking the same physical RAM device on every
attempt. It does not retry a serial command or change device permissions.
Three host controls cover settled permissions, timeout and device replacement;
its next hardware use remains untested. The two recorded trial collectors are
preserved unchanged.

The distribution source recipe can now be exported independently of the host
build directory. Use the checked runtime configuration and shared-SoC template
in `configs/`, the runtime manifest and the pinned public base archive:

```sh
python3 scripts/prepare_kernel_package.py \
  --manifest manifests/kernel-runtime.json --profile cpr \
  --config configs/linux-6.18.59-fx0-cpr-runtime.armv7 \
  --template configs/linux-postmarketos-qcom-msm8226.APKBUILD.in \
  --archive /path/to/fx0-linux-4b800b920c7db82e8012a580a17cc2d8ff9d5e66.tar.gz \
  --archive-sha512 3479e7b9d3e753f4dddde1b88cb6544d2304e46aa92b3ba0aab8cd0ce1108869efd8cc36692a05bc094ccdff6213e0cae0433dc5b742289c57023a838fda8741 \
  --output local/package-export/cpr-runtime --pkgrel 54
```

The exporter verifies the archive and every patch, preserves manifest order,
generates all source checksums and refuses an existing destination. Its recipe
runs `olddefconfig` explicitly before compilation and retains the isolated
`6.18.59-fx0-cpr-runtime` module release. Place the exported files in the kernel
port of an isolated complete pmaports clone; validate with the official
`pmbootstrap kconfig check` and source-build command. The rootless
[build fixture](../diagnostics/rootless-native-build/README.md) also applies;
this run keeps its writable storage inside the workspace and mounts the cached
base archive read-only. The normalized r54 recipe now passes a full source
build with Alpine Clang 22.1.3; all 48 prepared files match the frozen host
candidate. The actual normalized configuration passes the community check.
The signed 18,475,505-byte APK, embedded recipe commit, exact kernel and both
DTBs, kernel trust list and all 464 module signatures verify. Corrupt module
payload/signature, wrong-build certificate and changed signed package metadata
are rejected. Offline APK simulation passes in a fresh usermode workspace
database; this does not test an installed-phone upgrade. Keep host and Alpine
modules with their respective build's
certificate and compiler; an identical release string does not establish that
they can be mixed. The existing RAM result applies to the host-built image;
the Alpine kernel requires its own RAM qualification. No candidate package is installed. See
[source-package evidence](../evidence/2026-11-08-runtime-kernel-source-package.json).

For retained-output audits, explicitly set `CLEANUP=""` and `ERROR_CLEANUP=""`
in the private buildroot's `abuild.conf`. Alpine's active defaults now live in
`default.conf`, while pmbootstrap's substitution only changes uncommented
assignments in `abuild.conf`; the initial r53 build consequently removed its
source tree after producing a valid signed APK. The corrected r54 fixture
preserves `vmlinux` and its certificate for the exact trust-list audit. Both
builds completed successfully; r54 reuses dependency/compiler caches after
r53's source cleanup, and its explicit `olddefconfig` removes the earlier EOF
messages. Local recipe commits `e59da87d99afc76fe177d44752913831f013dcbe` and
`4f17b6905c75da8a35f220b1f80724d2d07e997b` are reviewable through the
[package diff](../patches/pmaports/fx0-cpu-runtime-packaging.diff) and the
published [GitHub branch](https://github.com/timschmidt/fx0-pmaports/tree/integration/fx0-cpu-runtime-package).
The owner authorized GitHub pushes for all fx0 development; the published ref
was independently verified at `4f17b6905c75da8a35f220b1f80724d2d07e997b`.

The later [42-patch source manifest](../manifests/kernel-cpr-disabled-reference.json)
adds probe diagnostics and the verified stopped-controller XO handoff; seed
[its separate configuration](../configs/linux-6.18.59-fx0-cpr-disabled.armv7)
after preparation. This host-built moduleless kernel passes the CPR startup
RAM gate at 300 MHz with feedback disabled. It does not update the published
r54 Alpine package, whose 39-patch kernel remains independently unqualified.
Keep the source/build/certificate/module families distinct. See
[startup evidence](../evidence/2026-11-08-cpr-disabled-reference.json).

The input-dependent preboot USB defect remains open. The original image stalls
after 5,783,552 confirmed bytes with both standard fastboot and synchronous
transfers. Padding and pacing do not fix it; an isolated 32 KiB block reproduces
the stall at a different staging address, while 6 MiB of known data succeeds.
`scripts/transfer_fx0_ram.py` provides bounded 16 KiB synchronous chunks,
progress, exact readback and optional pacing, and stops before boot. The trial
used it followed by one existing raw boot query under active observation.
Changing gzip encoding is a verified workaround for this image, not a transport
fix. Ten transport host checks pass; the combined boot/network/transfer suite
passes 21 checks. A live syscall trace interrupted an earlier blocked write;
do not attach such tracing to an active transfer. Every failed attempt here
stopped before boot, and only the identified phone's USB transport was reset.
See [native bootstrap/transport evidence](../evidence/2026-11-08-l2-s2-ram-bootstrap.json).

## Earlier diagnostic build records

Historical r7 checkpoint: signed native **6.18.59-r7**, Linux source
`4598182e1708f22a7e58c45e4479d15dc80b5f68` (`integration/fx0-gpu`: r6 plus the
ADSP enable and MSM8226 GPU IOMMU), pmaports recipe
`68600046ae970267fbf800c2fbb333de302ba683`, which adds devfreq to the
configuration. Rollback checkpoint, trusted dry run, supervised install, exact
readbacks and installed boot pass, with taint 0, the ADSP running and Freedreno
FD305 with devfreq; see
[r7 evidence](../evidence/2026-10-30-native-r7-gpu-adsp.json). Earlier records
keep their scope. Factory restoration, final layout and remaining hardware
qualification are still open.

These images are development diagnostics. UART/USB are the only board functions described initially. A successful build does not establish physical boot or Nura hardware acceptance.

## Maintained Linux

Use the current exact source commit in `manifests/sources.json` and `evidence/2026-10-29-current-kernel-build.json` from the [development fork](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-lts). The recorded initial build used Fedora Clang 21.1.8 and GNU make, plus the usual Linux host dependencies. The current `simplefb` diagnostic configuration was derived from Nura's shared MSM8226 configuration, updated with Linux 6.18.59 `olddefconfig`, and enabled built-in configfs NCM/ACM USB diagnostics.

```sh
mkdir -p /tmp/fx0-storage/build/linux-6.18.59
cp configs/linux-6.18.59-fx0-diagnostic-simplefb.armv7 /tmp/fx0-storage/build/linux-6.18.59/.config
make -C src/linux-stable O=/tmp/fx0-storage/build/linux-6.18.59 ARCH=arm LLVM=1 olddefconfig
make -C src/linux-stable O=/tmp/fx0-storage/build/linux-6.18.59 ARCH=arm LLVM=1 -j8 zImage dtbs modules
```

The original build output lived at `/tmp/fx0-linux-lts`, then moved to Disk B after completion, retaining that old path as a symlink. Build timestamps and embedded host identity affect byte reproducibility; retain the exact artifacts/hashes used for each physical test rather than claiming independently identical binaries. No kernel module signing keys are published.

## lk2nd

Check out the pinned lk2nd base and apply `patches/lk2nd/0001-select-fx0-linux-device-tree.patch`, or use the public integration commit in the manifest. Build the secondary variant, leaving the stock primary bootloader intact:

```sh
make -C src/lk2nd \
  BOOTLOADER_OUT=/tmp/fx0-storage/build/lk2nd \
  APPSBOOTHEADER_DIR=/tmp/fx0-storage/build/lk2nd/build-lk2nd-msm8226 \
  TOOLCHAIN_PREFIX=arm-none-eabi- \
  LK2ND_DTBS=msm8926-lg-madai.dtb \
  LK2ND_VERSION=fx0-fd380ac6 \
  LK2ND_FORCE_FASTBOOT=1 lk2nd-msm8226 -j8
```

Use the DTB **basename**. Including the `msm8226/` directory in `LK2ND_DTBS` silently filters out the board and can still produce an unusable image. Verify that `qcdt.img` contains one entry and that its embedded `/lk2nd` compatible is `lg,madai`. The explicit `APPSBOOTHEADER_DIR` avoids a legacy relative-output assumption when the build output is absolute. Forced fastboot was used for initial diagnostics. A separate build with `LK2ND_FORCE_FASTBOOT=0` was installed and automatic Nura warm boot verified. Native display investigation temporarily reinstalls the verified forced-fastboot prefix so failures return to the menu. Full cold/key recovery qualification remains pending.

## Nura rootfs

The initial rootfs uses the verified live `v26.06` pmaports branch and pmbootstrap 3.12.1. Configure vendor `qcom`, device `msm8226`, console UI, developer USB profile, and a private development SSH key. Persistent work path is `/tmp/fx0-storage/pmbootstrap`. Initial installation creates a rootfs without writing any device: `pmbootstrap install --no-image --add busybox-static`. Authentication secrets/config stay under ignored `local/`.

The stable generic package currently supplies Linux 6.16.12. Creating that rootfs does not meet the maintained-kernel endpoint: deploy and package the maintained Fx0 kernel, correct DTBs and modules before qualifying an installed Nura system. The full graphical interface follows display/touch enablement.

## RAM diagnostic image

The image builder validates the ARM zImage, FDT and static ARM ELF inputs, then constructs a deterministic gzip/newc initramfs and legacy Android v0 header using the verified Fx0 load addresses. It performs no device writes:

```sh
python3 scripts/make_diagnostic_image.py \
  --kernel /tmp/fx0-linux-lts/arch/arm/boot/zImage \
  --dtb /tmp/fx0-linux-lts/arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai.dtb \
  --busybox /tmp/fx0-storage/artifacts/busybox-static-armv7 \
  --simplefb \
  --output /tmp/fx0-storage/artifacts/fx0-linux-diagnostic.img
```

Use `--simplefb` only with built-in simpledrm. It requests lk2nd's inherited framebuffer console; this is an early diagnostic, not native DRM/panel qualification. Initial diagnostics provide an unauthenticated root shell on USB ACM and HTTP status/logs at `172.16.42.1` on the isolated USB NCM link. Keep these images for attended physical development; normal Nura uses the separately configured SSH key and login policy. No eMMC filesystem is mounted by the diagnostic initramfs.

The initial image was independently unpacked with host `cpio`, checked for Android header alignment, and its init script checked with `sh -n`. Each boot record must identify the exact generated image hash; subsequent source builds overwrite the shared kernel output.

For automatic persistent-log capture, build `INPUT_PM8941_PWRKEY=y` into the standalone kernel (the shared configuration normally makes it a module). Apply `configs/diagnostic-warmreset.fragment` with the kernel configuration tools and rebuild. `--return-after 90 --usb-debug` generates a diagnostic init that requests a warm reboot after 90 seconds, with verbose USB probe logging and `reboot=w`. The intended next step is lk2nd `oem ramoops console` followed by `get_staged`; successful RAM retention must be verified on this boot chain. Warm reboot and complete console/raw ramoops retrieval are now physically verified.

The initial rootfs contains 399 packages on Alpine 3.24.3, including systemd 261. The stable OS branding files still say postmarketOS v26.06. Its exact package/repository manifest is recorded in `evidence/2026-10-29-nura-rootfs-packages.json`. This is an isolated chroot artifact, not an on-device installation claim.

The Linux source and output now live together at `/tmp/fx0-storage/src/linux-stable` and its `.output` directory, with `src/linux-stable` and the original output aliases retained as symlinks. This layout supports pmbootstrap `build --envkernel` packaging. The source move caused one full rebuild because recorded compiler paths changed; keep the canonical layout stable for subsequent incremental work.

For current physical images, use the pinned integration branch. The original `patches/linux-stable` source-subset candidate is a historical DTB check and lacks the SMEM, VBUS, storage and firmware-hole fixes. Apply the ordered `patches/linux-integration` followups in a full source checkout when reproducing those changes manually.

The maintained Nura package is developed in the public pmaports fork on `integration/fx0-v26.06`. Its source archive pins the Linux integration commit and records SHA-512 alongside the updated configuration. For a normal native package build, use `pmbootstrap build linux-postmarketos-qcom-msm8226`; Strict native clean builds now pass for both the preceding integration revision and the exact latest regulator-load fix. Final hardware, update/recovery and submission-base qualification remain separate. The initial development APK uses `build --envkernel` to package the verified host build. On this glibc host, that path needed an Alpine-built signing helper and a temporary private signing-key copy readable by the chroot's `pmos` UID (12345). The host helper was restored and the temporary key copy removed after packaging. The original key's permissions were preserved.

`pmbootstrap kconfig check linux-postmarketos-qcom-msm8226` now passes. Linux 6.18's explicit legacy xtables gate and dependent modules had to be enabled after olddefconfig migration; those are required by the current Nura checks. Remaining preference messages for built-in USB gadget support and modular optional filesystems are informational.

Use `pmbootstrap install --no-split` for the generic MSM8226 image containing the ext2 boot and root subpartitions. A development command-line drop-in at `/etc/kernel-cmdline.d/50-fx0-development.conf` requests inherited framebuffer, ramoops and warm reboot support. Verify the generated extlinux configuration contains the Fx0 DTB search path and correct root/boot UUIDs. The combined image must fit entirely within the independently reverified `userdata` partition before any deployment.

The installed console development system now uses the `postmarketos-base-nosplash` provider after a Plymouth crash. Keep the four development command-line entries shown above; the trial `clk_ignore_unused` and `pd_ignore_unused` flags did not restore visible display and have been removed. The owner still sees a blank screen despite working SSH. Final native display support remains required.

## Experimental display IOMMU build

The native panel candidate on `integration/fx0-lts` fails at the maintained MDP5 IOMMU requirement. The separate public `integration/fx0-iommu` branch, pinned by `evidence/2026-10-29-display-iommu-candidate.json`, carries the upstream QSMMU dependencies plus MSM8226-specific configuration/wiring. Its kernel/module build and targeted schema checks pass; it has not yet passed physical scanout or a Nura package boot. Keep the previous diagnostic artifacts frozen.

Use a separate full source worktree/output to preserve the verified baseline. Starting from this repository's diagnostic config, enable `CONFIG_QCOM_IOMMU=y` with the kernel `scripts/config` tool and run `olddefconfig`, then build `zImage modules qcom/qcom-msm8926-lg-madai.dtb` with `ARCH=arm LLVM=1`. Record the resulting exact source/config/artifact hashes. For controlled testing, generate a RAM diagnostic with `--return-after 180`; load matching signed modules only after USB log capture is established. The image generator now advertises 500 mA using ConfigFS's milliamps unit; it does not itself implement charger-current negotiation.

## Optional raw-image boot preparation

The separate public lk2nd branch `integration/fx0-rawboot` at `b106e16d0f3fc0e11c55aa58e4c617b89a0e3ef5` adds `LK2ND_EXTLINUX=0`. Use the existing MSM8226 recipe with that option and a separate output directory to omit filesystem discovery. Default `1` retains the existing path. Both configurations and a disabled-search/forced-fastboot diagnostic configuration build; invalid values are rejected. Check `evidence/2026-10-29-lk2nd-rawboot-preparation.json` for the exact artifacts. These are host-built preparation images and have not been flashed.

For a future controlled raw-image test, the forced-fastboot variant permits explicitly selecting `fastboot continue` while automatic diagnostic reboots return to the menu. Its virtual boot partition still starts at the existing 512 KiB offset. Validate that handoff, offset writes/readback and physical key/cold recovery before enabling a normal raw-image configuration. A host regular-file test with the actual RAM image validates updater byte preservation only.


## Display power candidate

The display-power branch at `476e36e72527b4115b656117634fb17a4b6e77dc` includes
camera DT, panel shutdown ordering and the shared CPU-PLL L8 supply fix. Image26
retains compiled39 and changes only the DTB; image27 contains the full kernel44
build and matching modules. Both have visible scanout and complete off/on tests.
Kernel44 still needs an initial power reference with its original MSM module.

The newer `integration/fx0-display-start` branch at
`c6ca8a0b04d1ce4bbd3d0cde7d079e532dd36b43` takes a bounded parent PM reference
for child creation and an optional DSI bus-clock reference for version queries.
Exact44 external-module W=1 and individual checkpatch checks pass. Its clean
module starts and cycles successfully in some tests, but repeated startup is
intermittent. Keep it experimental and record each boot outcome.

A fresh native r1 APK from source476e36e72 is exported and verifies with the
installed Nura trusted keys. Its build began with the prepared recipe changes
before their equivalent commit0b5e31934; PKGINFO says -dirty and this is recorded.
It has not been installed. Preserve the working kernel/module archives: kernel44
regenerated its signing key during build and has a different trust certificate
from39. Load matching modules with the actual trusted key; never force versions
or signatures. See the current build/package evidence for exact hashes.

The r1 APK now also passes a RAM diagnostic boot using its own kernel and modules:
USB, RMI probe, native DRM and a five-second off/on, followed by owner-confirmed
RGB. Initial MDSS/IOMMU holds were used and released before the cycle. Direct
archive extraction bypasses APK triggers, so regenerate module indexes with the
target's kmod before loading modules. The normal installed kmod trigger does
this automatically. This is not an installed-system or hold-free startup pass.

For persistent startup diagnostics, apply
`configs/diagnostic-display-pm-debug.fragment` to a separate output tree and
build its own matching module set. The tested diagnostic layout reserves the
same 512KiB at 0x2ff80000, split into128KiB crash records (8KiB each),128KiB
console and256KiB function trace with `flags=1` for per-CPU records. This layout
requires omitting `lk2nd.pass-ramoops`, whose DT hook overrides sizes. Retrieve
`oem ramoops raw` before any subsequent boot and decode using these sizes;
lk2nd's ordinary console command assumes its original layout. Do not use the
diagnostic configuration as a production package. The exact source and artifact
hashes are in the persistent-trace evidence.


### Native package initramfs RAM test

The [temporary native Nura RAM-boot guide](../diagnostics/native-display-boot-hold/README.md)
describes regenerating the normal initramfs using the native r1 kernel/module
set, keeping output and configuration changes in RAM. It includes an initial
display-power workaround and a complete matching-module overlay for testing
against the older installed root. These are development helpers, not qualified
startup or suspend fixes. Image33 reaches emergency mode without SSH. Large full-module images34/35
overlap the inherited framebuffer because LK overrides the load address.
Deduplicated XZ image36 stays below it and reaches a physically confirmed
readable console and SSH with taint 0 and automatic display PM. Evidence and
hashes are in [the RAM-initramfs record](../evidence/2026-10-29-native-nura-ram-initfs.json).


### Persistent native r1 development installation

The native r1 package now boots from the installed eMMC filesystem, with its
matching modules on ext4 and a temporary initial display-power workaround.
[Installed evidence](../evidence/2026-10-29-native-r1-installed-boot.json) records
one fresh boot, authenticated SSH, taint 0 and the physical two-contact test.
It does not close repeated/cold/default boot, full suspend or hardware acceptance.

Before updating, archive the existing boot files, kernel modules/release metadata,
configuration and package state; retain the exact old APK on two off-device
filesystems. Fingerprint raw boot and both GPTs. Configure the tested prefix
at `/usr/local/libexec/fx0-init`, map the original init to `/init.fx0-original`
and the prefix to `/init`, and include the panel/backlight/input modules. Install
only the display cleanup hook; the RAM-module overlay hook is unnecessary for
an installed matching kernel. The development override selects
`deviceinfo_dtb="qcom-msm8926-lg-madai"` and explicitly sets
`deviceinfo_flash_kernel_on_update="false"`. Preserve tested command-line
fragments and normal fstab-derived root/boot discovery.

When installing from the RAM-test environment, ensure APK writes to the real
module filesystem. Live libkmod mappings can keep the temporary module mount
busy. In this test a separate RAM bind retained those mappings, then lazy
detachment exposed ext4 for the package install. No on-disk filesystem was
forcibly unmounted. Use a supervised process for the update: the earlier detached
SSH/sudo launcher exited before starting, while a systemd transient service
completed normal APK and trigger processing. Inspect completion state and logs
before retrying any stage. The old dated development version sorts above r1;
the explicit trusted APK installation is a package-version downgrade while
advancing the tested source.

Keep old boot files in a subdirectory outside the `vmlinuz*` selection glob,
retain their module release, and add an explicit fallback entry. Verify the new
kernel and Fx0 DTB against the signed APK, inspect initramfs bytes/module ABI and
load-slot fit, and confirm raw boot/GPT fingerprints are unchanged. Reboot through
lk2nd and verify a changed boot ID and persistent module filesystem. The selected
`fastboot continue` path is tested here; default unattended boot and fallback
selection still need qualification. The device's final update and consolidated
storage path remain separate acceptance work.


### Native r2 touch orientation update

The r2 recipe at f50eb6893 uses Linux87d953b4, adding only the standard X/Y
inversion properties to RMI Function12. DTB build/schema/checkpatch and Nura
kconfig checks pass. The signed native APK's DTB matches the physically tested
RAM candidate byte-for-byte. Its embedded abuild recipe commit still reads
`-dirty` despite a clean committed host recipe; record this limitation alongside
the external source/archive/recipe/APK hashes. Do not rewrite signed metadata.

The trusted APK dry run selects one upgrade, r1 to r2. Normal installation and
mkinitfs/boot-deploy complete. The final wrapper check catches the missing manual
fallback label. Restore that preserved label only, rather than repeat the upgrade.
The current generator replaces extlinux.conf and does not preserve manually added
entries; update-safe fallback generation and a physical rehearsal remain required.
Saved old boot files/module tree alone do not complete update/recovery acceptance.

Readback verifies r2 kernel/DTB, matching-ABI initramfs, preserved initial-hold
hooks and a safe 11,955,718-byte ramdisk. Raw boot and both GPT copies are unchanged.
An eMMC filesystem boot through selected lk2nd continue reaches SSH, msmdrmfb,
real ext4 modules, both live inversion flags and taint0. Minimal Wayland is used
for the installed touch check while the separate UPower/battery defect is open.
See the r2 installed-boot evidence for exact hashes and remaining gates.


### Rootless native r3 and retained recovery menu

The tested v26.06 integration now points to0a7b0e9fa and Linuxd80fe993. Both the
canonical Linux/pmaports integration branches are fast-forwarded to these tested
revisions. Rootless Podman builds UPower armv7 through qemu-only and the kernel
through LLVM cross-native compilation without host sudo. Private container device
bindings, fresh work initialization and `--lax` are documented in
[the build fixture](../diagnostics/rootless-native-build/README.md).

The checked wrapper supplies the verified clean recipe snapshot and timestamp
to abuild before signing. Native kernel r3 embeds the exact0a7b0e9fa commit; older
artifacts keep their honest `-dirty` metadata and external provenance. The native
r3 DTB matches the physically tested RAM button candidate. Normal trusted upgrade,
boot-file/ABI/load-slot verification and eMMC boot pass. The installed owner test
confirms typing and keyboard gestures, and raw events confirm all three GPIO keys.

Current filesystem boot now uses a supported managed extlinux menu, documented
[here](../diagnostics/managed-extlinux/README.md). Disabling menu generation still
allows DTB/initramfs updates. Two normal regenerations and the actual r3 kernel
upgrade preserve the menu; the new DTB is copied and verified. Root UUID or command
line changes require explicit menu updates. A physical fallback rehearsal and the
final storage/raw-boot update design remain separate gates.

The [Fx0 Sxmo profile](../diagnostics/sxmo-fx0-profile/README.md) uses measured
gesture thresholds and observed input identifiers. It retains software rendering
and the current restricted idle/suspend/audio/modem test policy. This milestone
does not complete remaining hardware, power, cold-boot or reliability qualification.
