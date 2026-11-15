# Camera clocks: unsigned current-maintainer drafts

Two separately routed drafts refresh the existing integration changes. Official
Qualcomm refs were observed and fetched on 2026-11-15 from
`https://git.kernel.org/pub/scm/linux/kernel/git/qcom/linux.git`.

| Draft | Advertised base | Local source head |
| --- | --- | --- |
| MCLK bug fix, `clk-fixes-for-7.4` | `60521e4ff9e7f1b41758f387842d73667a7f0410` | `747fd18ccba4e168ba63e254e977f160cab45756` |
| MCLK fix plus VFE AXI support, `clk-for-7.5` | `fbfe0c4beecfbd0e2958d91e5c95ff189bc489a0` | `443ed6739ab718fe75284baf182eaee4c7ded5c1` |

The four MCLK RCGs still omitted `mnd_width` on both bases. Their tables include
fractional M/N rates, but width zero prevents programming and reading those
registers. With the table's 600 MHz GPLL0 assumption, the 24 MHz entry therefore
produces 120 MHz. The fix restores the existing integration's eight-bit counters.
Its `Fixes` tag names `d8b212014e69`, the original MMCC driver introduction.
Historical Git objects confirm that all four widths were absent then and that
the original shared helper also gated M/N programming/readback on nonzero width.

The VFE AXI branch also still lacked rate propagation. Its new flag lets the
parent source supply the nonzero rate required by the new MSM8226 CAMSS resource
table. This is additional platform support, without an invented upstream capture
regression or Fixes tag. The integration series includes the MCLK fix as its first
patch at `85faf3b206a2d1c01ae4ef3220260b2eaa7b7623`; its MMCC file is byte-identical
to the standalone fix before the AXI flag is added.

## Qualification

[The evidence](../../evidence/2026-11-15-mmcc-camera-clocks-current.json) pins both
final source trees, original provenance, inputs, diagnostics, configurations and
compiled objects.

The ASan/UBSan fixture copies production descriptors, frequency tables, RCG
programming/readback helpers, parent lookup and CCF rounding functions. Regmap
access is emulated in owned memory; the CCF parent is backed by the actual AXI
table. Numeric rate expectations are generated independently with rational
arithmetic. Parent-rate assumptions are XO 19.2 MHz, GPLL0 600 MHz and MMPLL0
800 MHz; these are fixture inputs, not current phone measurements.

| Input | Rate cases | Correct | Mismatches | AXI result for a 266.67 MHz request |
| --- | ---: | ---: | ---: | ---: |
| Pristine fixes base | 50 | 28 | 22 | retains 100 MHz |
| MCLK fix | 50 | 50 | 0 | retains 100 MHz |
| MCLK plus AXI support | 50 | 50 | 0 | forwards; selects 266666666 Hz |

The 50 cases cover every listed MCLK rate for four MSM8974 clocks and the two
MSM8226 override clocks, including integer and fractional entries. Each corrected
candidate also passes five register-offset error propagation cases, invalid-parent
rejection and four omission controls that restore the 120 MHz failure. The AXI
candidate propagates parent errors; removing its flag restores the old result.

Both bases build the complete MMCC, RCG2, branch, common and CCF core objects on
native ARM32 with `COMPILE_TEST=n` and on ARM64 with `COMPILE_TEST=y`. ARM64 is a
compile-test path because the existing driver depends on `ARM || COMPILE_TEST`.
All four builds pass with LLVM 21, `W=1` and
`KCFLAGS=-Werror=incompatible-function-pointer-types`, with no warnings/errors.
Configurations remain unchanged during compilation and no signing key is created.

The exact executed fixture sources are
[check-clock.py](../../diagnostics/mmcc-camera-clocks/check-clock.py) and
[fixture.h](../../diagnostics/mmcc-camera-clocks/fixture.h). For a fresh result:

```sh
python3 diagnostics/mmcc-camera-clocks/check-clock.py --source <linux> \
  --output <fresh-directory> --expect-mnd fixed --expect-axi fixed
```

Use `--expect-axi broken` for the standalone MCLK fix, and both expectations
`broken` for the pristine recorded fixes base. This requires Clang 21 and an
environment where ASan/UBSan can execute normally. The scaffolding supplies minimal
host structs, arithmetic, locks/traces and regmap/parent interfaces. It does not
test the kernel ABI, actual source clocks, exclusivity/range transitions, hardware
timing, or a complete CCF set-rate transaction.

Component builds copy the archived native configs from
`submissions/camss-arm32-native-dma/configs`, enable `COMMON_CLK_QCOM`, request
`MSM_MMCC_8974=m`, set the architecture's compile-test mode above, and normalize
with `olddefconfig`. Build `modules_prepare`, then
`drivers/clk/qcom/mmcc-msm8974.o`, `clk-rcg2.o`, `clk-branch.o`, `common.o` and
`drivers/clk/clk.o`, using their full source-relative paths. Recorded build identity
is `fx0-review`, `source-check`, timestamp `2026-11-15 00:00:00 UTC`.

## Review status and limits

All three exported patches pass unfiltered strict checkpatch with `--no-signoff`:
zero errors, warnings or checks. Full checks report only missing human
Signed-off-by. Kernel guidance prohibits agents adding that human DCO tag.
The [fixes](fixes-maintainers.txt) and [integration](next-maintainers.txt) maintainer
lookups were generated in their actual source checkouts.

Timothy Schmidt's original authorship and the original Claude Opus 5.5
<noreply@anthropic.com> co-author credit are preserved. Original changes are
`0bf18e8b12f6` and `4422f09b6050`; current refresh and qualification used OpenAI
Codex. The initial second-checkout base error was preserved and corrected before
testing; no test from that wrong-base attempt is counted.

Both source branches and this review remain local and unsigned. No maintainer
contact, phone access, full kernel/package build, module load, boot image or
hardware camera/clock acceptance occurred. Existing CAMSS/IOMMU drafts, qualified
r7 artifacts and physical trial gates remain unchanged. Common DTS, Fx0 board and
sensor support, DMA/RDI geometry review and physical acceptance remain open.
