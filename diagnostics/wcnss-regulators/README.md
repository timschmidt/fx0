# WCNSS regulator selection check

Linux 6.18.59 includes stable backport `3dbc90b9c22e` ("remoteproc: qcom_wcnss:
Fix handling the lack of PD regulators in v3"). It treats any table with at least
as many power-domain names as non-PD regulators as Pronto v3. Pronto v1 and v2
also name two domains and have one non-PD regulator. `wcnss_init_regulators()`
therefore requests only `vddcx` for them, whatever domains are attached.

On the Fx0 (Pronto v2, CX attached as the single power domain), the installed r4
kernel gets a dummy `vddcx` and never requests the described L3 MX or L6 PX
supplies. The [Linux fix](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-wireless-r4)
selects the v3 path only when the table has no PD regulators.

`check.py` extracts every `wcnss_data` table and the actual branch condition from
a Linux tree. It evaluates the requested supplies for each number of attached
domains and checks bounds:

```sh
python3 diagnostics/wcnss-regulators/check.py /path/to/linux
```

The unfixed 6.18.59 source fails six Pronto v1/v2 cases and reproduces the
physical observation. The fixed source passes all ten cases, including the
Pronto v3 and Riva cases that the original fix protects. This is a model of the
selection arithmetic only. Physical consumer state on the phone is recorded
separately in the wireless evidence.
