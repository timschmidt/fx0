# IIO draft submission

One fix for Jonathan Cameron's
[IIO tree](https://git.kernel.org/pub/scm/linux/kernel/git/jic23/iio.git),
based on `togreg` at `a3b3580713f3ac5a32dc2874ee546828977a1d68` (fetched October 31, 2026). It does not depend on
any Fx0 board patches. **Not sent:** mailing it needs the owner's approval and
Signed-off-by.

The [submission branch](https://github.com/timschmidt/fx0-linux/tree/submission/fx0-iadc-current)
is `60e3273b655b`. It is the integration commit `5c3efd4c7fa8` with a
`Fixes:` tag, the disclosure and `Assisted-by` trailer required by
`Documentation/process/coding-assistants.rst` and `generated-content.rst`, and
one continuation-line alignment fix.

## The fix

`iadc_read_raw()` stores a signed difference in a `u16`, so currents below the
zero reference wrap to small positive values. It also divides microvolts by
microohms, which gives amps, while the channel's IIO scale (0.001 mA) expects
microamps. The [patch](0001-iio-adc-qcom-spmi-iadc-Preserve-current-sign-and-mic.patch)
uses a signed difference and converts to microamps with 64-bit arithmetic,
returning `-ERANGE` outside the `int` range.

## Checks

- **Fixture:** the [host fixture](../../diagnostics/iadc-conversion/README.md)
  fails on the unmodified `togreg` driver and passes with the patch: 13
  vectors per channel under clang `-fsanitize=undefined`.
- **Build:** ARM `multi_v7_defconfig` with `QCOM_SPMI_IADC=m` builds the
  object with LLVM W=1 and no warnings.
- **checkpatch:** `--strict` reports only the missing Signed-off-by.
- **Hardware:** on the LG Fx0 (PM8226) the integration kernel reports negative
  sensed current where the unpatched driver reported 40 and 36.
- **Recipients:** `get_maintainer.pl --no-keywords` lists Jonathan Cameron,
  David Lechner, Nuno Sá, Andy Shevchenko, the commit signers Stepan Ionichev
  and Ivan T. Ivanov, and linux-iio, linux-arm-msm and linux-kernel. The
  keyword matches without `--no-keywords` (LLVM maintainers, triggered by
  "clang" in the changelog) are not relevant.
- **Classification:** under `Documentation/process/threat-model.rst` this is a
  regular bug, not a vulnerability.
