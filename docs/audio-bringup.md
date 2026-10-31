# Fx0 audio gap assessment

The plan's [phase 6](bringup-plan.md#phase-6-complete-audio-sensors-and-peripheral-interfaces)
requires speaker, earpiece, microphones, headset jack, routing, UCM and call
audio. This is a source-only assessment of what exists and what must be
written. No audio component has been enabled on the phone.

## Stock design

From the pinned vendor tree (`msm8226.dtsi` and `msm8226-madai/`):

| Component | Stock description |
| --- | --- |
| Codec | WCD9302 "Tapan" (`qcom,tapan-slim-pgd`), SLIMbus PGD; reset GPIO72; 9.6 MHz MCLK from PMIC XO_PMIC_CDC_MCLK |
| Codec interrupt | `qcom,wcd9xxx-irq` on an MSM GPIO |
| Codec supplies | Buck S4 1.8–2.15 V (charge pump); L6 1.8 V (VDD-H, PX); L4 1.2 V (CX); L25 1.775–2.125 V (buck helper) |
| Mic bias | CFILT1/3 1.8 V, CFILT2 2.7 V; Fx0 marks MICBIAS1 as having an external capacitor |
| Bus | SLIMbus NGD controller at 0xfe12f000 (`qcom,slim-ngd`) with BAM |
| DSP | ADSP via `qcom,adsp-loader`; Q6 AFE/ASM/ADM routing, voice, LPA and LSM front ends |
| Card | `qcom,msm8226-audio-tapan`, model `msm8226-tapan9302-snd-card` |
| AUX PCM | SoC DT uses GPIO63–66. The Fx0 uses GPIO64 for the camera I/O regulator and GPIO66 for the magnetometer IRQ, so the board overrides these and they must not be copied |

The Fx0 DT names no separate speaker amplifier; the codec drives the speaker.
This must be confirmed against a stock runtime mixer state before routing is
written.

## Mainline status

Checked against remoteproc `for-next` (7.3-rc1), which carries current mainline,
and the running 6.18.59-r6 configuration:

| Piece | Mainline | Fx0 kernel |
| --- | --- | --- |
| ADSP remoteproc | `qcom,msm8226-adsp-pil` in `qcom_q6v5_pas`; SoC DT has the ADSP node, region and SMP2P | PAS built as a module; ADSP is not enabled on the Fx0 board |
| QDSP6 APR/AFE/ASM/ADM | Generic drivers exist, built for newer ADSP firmware | Not configured |
| SLIMbus NGD | `qcom-ngd-ctrl` matches only NGD v1.5.0 and v2.1.0; it needs the ADSP QMI SLIMbus service | Not configured |
| Tapan WCD9302/9306 codec | **None**; only WCD9335/934x (SLIMbus) and later codecs | — |
| MSM8226 machine driver | **None** in `sound/soc/qcom` | — |
| UCM | None for this card | — |

Public trees contain no mainline-style Tapan driver to build on.

## ADSP start

The ADSP now starts from RAM on the r6 kernel with the
board enable (`6fb0c0cae80b`). Its stock firmware fits the SoC reservation and
runs stably. It exposes the `apr`, `apr_audio_svc` and `apr_apps2` channels, the
**SLIMbus control service** (QMI 769) needed by the NGD controller, and the
**Sensor Manager** (QMI 256) with other sensor services. See
[ADSP evidence](../evidence/2026-10-30-adsp-start.json).

## Work required

1. Done: the ADSP starts and its QMI services are listed. Still to check: APR
   service versions. The sensor path depends on the same ADSP
   decision. Check whether audio and an AP-owned IMU can coexist.
2. Read the MSM8226 NGD version register. Check the ADSP QMI SLIMbus service
   against `qcom-ngd-ctrl`, and add a compatible only if the protocol really
   matches.
3. Check QDSP6 APR/AFE/ASM/ADM protocol versions against this ADSP firmware
   before reusing the generic drivers.
4. Write a Tapan codec driver: register map and defaults, supplies, MCLK,
   SLIMbus ports, DAPM, MBHC jack/button detection and mic bias. Model it on
   wcd9335's structure with the vendor `wcd9306` code as hardware reference.
   This is new upstream driver work with bindings and review.
5. Add an MSM8226 machine driver using `qcom` common helpers, the Fx0 routing,
   UCM and a Nura package.
6. Capture a stock runtime mixer/route baseline (speaker, earpiece, headset,
   mics) to verify routes and gains rather than guessing from source.

This is the substantial infrastructure workstream the plan anticipated. Steps
1–3 decide how much of the generic Qualcomm stack is reusable and come first.
Call audio depends on the modem path in phase 8.
