# Fx0 fixed-register IMU identity diagnostic

This diagnostic prepares a direct AP identity read while the MPU-6515M control
path is being established. Raw samples, DMP execution and DMP interrupt wake have
separate acceptance gates in [the plan](../../docs/bringup-plan.md#61-mpu-6515m-dmp-access-and-interrupt-wake).

The preserved stock system has `/etc/sensor_def_qcomdev.conf`, an ADSP sensor HAL
and a sensor daemon. Its original `sns` partition contains `/cal/sns.reg`.
All 72 shared static keys in group 2690 match the stock defaults using the pinned
[`sns-reg` map](https://gitlab.com/msm8996-mainline/sns-reg/-/tree/4d238e5f0baba3fb77456fe2bffbf8e8f18a71a0).
Accel/gyro select bus 2/address 0x68/IRQ69; the defaults name MPU6500. This is
configuration evidence, not a silicon identity result. Bus2's proposed GPIO6/7
path follows the MSM8226 BLSP I2C2 pin description; actual connectivity still
requires the physical read. Calibration and complete stock files remain private.

The stock `qcom,msm-adsp-sensors` driver handles timing/OCMEM, which does not
establish direct MPU ownership. The proposed
[Sensor Manager path](https://lkml.iu.edu/hypermail/linux/kernel/2504.0/07239.html)
is an alternative for raw sensor operation, but its software-fusion outputs
alone cannot establish on-chip DMP execution. Modern libssc's SSC/Protobuf path
must not be assumed to implement the older SMGR transport.

`capture=0` only reads the two TLMM control/IO pairs. It requires the actual Fx0
compatible, the MSM8226 ADSP node disabled, and exactly one disabled QUP2 node at
0xf9924000. It makes no PAS or GPIO request. `capture=1` additionally requires a
successful `qcom_scm_pas_shutdown(1)` before any GPIO acquisition; a disabled DT
node alone does not prove that a warm-booted DSP stopped. GPIO requests must be
exclusive and the released bus must be idle-high. No supply is changed.

The temporary open-drain adapter performs only a one-byte register-pointer
transaction for WHO_AM_I 0x75 at 0x68, followed by a one-byte read. It does this
three times and requires 0x74 each time. It does not scan, reset/configure the MPU,
write firmware or manipulate IRQ69. The adapter exists only during these reads.
It is removed, acquired GPIOs are released, and their original control/output
values are restored and checked on cleanup paths. Reboot after PAS shutdown;
the diagnostic does not restart a previously running DSP.

Run `python3 diagnostics/imu-read-id/check.py`. It executes the actual DT-gating,
message and repeated-ID helpers in 800 sanitizer cases, including wrong/absent/
enabled nodes, duplicate buses, transfer errors/partial results and every byte
identity. It does not simulate the complete init/cleanup or secure firmware.
ARM LLVM22 W=1 compilation against canonical r4 source 5c3efd4c7fa8 passes. No
hardware pass is implied by compilation or the helper tests.

Before physical use, preserve exact module/source/ABI identities and current
boot/recovery artifacts on two filesystems. Verify the normal r4 kernel and
absence of active remote processors, then arrange a supervised return/reboot and
capture kernel messages privately. A userspace return timer is not a hard
deadline if secure firmware or the CPU stalls. Inspect the same running job
before retrying. Restore normal firmware/kernel, verify a fresh taint-zero boot,
normal services and original bootloader/GPT values afterward.

## Physical result

The first preflight and ADSP PAS1 shutdown succeed. GPIO6/7 both remain low;
capture refuses before clocking or registering an adapter and returns -EBUSY.
Pin restoration checks pass. A supervisor launch-status error is recovered from
the previous-boot journal; the hardware trial is not repeated. Normal r4/UPower
r4 returns with taint 0 and matching bootloader/GPT. See the
[sensor work record](../../docs/sensor-bringup.md) for the next power/mapping
investigation. No chip identity or DMP operation is qualified.
