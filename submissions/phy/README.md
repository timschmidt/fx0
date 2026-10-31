# PHY draft submission

One fix for the [PHY tree](https://git.kernel.org/pub/scm/linux/kernel/git/phy/linux-phy.git)
(Vinod Koul), based on `next` at `8f56fdf3d8cb9f1dbdc93bf9ac816698aa6f70b7`
(fetched October 31, 2026). It does not depend on any Fx0 board patches.
**Not sent:** mailing it needs the owner's approval and Signed-off-by.

The [submission branch](https://github.com/timschmidt/fx0-linux/tree/submission/fx0-usb-hs-init-seq)
is `fa8bc1003836`.

## The bug

`phy-qcom-usb-hs` ends its copy of `qcom,init-seq` with a zero-address
sentinel, but offset zero is a valid vendor register. The MSM8226, MSM8916 and
MSM8939 SoC descriptions (arm `qcom-msm8226.dtsi`, arm64 `msm8916.dtsi` and
`msm8939.dtsi`) all start at offset zero, so their whole sequence is skipped.
The MSM8974-family boards start at offset 1 and are unaffected.

The [patch](0001-phy-qcom-usb-hs-Apply-init-sequences-that-start-at-o.patch)
stores the pair count, annotates the flexible array with `__counted_by()`, and
rejects an odd-length property.

**Behaviour change for reviewers:** MSM8916 and MSM8939 boards will apply their
PHY tuning for the first time. The message says so and that those SoCs were not
tested. A `Tested-by` from an MSM8916 user would be valuable.

## Checks

- **Hardware:** the v6.18 form of this fix (`c7b37b2f2132`, from before
  upstream's flexible-array conversion `deb281cec3cb`) runs on the LG Fx0. USB
  device mode works with the MSM8226 sequence applied, across the warm and cold
  boot runs. The rewrite for `next` is build-tested only; it was not loaded on
  the phone, because its SSH link runs over this PHY.
- **Build:** LLVM W=1 for ARM `multi_v7_defconfig` and arm64 `defconfig`, each
  with `PHY_QCOM_USB_HS=m`, produces no warnings.
- **checkpatch:** `--strict` reports only the missing Signed-off-by.
- **Recipients:** `get_maintainer.pl --no-keywords` lists Vinod Koul, Neil
  Armstrong, linux-phy, linux-arm-msm and linux-kernel, plus commit signers.
  Also Cc the MSM8916 community (Stephan Gerhold, msm8916-mainline) because of
  the behaviour change.
- **Classification:** under `threat-model.rst` this is a regular bug.
- **Disclosure:** the message carries the AI-assistance paragraph and
  `Assisted-by: LLM`, with no Signed-off-by.
