# PM8226 USB input actuator candidate

Native r50 runs a configured high-speed gadget on `ci_hdrc.0`. Its only
configuration advertises 500 mA, and the legacy SMBB property reports a
500,000 µA input limit. The charger’s sysfs parent resolves to SPMI slave 0.
USB peripheral type `0x02`, subtype `0x34`, IMAX selector 5 and a clear
suspend bit agree with the selected 500 mA limit. The first observation used
the regulator slave and is excluded from the USB interpretation. These
values describe programmed limits rather than measured current.

The composite gadget calls `usb_gadget_vbus_draw` during configuration and
suspend/resume. ChipIdea forwards the request to a legacy `usb_phy` when
one exists. The Fx0 path uses the generic Qualcomm PHY, which leaves that
callback unsupported. A ConfigFS `MaxPower` value therefore does not show
that the USB charger accepted an updated current request.

The candidate builds on the experimental charging-policy commit
`2457eebe0bb67bcb5eccee7916650629cc4e9bf0`. It exposes the standard
`input_current_limit` property for the verified PM8226 SMBP USB path.
A zero request uses the vendor USB input suspend bit, with a fresh
battery-presence read before suspension. Positive values use the existing
selector conversion, which rounds down, and the existing verified write.
The input is resumed only after the selector readback matches. Reads
report zero when suspend is set and decode the hardware selector otherwise.
A value between zero and 100,000 µA is rejected. A future budget owner can
translate a suspend request below that hardware floor to zero.

An error on the standard positive path returns the original error and
attempts battery-checked suspension. A persistent bus failure can leave
the input enabled, so successful inhibition requires readback. The
existing `charge_control_limit` property keeps its configured-limit
semantics and does not change suspend state. Both write paths serialize
with the existing charger lock. The actuator operates on the USB path
and leaves the existing battery charging votes in charge of battery
charge enable. [Patch](usb-input-control.patch)

The 48 extracted-callback ASan/UBSan cases cover hardware identity, input
limits, absent battery, register write order, selector rounding, invalid
readback, single and persistent bus failures and legacy compatibility.
All 8,846 existing policy and legacy cases also pass. The policy test now
extracts by the charge verification function name so similarly worded
comments can coexist. The ARM `W=1` object builds with the experimental
policy enabled. Checkpatch reports zero errors and warnings with the DCO
check excluded.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 diagnostics/smbb-charging-policy/check-usb-input.py \
  --driver local/smbb-usb-input-01/qcom_smbb.c --output local/smbb-usb-input-recheck
```

The candidate remains a source patch and compiled ARM object. Routing
configuration, suspend, disconnect and role events to the actuator needs
integration. Physical validation must cover battery-powered USB suspension,
resume, actual current draw, charger-only startup and loss of a power source.
[Manifest](../../manifests/smbb-usb-input-control.json) ·
[Evidence](../../evidence/2026-11-10-smbb-usb-input-control.json)
