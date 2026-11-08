# MPU-6515 DMP firmware and RAM transport

This is a prerequisite diagnostic for maintained-driver DMP support. It does
**not** start the DMP, decode its output or qualify interrupt wake.

The installed part reports WHO_AM_I `0x74`. InvenSense's AOSP MPU-6515 HAL at
[`d411d613f60e6305d48ade617c848262b62a582a`](https://android.googlesource.com/platform/hardware/invensense/+/d411d613f60e6305d48ade617c848262b62a582a/6515/)
contains a 2,943-byte image in `ml_load_dmp.c`. Its Linux CRC32 with seed zero
is `0xa7e2110d`, exactly the image contract in the manufacturer kernel driver
at [`04a77e80d63a6b792970c8567447f70d76ac7be4`](https://android.googlesource.com/kernel/msm/+/04a77e80d63a6b792970c8567447f70d76ac7be4/drivers/iio/imu/inv_mpu6515/).
The driver loads it at RAM address `0x20` and uses entry point `0x400`.
Matching the image contract does not qualify its algorithms on the Fx0.

The image and the accompanying InvenSense agreement stay in ignored local
storage. No firmware bytes are copied into the public repository. To obtain
and extract the pinned inputs from the original AOSP archive:

```sh
mkdir -p downloads/dmp-reference
curl -fL 'https://android.googlesource.com/platform/hardware/invensense/+archive/d411d613f60e6305d48ade617c848262b62a582a/6515.tar.gz' \
  -o downloads/dmp-reference/invensense-6515-hal.tar.gz
python3 - <<'PY'
from pathlib import Path
import tarfile
base = Path('downloads/dmp-reference')
with tarfile.open(base / 'invensense-6515-hal.tar.gz') as archive:
    for source, destination in [
        ('libsensors_iio/software/core/mllite/linux/ml_load_dmp.c', 'ml_load_dmp.c'),
        ('libsensors_iio/License.txt', 'HAL-License.txt'),
    ]:
        (base / destination).write_bytes(archive.extractfile(source).read())
PY
python3 scripts/extract_mpu6515_dmp.py \
  --source downloads/dmp-reference/ml_load_dmp.c \
  --license downloads/dmp-reference/HAL-License.txt \
  --output local/firmware/mpu6515-reference
```

The extractor pins both input-file hashes, parses only byte literals, checks
length/CRC/SHA-256, preserves the agreement, and creates a new private output
directory with a mode-0600 image. It refuses an existing output directory.

## Physical diagnostic

`check_memory.py` requires the existing MPU6515 driver, its debugfs register
interface, the verified Fx0 I2C address and the extracted reference image.
Run on the phone as root, with the files in a private directory:

```sh
systemd-inhibit --what=sleep --mode=block --who=fx0-dmp-memory \
  --why=DMP-RAM-transport-check \
  python3 check_memory.py --firmware mpu6515-dmp.bin \
  --snapshot original-ram.bin
```

It temporarily masks/stops the sensor proxy, holds runtime power, and refuses
an active capture buffer, motion event, FIFO or DMP. It saves a new private
RAM recovery file before writing. Only RAM banks 0–11 and addresses `0x20`
through `0xb9e` are written; reserved bytes and OTP banks are excluded. It
verifies the uploaded image and restores/read-verifies the pre-write RAM,
register selection, power policy and previous service state. SIGTERM follows
the cleanup path. Do not kill it with SIGKILL while it is writing.

The first trial assumed sequential debugfs reads retained the MPU memory
pointer. Image verification and restoration verification failed. The original
RAM contents from that first trial were not saved separately, so restoration
to that first pre-test state is **unproven**. The DMP was never enabled; normal
raw readings, power policy and the sensor service remained available.

A four-byte scratch trial isolated the error: explicitly addressed reads
matched writes, while sequential debugfs reads did not. Scratch restoration
passed. The corrected diagnostic explicitly selects each byte and adds the
private recovery snapshot. It uploaded and verified all 2,943 bytes across
all 12 banks, then restored and verified that retry's pre-write RAM. See the
[physical evidence](../../evidence/2026-11-06-mpu6515-dmp-memory.json).

## Remaining implementation

Integrate a firmware loader and lifecycle into the maintained IIO driver.
Use addressed, bounded no-increment MEM_R_W transfers; do not use register-
incrementing bulk reads or assume pointer persistence across transactions.
The bounded execution prototype now configures and decodes accelerometer
and six-axis quaternion packets. Port that lifecycle/parser into the driver
and add a reviewed userspace ABI and PM/IRQ wake path. Ordinary wake-on-motion remains distinct from DMP-generated wake.

The reference loader's verification skips the first memory bank; the corrected
Fx0 diagnostic verifies every uploaded byte. Do not infer that this difference
explains the failed debugfs trial: the indexed-read control identified that
trial's transport issue directly.

Targeted tests (no audio tests):

```sh
python3 -m unittest discover -s tests -p test_mpu_dmp.py -v
```

Bounded execution results and the later loss of temporary captures are recorded
in [execution evidence](../../evidence/2026-11-06-mpu6515-dmp-execution.json).
The successful diagnostic is not native IIO or suspend-wake qualification.
