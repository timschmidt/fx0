# Bounded NCI controller startup preparation

The next r58 RAM image is prepared and host-verified, with physical entry gated
on display/touch confirmation for native boot
`2e6126b9-498e-4d89-b23e-f08fe6ccc361`. It has not been staged or booted.
See [the manifest](../../manifests/nfc-controller-startup-ram.json) and
[preparation evidence](../../evidence/2026-11-08-nfc-controller-preparation.json).
The prior [cold lifecycle trial](cold-lifecycle.md) qualifies the exact five
signed modules and cold cleanup; it does not prove controller communication.

The image retains the qualified encoded kernel, DTB, command line, fourteen
base CPIO entries and independent 180-second init timer. It adds the same five
signed modules, a static ARM `nfc-state` helper, a separate permit/hash manifest
and `controller-startup.sh`. No firmware, CPU registration or invalid-signature
control payload is included. The original r56/r58 builds, APKs and four prior
NFC images retain their bytes.

`nfc-state.c` exposes only `get`, `up` and `down` for a numeric NFC index. It
resolves the `nfc` family, validates name/index/protocol mask and `RF_NONE` (2),
and obtains fresh powered state before and after a mutation. It requires the
kernel sender, expected sequence/type/version, negotiated capped ACK format,
matching request echo and exact attribute types/sizes. GET operations need
both data and ACK; ACK alone cannot establish the requested powered state.
Interrupted, failed or short mutation sends are never resumed or resent, and
an error triggers no automatic down/cleanup mutation. Unsupported poll, vendor,
secure-element and firmware commands have no CLI path.

The pinned NCI core's `DEV_UP` path sends `CORE_RESET`, `CORE_INIT` and
`RF_DISCOVER_MAP`. Mapping configures interfaces without starting discovery.
The NXP driver has no setup/post-setup/secure-element-discovery callback that
adds other initialization commands. `DEV_DOWN` resets the controller before
entering cold mode. Its kernel close path ignores the reset request result,
so powered=false and a successful netlink ACK alone cannot qualify that reset.
The shell additionally requires successful reset/init/map response traces and
manufacturer/version information from narrowly selected NCI debug functions.
It checks an active reference-clock vote and VEN high/FIRM low, then a cold
clock/GPIO return, stable IRQ count, and complete ordinary module unload.
It issues one up/down pair with no polling, RF discovery, vendor, secure-element
or firmware request. Kernel I2C retry behavior is unchanged.

Userspace reply waits have deadlines, with a 30-second helper budget, 35 outer
completion checks per operation and a 110-second checker budget. A synchronous
kernel handler can block inside sendmsg beyond a userspace receive deadline;
uncertain completion stops further mutations and leaves recovery to the
independent init timer. This preparation does not qualify recovery from a hard
kernel lockup. The observer invokes the checker once and subsequently reads
notes, boot hash and logs. Native pre/postflight additionally requires VEN/FIRM
low, released NFC pin ownership and zero reference-clock votes; those conditions
pass on the current native baseline.

Thirteen host tests cover 105 protocol/state/CLI and shell-fixture cases.
Address/undefined-behavior sanitizers and 16,384 packet byte/length variants
pass. ARM emulation matches all 79 helper cases and repeats those packet
variants. Tests detect five isolated weakened sequence, post-powered-state,
short-send, active-clock and close-reset-response guards. Exact ARM BusyBox
checks all four scripts, twelve debug-selector cases and five debug-write
allowlist cases. A real host exchange queries only its built-in `nlctrl`
family; no host or phone NFC command is sent. GCC's missing sanitizer runtime
initially prevents linking; the final suite uses the installed Clang runtimes
without skipping sanitizer coverage. These results verify preparation and
modeled callbacks, with real controller startup/identity/clock behavior still
unproven.

After this bounded startup is physically qualified, test open-device teardown,
then a suitable tag, RF/userspace and suspend/wake. Pending-IRQ and firmware
concurrency, installed update/recovery and wider bringup remain separate work.
