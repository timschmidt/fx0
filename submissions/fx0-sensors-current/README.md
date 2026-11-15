# LG Fx0 Sony sensor proposals and host qualification

Both complete existing sensor drivers are adapted to the media profile's
required development tree, `media-committers/next`, at
`48fe5a7834cc10081887d7bcd9ff0a4cadc3fa8c`.

The IMX132 retains its 1976x1200 RAW10 mode on one lane. The IMX179 retains
3280x2464 and 2x2-binned 1640x1232 RAW10 modes on four lanes, its corrected
0x8179 identity, 24 MHz clock setup and whole-array crop rectangles.
All original constants, register tables, mode tables and sensor structures
are byte-identical. Other callback tokens are unchanged except the two
verified corrections and current API signature adaptation described below.

Local source series:

- IMX179 binding: `0982febda6bb6446d13f800eb132938d41e873f2`.
- IMX179 driver: `d60c86f2d9ddb3f4795af18744bae7dd7c84177f`.
- IMX132 binding: `71e0dee09b6e6d5cb73f18f73b79cf6dbe14e42e`.
- IMX132 driver/head: `fbd111d84f091af4b7eca0161f49547b36d6e55b`.

The integration is `0996a0fbab5498883460e2b00517c4f51c729508`, based on
panel/QFPROM/power/touch integration
`a4e91406a10be6d00011fb2e6a5b8cb3cb639751`. Its complete `arch/` tree is
unchanged. Sensor sources, bindings and relevant V4L2/CCI/PM sources and
headers match the qualified media target exactly.

## Corrections

A failed standby write previously released the stream's runtime PM
reference while the real V4L2 stream helper kept the stream enabled.
A successful retry then reached the actual PM decrement helper's underflow
warning branch. Both candidates retain the reference after a failed stop
and release it after a successful stop.

The rear driver also accepted an ACTIVE format change while streaming.
Its mode pointer and reported format changed while the output-size
registers still described the previous mode. Both candidates reject ACTIVE
format updates while streaming; TRY negotiation remains available. The
rear's two modes provide the reproduced hardware/software-state mismatch.
The front's corresponding guard consistently applies the configuration
policy to its single supported mode.

The current `set_fmt` and `get_selection` signatures receive the unused
client-info argument. Original human authorship/date and earlier Claude
Opus 5.5 assistance are retained in the patch records. Codex (GPT-6)
assisted with adaptation, corrections, fixtures and qualification.

## Evidence

- Native Qualcomm ARM built-in and ARM64 module profiles compile both
  complete sensors and five actual V4L2 core components on each base:
  28 objects across four profiles, LLVM 21, `W=1`, `COMPILE_TEST=n`, and
  no build warnings.
- Extracted actual sensor stream, control, format and power functions run
  with current V4L2 stream helpers, CCI writes, nearest-size selection and
  PM count helpers. The front passes 146 checks and the rear passes 231.
  The prior proposals fail two and six checks respectively. Reverting the
  stop guard fails two front/four rear cases; reverting the rear format
  guard fails two. Address, undefined-behavior and leak sanitizers pass.
- The tests cover healthy repeated streaming, each initialization write
  failing in turn, resume/control-setup errors, failed-stop retries, TRY
  negotiation, rear live-mode rejection, active/inactive controls, normal
  power sequencing and supply-enable/clock-enable errors.
- Normal binding examples pass. The complete unchanged Fx0 DTB passes both
  selected sensor schemas. One additional IMX132 two-lane hardware-binding
  profile passes; the initial driver still supports one lane. Thirty-two
  missing-resource, lane, cardinality or unknown-property controls fail as
  intended.
- All 19 complete DTBs remain byte-identical to prior qualification. The
  full Fx0 DTB SHA256 remains
  `c9cba4a019eb80eb5baddd366cefc9ec2f2bb89616d3d47a6ee99dc55498db65`.
  The same 58 inherited DTC warnings remain, with no new warnings.
- Full unfiltered Fx0 schema validation now has zero diagnostics and zero
  unmatched bindings. Audio descriptions remain present; audio execution
  is excluded.
- Strict media checkpatch passes at 80 columns without signoff checks.
  Full checkpatch reports only four missing human signoffs. Proposed
  maintainer entries need human review. Maintainer discovery is recorded;
  no messages have been sent.

## Replay

With Clang 21, its sanitizers and standard Linux UAPI headers available:

```sh
python3 -B replay-fixtures.py --output /tmp/fx0-sensor-fixtures
```

Choose a new output directory. The runner verifies and compiles all seven
fixtures and checks their exact expected results without Git or a kernel
checkout. Original extracted C bodies remain intact inside attribution
comments. See `NOTICE`, `LICENSE.GPL-2.0` and `fixture-index.json`.
Unused-parameter/unused-constant diagnostics are disabled only in the
extracted fixtures; actual native builds use the normal kernel `W=1` flags.

`check-bindings.py` accepts the processed schema, complete Fx0 DTB,
`dt-validate` and new output directory. It replays artifact validation.
`check-callbacks.py` reconstructs fixtures from supplied kernel and driver
sources. Configurations, source hashes and original qualification records
are retained under `configs/` and `validation/`. Large schema/DTB build
artifacts are separate.

## Remaining qualification

Transport, active-state locks, control-cache helpers, privacy LEDs, power
resources and full runtime PM are mocked. The actual ioctl layer and
V4L2 compliance are not executed. GPIO and regulator-disable failure
recovery are unqualified. Persistent standby failures retain the enabled
stream and PM reference until a successful retry or device teardown;
automatic physical recovery from that fault is not established.

Physical frame integrity, Bayer order, analogue-gain calibration, scenes,
queues, lens/flash interactions, suspend and charging remain open. The
integration still needs other prepared runtime prerequisites before it can
be called a complete current kernel. All original non-audio hardware,
interaction, endurance, update/recovery, reproducibility and final currency
requirements remain intact.

Human DCO certification and proposed maintainer-entry review remain pending.
The source and review heads are local and unpublished. This qualification
includes no phone changes or maintainer communication.
