# Current vibrator and USB PHY review

Four vibrator patches select voltage ranges by register layout, clamp
the inclusive endpoint, replace stale drive bits during intensity
changes, and extract the PMI632 upper field with a right shift. One USB
PHY patch counts initialization pairs so offset zero remains valid and
rejects incomplete pairs. All five are unsigned local drafts.

The verified official input `next`/`master` base is
`ab13b5fc808e043a13f861a7c1c2ba8173c22b84` (7.4-rc2). PHY `next` is
`6bdfbe223ed4735073c299a6645ebd3faac3f51f` (7.4-rc1). These are separate
maintainer series; the small replay assembles their independent driver
fixtures, not a complete kernel tree. The separate combined runtime
keeps its 7.4-rc1 allocation API. Exact heads are in `qualification.json`.

| Actual-source model | Cases | Checks | Baseline failures |
| --- | ---: | ---: | ---: |
| Vibrator voltage and both drive fields | 12,303 | 86,077 | 23,832 |
| USB HS probe/power/init sequence | 782 | 47,691 | 14,203 |

Candidates and the combined-tree fixtures pass with address,
undefined-behavior and leak sanitizers. The vibrator tests cover every
speed in ascending/descending order, three register layouts, zero and
nonzero bases, unrelated bits and regmap errors. The earlier three
fixes still fail 8,160 checks because the older fixture excluded PMI632
upper-byte encoding. The fourth fix resolves that separately reproduced
bug. Four independent vibrator controls fail as expected.

USB tests include zero offsets at the start, middle and end; zero to
32 pairs; repeated on/off cycles; clock/regulator/init-write/reset error
cleanup; probe resource errors; absent sequences; and malformed length
validation before a failing data read. Three controls fail. The replay
extracts the actual MSM8226/8916/8939 bytes from the included full SoC
snapshots. USB baseline and candidate check totals differ because the
candidate also verifies the allocated pair count and exact allocation
size. This does not test every existing notifier/error path.

Six native Qualcomm profiles build 28 driver and related core objects
with LLVM 21, `W=1` and `COMPILE_TEST=n`, without diagnostics. They cover
both maintainer trees and the combined runtime as ARM and ARM64. The
ARM profile uses a built-in force-feedback helper; ARM64 uses a module.
Both vibrator drivers are modular. PHY checks include generic PHY,
ULPI bus and the actual ULPI viewport object; combined checks also
include regmap-SPMI and extcon. Object hashes and configurations are
bound by `native-components.json` and `configs/`.

Run the portable replay with Python 3, Clang 21 and standard `patch`:

```sh
python3 -B /absolute/path/to/fx0-vibrator-usb-phy-current/replay.py /tmp/vib-usb-replay-new
```

Choose a fresh output directory outside the packet. No Git, network,
phone, private logs or credentials are required. It verifies every file,
applies five patches with zero fuzz, checks resulting source bytes and
reproduces all 14 model variants. Do not disable LeakSanitizer when a
restricted environment blocks execution; use a normal host environment.
Recorded native builds are not repeated by this small replay.

For native reproduction, use the complete pinned source tree for the
desired profile, copy its supplied configuration into a new absolute
output directory as `.config`, and invoke successive `make` targets
`olddefconfig`, `modules_prepare`, then the objects listed in
`native-components.json`. Set `O=/absolute/output`, `ARCH=arm` or
`ARCH=arm64`, `LLVM=-21`, `W=1`,
`KCFLAGS=-Werror=incompatible-function-pointer-types` and `-j4`.
The corrected launcher also uses `--jobserver-style=pipe` to avoid
temporary FIFO collisions across isolated build processes.

Only two runtime source paths change. Every board/binding path and the
previously qualified display, camera, sensor, panel, power, touch and
wireless changes remain unchanged. This preserves their existing host
evidence and does not establish combined physical acceptance.

The current maintainer sources have not been booted on the Fx0. The
PMI632 fix has no PMI632 hardware test. Enabling the existing zero-offset
MSM8916/MSM8939 tuning requires separate hardware validation. This packet
does not qualify FF IOCTL behavior, physical vibration, electrical eye
diagrams, USB data/OTG/reconnect, concurrent operations, system suspend,
a fully linked kernel, package installation or recovery. It does not
resolve the original r2 display/IOMMU fault. Ordinary driver-bug
classification and all unsigned patches remain for human review and
DCO certification. No maintainer was contacted and nothing was published.
