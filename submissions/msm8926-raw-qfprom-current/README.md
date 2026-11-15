# MSM8926 restricted raw-QFPROM proposal

This proposal carries the existing MSM8926 CPU/PVS and CPR calibration
reader onto NVMEM `for-next` at
`6628e7d4c6b25c8d18f1345e3a20d21829aae7e4`. It exposes a separate,
root-only, read-only raw view, retaining the existing keepouts around the
documented calibration rows and rejecting additional programming regions.
The corrected provider remains independent.

A synthetic-resource reproducer found that the earlier local proposal
accepted a view wider than the 4 KiB covered by its keepout table. Reads
beyond the final keepout could then reach the extra window. The new
feature rejects oversized views before NVMEM registration. The production
Fx0 board's existing 4 KiB resource is unchanged. This is a configuration
bounds issue; no security vulnerability or physical fault is claimed.

Local source commits:

- Binding: `c94c9248174c7712e0c960a1bf5cf0afde7ceebb`.
- Driver: `6c4c04ede46b2c81ba2971e869e3887deeb620db`.
- Integration: `a4e91406a10be6d00011fb2e6a5b8cb3cb639751`, based on
  panel/power/touch integration `ae10f0803a05730d33102925b7c88110a443ce39`.

The integration changes only the QFPROM driver and binding. Its complete
`arch/` tree is unchanged. QFPROM, NVMEM core, relevant headers, Kconfig and
Makefile exactly match the qualified NVMEM target.

## Evidence

- Qualcomm ARM built-in and ARM64 module builds compile the driver and
  NVMEM core with LLVM 21, `W=1`, and `COMPILE_TEST=n` on both bases:
  eight objects across four profiles, with no warnings.
- Extracted actual probe/read functions, current NVMEM keepout/read/sysfs
  helpers and registration assignment fragments execute 18,393 checks
  over synthetic aligned reads, boundaries, permissions, invalid resources,
  legacy probe profiles and acquisition errors. This count includes
  generated read patterns and their return/data assertions.
- The earlier proposal fails the oversized-view check; the guarded proposal
  passes. Removing root-only policy fails four checks, removing the
  extra-resource guard fails two, and removing keepouts fails 8,158.
  Address, undefined-behavior and leak sanitizers remain enabled.
- Normal binding examples pass, including both unchanged corrected-provider
  examples. The complete unchanged Fx0 DTB passes the selected schema.
  All 48 existing compatible strings pass synthetic corrected-provider
  profiles; ten malformed or forbidden-resource controls are rejected.
- All 19 integrated DTBs match the prior complete DTBs byte for byte.
  The original Fx0 DTB retains SHA256
  `c9cba4a019eb80eb5baddd366cefc9ec2f2bb89616d3d47a6ee99dc55498db65`.
  All audio descriptions remain present; audio execution is excluded.
  The same 58 inherited DTC warnings remain, with no new warnings.
- Full unfiltered schema validation still reports unmatched `sony,imx179`
  and `sony,imx132` bindings. This is not full-board schema acceptance.
- Strict checkpatch passes without signoff checks. Full checkpatch reports
  only missing human signoffs. Maintainer discovery is recorded; no
  messages have been sent.

The first clock rejection control exposed a checker assumption: a forbidden
property produces a generic `False schema does not allow` message without
the property's name. The final checker verifies that rejection and the
QFPROM schema identity. The schema was not relaxed.

## Replay

With Clang 21 and its sanitizers available, choose a new output directory:

```sh
python3 -B replay-fixtures.py --output /tmp/fx0-qfprom-fixtures
```

This verifies the five fixture hashes, compiles them and checks the exact
expected successes and failures without Git or a kernel tree. Fixtures
retain the executed C bytes and original copyright notices. The fixture
compiler disables unused-parameter/unused-constant diagnostics for extracted
kernel code; the actual native kernel builds use their normal `W=1` flags.

`check-binding.py` accepts a processed schema, complete Fx0 DTB, validator,
binding and new output directory. It replays artifact validation; it does
not rebuild the schema or DTB. These large build artifacts are separate.
`check-reader.py` can reconstruct fixtures from supplied kernel and driver
sources. Configurations, source hashes, commands and qualification records
are retained under `configs/` and `validation/`.

## Limits and attribution

All register values and resources are synthetic. Resource acquisition,
full device registration, runtime PM and SRCU are mocked. The fixture
executes selected real registration assignments rather than the full
registration function. It does not execute fuse programming. Sysfs access
tests use valid in-window aligned requests; kernfs bounds enforcement and
arbitrary trusted-kernel consumer requests are outside this model.

Physical CPU/CPR calibration behavior, higher CPU operating points and a
complete current kernel remain unqualified. This work neither enables CPR
nor changes CPU limits. All original non-audio hardware, interaction,
endurance, update/recovery and final currency requirements remain open.

The original local r50 overlay is
`5624c0158e00149c03f6d1ae53f96092015274bd`. Timothy Schmidt's author/date
and the existing source copyrights are retained. Codex (GPT-6) assisted
with adaptation, the size guard, fixtures and qualification. See `NOTICE`
and `LICENSE.GPL-2.0`. Human DCO certification remains pending. These heads
and this bundle are local and unpublished; no phone action is included.
