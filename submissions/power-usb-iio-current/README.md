# Current Fx0 power, USB and sensor review

The guarded charger consumes battery voltage in microvolts and the raw-voltage
thermistor channel in millivolts. This proposal adds the missing processed VADC
interfaces, forwards configured USB gadget budgets to the charger, and keeps
charge inhibition under the existing independent policy, pack and fault votes.
The 83-point thermistor model and LG rules retain their vendor attribution.

These are local maintainer proposals with human review and DCO pending.
Timothy Schmidt's original authorship and prior AI-assistance disclosures are
preserved in the ten patches. Codex assisted with current-tree adaptation and
host qualification. No agent Signed-off-by has been added. The narrow proposed
policy MAINTAINERS entry still needs its named human's review. Nothing in this
directory authorizes publication or contact with maintainers.

The seven power patches target power-supply `for-next` at
`7071d4750856abbc68dfe431acc58a1d45dd42e8`; the two USB patches target Greg's
`usb-next` at `6628e7d4c6b25c8d18f1345e3a20d21829aae7e4`; the sensor patch
targets IIO `togreg` at `1390ca4953a7400ca932cb49635f02c727f885a6`.
The integration base is the current SoC/APR proposal
`a7ba24173e4618ace25b68ec36991fb08b7b552e`. The existing APR review directory
contains the validation-only schema/complete-board patch. The integration
driver files match the independently qualified component versions byte for
byte. `qualification.json` pins all original and applied commits.

Two native Qualcomm profiles compiled 39 component objects with W=1 and
COMPILE_TEST disabled. This was component compilation, without a full kernel
link, module postprocessing, package build or physical trial. All 19 ordinary
platform DTBs match the prior APR results byte for byte. The full Fx0 board,
including audio descriptions, is intact. The selected binding examples and
USB/power malformed controls pass; full unfiltered board-schema gaps remain.
Firmware hook results from the prior exact full DTB still apply to its identical
bytes; PMIC I/O and pack identification in those checks are simulated.

The source-only export below executes actual default VADC scaling, registration
assignments, read callback, IIO processed-read wrappers, policy sample worker
and actuator control. Its 39 cases cover units and fractional precision,
temperature/voltage limits, conversion errors, stale samples, disappearance,
recovery and preserved inhibition votes. Three compiled broken variants must
fail. The synthetic bus and kernel primitives are frozen in chain-support.json;
ADC results, calibration references, work queues and PMIC registers are mocked.
It does not execute actual registration, driver core, USB transactions or
physical hardware. The connected USB fixture adds 131 checks through the real ChipIdea budget
callbacks, power-supply class dispatch and SMBB actuator in two linked C
translation units. It reuses the 59 original consumer checks and adds current
rounding, status completion, bus faults, absent-pack fallback and removal/use-
count guards. Three separately compiled broken variants fail on their intended
contracts. Synchronisation primitives, empty extension lists, reference counts,
firmware lookup and the PMIC bus remain simulated. The full driver core and
real USB transactions are not executed. The absent-pack zero-budget case keeps
100 mA and reports ENODEV. Persistent bus failure can leave the prior selector;
the test verifies the error report without claiming physical inhibition.

Run the portable fixture without Git or a kernel build directory:

```sh
python3 -B check-sensor-policy-chain.py source --output /tmp/fx0-sensor-chain --negative-controls
```

Run the connected USB fixture from the same source-only export:

```sh
python3 -B check-USB-provider-chain.py source --output /tmp/fx0-USB-chain --negative-controls
```

Use fresh output paths, Python 3, Clang and working ASan/UBSan runtimes.
No network or phone is accessed. The exported source headers and driver bodies
retain their original licenses and copyrights; GPL-2.0 text is included.
Checksums cover every exported file in files.json.

Physical sensor calibration, current/SOC, charging/thermal/source loss, USB
timing/current, suspend/recovery and the rest of the original nonaudio bringup
matrix remain requirements. This proposal does not resolve the r2 boot fault.
