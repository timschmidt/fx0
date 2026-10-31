# MSM8226 SLIMbus NGD probe

Mainline `qcom-ngd-ctrl` supports NGD v1.5.0/v2.1.0 with the NGD at offset
0x1000 and expects the apps message-queue BAM pipes as fixed `dmas`. The
vendor driver reads the version and the pipes from the hardware after the
ADSP powers the controller. This module reproduces that read:

1. Look up the ADSP's QMI SLIMbus service (0x301, version 1, instance 0).
2. Select instance 0 with the ADSP as bus master, then request power
   "active". Both use the message layouts of `qcom-ngd-ctrl.c`.
3. Only if the power request succeeds, map `0xfe12f000` and log the control
   word (version in the upper 16 bits) and the status word at `0x804` (vendor
   V1 layout, odd controller) and `0x1004` (V2 layout, mainline v1.5.0).
4. Request power "inactive".

**Run it only with the owner available.** If the DSP acknowledges the vote
but the block is still unclocked, the register read can stall the bus, and
the phone then needs a long power-key press. Load it on a RAM boot of the
matching kernel, after `qmi_helpers`, and read the `fx0_slimprobe:` log lines.
Build it as an external module against the exact running kernel source and
configuration, as for the [q6core probe](../q6core-probe/README.md).
