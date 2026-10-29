# Stock hardware findings

These observations belong to the development unit inventoried on October 29, 2026. They guide the maintained device tree and acceptance tests. A stock log or DT entry does not establish that feature works under Nura. Raw stock logs, DTBs and device identifiers remain private.

| Component | Evidence on this unit | Bringup consequence |
| --- | --- | --- |
| SoC | Stock identifies MSM8926 revision 1.1; lk2nd matches `lg,madai`, board ID 150 | Start from shared MSM8226 support; use MSM8926 modem variant when enabling it |
| eMMC | 15,758,000,128 bytes; 39 named partitions; stock lk2nd log reports HS200 | Preserve GPT/NV; verify storage supplies/pins and test only a selected development filesystem |
| Boot images | Android v0, 2048-byte pages, kernel load 0x8000, ramdisk 0x02000000, tags 0x01e00000 | Use the measured addresses; installed lk2nd OS offset is 512 KiB |
| Display | 720×1280, 24-bit continuous framebuffer inherited from stock | Inherited simpledrm is diagnostic; native DSI panel/reset/backlight qualification is separate |
| Touch | Stock log identifies Synaptics S3320; DT enables its board path | Translate the actual supplies/interrupt/reset and validate upstream RMI4 function support |
| Audio | WCD9302 Tapan SLIM codec and stock jack/button inputs | Needs SLIMbus/DSP firmware, board routing, ALSA and UCM qualification |
| Rear camera | IMX179 in stock probing and DT; EEPROM/actuator path present | Determine supported sensor driver and MSM8926 ISP pipeline; preserve calibration |
| Front camera | IMX132 in stock probing and DT | Sensor/CSI/ISP and camera switching remain required |
| WLAN subsystem | Stock WCNSS load range 0x0d200000–0x0d74f000; Iris TSMC 3.0, 48 MHz XO | Validate exact carveout and remoteproc before firmware start; port missing LTS WCNSS support |
| USB PHY supplies | Stock DT links PM8226 L10 fixed 1.8 V and L20 fixed 3.075 V | Describe those consumers and constraints; avoid borrowing another board's voltage policy |
| USB mode | Stock DT mode value selects peripheral mode in its vendor enum | Initial mainline device mode is explicit; product OTG/host support still needs determination |
| NFC | Enabled PN547 DT node at I²C 0x28 | Candidate identity until physical firmware/driver/tag tests confirm operation |
| LED controller | Enabled LP5521 DT node at I²C 0x32 | Inventory actual LED channels and routing before exposing notifications |
| Vibration | PM8226 QPNP vibrator node | Enable using verified board parameters, then qualify actual actuator behavior |
| Power/input | Stock power key, GPIO keys, battery/charging reports | Actual charger/battery limits, suspend, thermals and button operation remain separate work |

Original boot, recovery and LAF are each 32 MiB. The verified selected backup covers 29 critical partitions, totaling 359,137,280 bytes. Separate GPT metadata and independently verified host/phone recovery copies exist. The internal SD recovery copy must survive development installs; its presence is not a replacement for Disk B backups.

The original boot QCDT contains four match entries pointing at one 172,032-byte DTB, covering platform IDs 200/224 and SoC revisions zero/0x10001, board 150. Extracted source is a stock description, not a runtime firmware-patched memory map. Obtain the live handoff DT before enabling firmware carveouts or making final memory assumptions.
