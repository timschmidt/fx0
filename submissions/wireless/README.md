# Wireless draft submission

One cfg80211 regression fix for the
[wireless tree](https://git.kernel.org/pub/scm/linux/kernel/git/wireless/wireless.git)
(fixes). Its base is `main`, pinned on October 30, 2026 to
`25e73f1d6868c759c8eb56cad4e411692c5341b4` (7.3-rc7). It does not depend on any
Fx0 patch. **Not sent; upstream submission waits for owner approval and
sign-off.**

## Deferred scan-done message never sent

Mainline `dab68a74e90b` ("wifi: cfg80211: don't free driver-owned scan
requests") is also in 6.18.59 stable. Since that commit, when an interface goes
down mid-scan and the driver still owns the request, the scan-done message
parked in `rdev->scan_msg` is never sent. nl80211 then rejects every later scan
with `-EBUSY` until the wiphy is unregistered. With wcn36xx, ordinary
NetworkManager reconnection triggers this.

The [patch](0001-wifi-cfg80211-flush-deferred-scan-done-message-on-in.patch)
queues `scan_done_wk` whenever the message is parked. The
[submission branch](https://github.com/timschmidt/fx0-linux/tree/submission/fx0-cfg80211-scan-msg)
is `b639287c3b62`. Checks on the maintainer base:

- Strict checkpatch reports only the missing Signed-off-by (left for the owner)
  and a `Fixes` id unknown to the shallow fetch, confirmed in mainline.
- `get_maintainer.pl` lists Johannes Berg, linux-wireless and linux-kernel.
- LLVM W=1 builds of `net/wireless/scan.o` for x86_64 `defconfig` and ARM
  `multi_v7_defconfig` produce no warnings.
- The cfg80211 KUnit suite on UML passes 57/57. It does not cover this path.
- `git am` of the exported file reproduces the branch tree exactly.

The physical evidence comes from the same change on the Fx0's 6.18.59 kernel:

- tracepoint localisation
- a 10-cycle negative control that blocks from the first disconnect
- 10/10 cycles with the fixed module and with the installed signed r6 package

See the [diagnostic](../../diagnostics/wcnss-scan-busy/README.md) and
[evidence](../../evidence/2026-10-30-wifi-r6-qualification.json). Untested:

- a kernel built from the wireless tree on hardware
- other drivers
- P2P device interfaces, whose stop path uses the same deferred call

The patch states these limits below `---`. It carries `Assisted-by` and
`Cc: stable` under the kernel's coding-assistants and stable rules. Under the
threat model this is a functional regression, not a vulnerability.
