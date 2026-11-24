# RMI4 I2C suspend review draft

A failed RMI sleep command currently leaves the I2C supplies disabled while
returning an error from system suspend. The PM core skips resume for a device
whose suspend callback failed, leaving the transport powered down. The draft
completes the callback after powering down so resume can restore the transport.
It also corrects the copied resume diagnostic.

The single unsigned patch targets Input `master`/`next` at
`8e16f8bbf1bd528975fd6f4081eaf00513c1d83e` (Linux 7.4-rc2). It adapts Timothy
Schmidt's downstream fix `6d3c6c42f7bbfcc93dfac4e46da6debe23e4f3bd` without
requiring the downstream reset-GPIO or panel-follower additions. The current
allocation API and the other three transport PM callbacks are preserved.

The [public source branch](https://github.com/timschmidt/fx0-linux/tree/submit/rmi4-suspend-completion-v1)
preserves the upstream commits and signed merge bytes. Missing history was
recovered from exact Gitiles objects and checked through Git identities to
three boundaries already available in the destination fork. This does not
claim a full local clone of mainline history.

Apply the patch listed in [series](series). The [cover letter](0000-cover-letter.patch)
records the behavior, suggested recipients and qualification limits.
[Validation](validation.json) pins the reviewed tree and its tested equivalent.

The [actual-callback checker](../../diagnostics/rmi4-suspend/README.md) passes
119 lifecycle cases with ASan and UBSan, reproduces the unmodified tree's defect
and rejects four independent regressions. It covers preserved supply-enable and
RMI-function resume errors. The PM-core decision is modeled from checked source;
the host test does not execute kernel PM code or hardware.

Unmodified base and draft ARM objects pass Clang 21.1.8 `W=1` builds with no
diagnostics. KCFI and full zlib-compressed DWARF5 remain enabled. All four PM
callback type words match. The [normalized configuration](../../configs/linux-7.4-rc2-input.armv7)
is preserved byte for byte; its inherited local-version suffix does not identify
a phone image qualified by this draft. Strict checkpatch passes with only
sign-off checking disabled, and the exported patch replays to the exact draft
tree.

Earlier [Fx0 s2idle results](../../evidence/2026-11-01-s2idle-touch-mdp5.json)
exercised the same return-value fix together with separate touch-panel and MDP5
changes. Those results do not qualify this standalone maintainer tree.
Full kernel/module links, this tree's physical boot and suspend, other RMI
hardware, regulator-disable errors and GCC remain unqualified.

The receiving tree requires AI-assistance disclosure and prohibits agents from
adding DCO sign-offs or sending submissions. Human review and certification
remain pending. The draft has not been emailed and no upstream PR was opened.
