# Fx0 bring-up status (2026-11-23)

Installed kernel: **6.18.64-r13** (`linux-postmarketos-qcom-msm8226`), built offline and
signed from `timschmidt/fx0-pmaports` `development/fx0-venus-package-01` (patches 0001-0066)
on top of `timschmidt/fx0-linux` `development/fx0-venus-r13-01`. The r12 rollback set is
staged on the handset.

## Working on the installed system

| Area | State | Evidence |
| --- | --- | --- |
| Display, touch, Sxmo | Working; owner-checked after each install | `evidence/2026-11-23-fx0-r13-installed-venus.json` |
| Cameras (front IMX132, rear IMX179) | Both sensors stream, also across s2idle | r8-r13 exact-package RAM trials |
| Charging and battery reporting | Managed SMBB policy, capacity and Full | r5-r6 evidence |
| CPU frequency with CPR | 300 MHz-1.19 GHz, four-core checksum load clean | `2026-11-21-fx0-r11-deep-qualification.json` |
| Deep suspend (default) | MSM8226 cluster collapse with RPM handshake, RTC and power-key wake, all CPUs restored | `2026-11-21-fx0-r11-installed-deep.json`, `2026-11-23-fx0-r13-deep-soak.json` |
| RPM XO shutdown and VDD-min | Reached; VDD-min ~60.5 s of 61 s with the modem radio idle | `2026-11-21-msm8226-first-vddmin.json`, `2026-11-22-fx0-r12-installed-vddmin.json` |
| Venus video codec | H.264 hardware encode; stock FFmpeg decode byte-exact with matching timestamps, also after deep suspend | `2026-11-22-msm8226-venus-decoder-stock-ffmpeg.json` |
| Modem | Boots (rmtfs read-write), SIM read, GNSS receives | `2026-11-21-fx0-modem-sim-no-service.json` |

## Limits and open items

- **Cellular service**: the au band set (LTE 1/3/11/26, UMTS 1/5, GSM) sees no US network.
  The owner closed the modem-wake-from-deep test as a hardware limit.
- **VDD-min residency** varies while the out-of-service modem keeps scanning; the owner chose
  to keep the radio searching.
- **CPR suspend drain**: one 10 ms drain timeout seen in a RAM trial (suspend cleanly aborted);
  not reproduced in a 20-cycle installed soak.
- **FFmpeg filter-graph input** to `h264_v4l2m2m` crashes in userspace; raw-file input works.
- **Overnight unplugged drain** measurement armed on r13 (2026-11-23).
- **Upstream**: CAMSS v3 Tested-by drafts under owner review; nothing is sent without approval.
