# Bounded PM8226 BMS1 observation

This development module reads 46 bytes through 16 fixed `regmap_bulk_read` calls.
It discovers the existing PM8226 IADC platform device to obtain its parent's
regmap, verifies BMS type 0x0d/subtype 1 at 0x4000, and reads only the listed
BMS/output/companion windows. There are no register writes, module parameters,
new platform bindings or counter resets. The register definitions come from the
pinned vendor `drivers/power/qpnp-bms.c`.

Build against the matching ARM kernel configuration, generated headers and
symbol table with:

```sh
make -C /path/to/linux O=/path/to/matching-build ARCH=arm LLVM=1 W=1 \
  M="$PWD/diagnostics/pm8226-bms-readonly" modules
```

The tested diagnostic build uses Alpine Clang 22.1.3, r3's configuration except
release-suffix generation, and the previously validated matching symbol seed.
W=1 and checkpatch pass. The module is loaded briefly from RAM and immediately
unloaded. It is unsigned and external, so its expected kernel taint is 12288;
a subsequent reboot is required to clear it. This is a development diagnostic,
not a package or production driver.

The actual unit reports BMS1 type 0x0d/subtype 1, revision 2, and IADC companion
type 0x08/subtype 5, revision 4. Voltage/VSENSE and counter bytes are present.
The output-hold bit is deliberately not set, so these multi-byte counter reads
are **not coherent samples** and do not establish capacity, counter trends or
measurement accuracy. The PM8226 non-VM BMS requires its own driver support;
this does not qualify PM8916 VM compatibility or use of the companion as the
ordinary conversion ADC. No charger policy is changed.
