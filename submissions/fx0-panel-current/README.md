# LG Fx0 panel proposal and host qualification

The production LG Fx0 panel proposal now targets DRM misc-next at
`39e407b553ec15d4a233b651531ad431ed7542be`. It preserves the vendor
initialization payloads, display-on-before-sleep-out ordering, rail order,
waits and LP11 preparation. It tracks rejected power cleanup before taking
another VDD reference and reports unprepare errors to the DRM panel core.

The two attributed local proposals are:

- Binding: `272f4eb2214b420167edced50abd07cfa132a75c`.
- Driver: `8357d00127efde090b81815527ead651744390c8`.

The local integration on the previously qualified power/touch source is
`ae10f0803a05730d33102925b7c88110a443ce39`, based on
`2223cefc134cca099f3c9fb5470ed58b6057ca38`. Its entire `arch/` tree is
unchanged. Its panel source and binding match the DRM proposal exactly.
The integration preserves the existing charging-policy maintainer entry
alongside the proposed display entry.

## Evidence

- Native Qualcomm ARM built-in and ARM64 module profiles compile the panel,
  DRM panel core and DSI core with LLVM 21, `W=1`, and `COMPILE_TEST=n`.
  All six objects pass on both the DRM target and the integration base.
- All 19 complete integrated DTBs match the prior qualified DTBs byte for
  byte. The full Fx0 DTB retains SHA256
  `c9cba4a019eb80eb5baddd366cefc9ec2f2bb89616d3d47a6ee99dc55498db65`.
  Audio descriptions remain present; audio execution is outside scope.
- Normal binding examples and the unchanged complete Fx0 DTB pass the
  selected panel schema. Thirteen missing-resource or malformed controls
  are rejected. Full unfiltered validation still has unmatched bindings
  for `sony,imx179`, `sony,imx132` and `qcom,msm8926-qfprom-raw`.
- The extracted panel, DRM panel core and regulator-disable code executes
  16 modeled power cases. The earlier proposal fails eight; the candidate
  fails none. Removing pending cleanup fails three, and hiding the
  unprepare error fails five.
- Actual on/off functions, DSI multi helpers and command helpers execute
  18 command/error cases per variant. Baseline and candidate traces match
  vendor production command families, payload bytes and waits. Deliberate
  byte, wait and command-order regressions are detected.
- Strict checkpatch passes without signoff checks. Full checkpatch reports
  only the missing human signoffs. Maintainer discovery is recorded; no
  messages have been sent.

## Replay

Run the exported fixtures with Clang 21 and its address, undefined-behavior
and leak sanitizers available:

```sh
python3 -B replay-fixtures.py --output /tmp/fx0-panel-fixtures
```

Choose a new output directory. The runner verifies each fixture hash,
compiles it, checks all expected failures as well as successes, and writes
its results there. It needs neither Git nor a kernel tree. Fixture index
hashes distinguish the original executed C bodies from exported copies
with the original notices prepended and a comment end marker. See `NOTICE` and `LICENSE.GPL-2.0`.

`check-binding.py` accepts a processed schema, full Fx0 DTB, `dt-validate`
path and new output directory. This replays artifact validation; it does
not rebuild the kernel, schemas or DTBs. Native configurations, commands,
source hashes and qualification records are retained under `validation/`.
The large processed schema and DTBs are separate build artifacts.

## Limits and review status

GPIO, DSI, regulator hardware, sleeps, registration and locking are mocked
in the host fixtures. Power fault tests cover last-user hardware-disable
rejection before consumer decrement. Late failures after decrement,
coupled supplies, physical rail behavior and recovery remain unqualified.
Command tests do not qualify wire packet types or host timing. The vendor
uses some long-write packet types where current DSI helpers can choose
short writes; this proposal preserves the earlier driver behavior.

An initial malformed GPIO-string control crashed the validator's GPIO
decoder. An empty GPIO produced no selected-schema diagnostic despite the
processed `minItems: 1`. Neither result is counted as schema rejection;
both are retained in the private qualification history and summarized in
the public tool-limitations record. The schema was not relaxed.

Historical live testing removed a DCS-off timeout but still reset during
later host/PLL shutdown. This work does not establish complete cycling or
qualify a complete current kernel. The integration still lacks other
prepared runtime subsystems. The full non-audio hardware, interaction,
update/recovery and endurance requirements remain open.

Timothy Schmidt's original author/date and vendor copyrights are retained.
The original local proposals and folded LP11/shutdown changes are named in
the patch messages. Codex (GPT-6) assisted with adaptation, cleanup
tracking, fixtures and qualification. Human review of the proposed
maintainer entry and human DCO certification remain pending. These heads
and this bundle are local and unpublished. No phone update is part of this
qualification.
