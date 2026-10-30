# Rejected PM8226 BATFET IRQ experiment

Loading this experiment produced sustained interrupt activity. It is excluded
from the Linux integration branch and installed Nura packages. The patches are
retained for source review and diagnosis, with the failed result recorded in
[the current-observation evidence](../../evidence/2026-10-30-bms-current-observations.json).

Base: Linux candidate `35743f1984fc7b9863224856dca0aa148e832be5` in
[fx0-linux](https://github.com/timschmidt/fx0-linux).

1. `0001-isolation-and-batfet-irq.patch` adds a shared battery-interface base,
   instantaneous BATFET validity checks and a both-edge interrupt that invalidates
   the relative charge epoch and queues measurements. A bounded RAM test exceeded
   its 100-events/second guard; the driver was unloaded.
2. `0002-disable-polling-and-refresh-for-observation.patch` disables both automatic
   polling sites and makes the IRQ handler acknowledge without scheduling work.
   It adds readback of the interrupt type/polarity registers. This variant still
   records 13,616 interrupts in 2.0025 seconds, approximately 6,799/second. Edge mode
   and both polarities read back enabled. No IADC current-debug entries or external
   calibration commits occur in the three-second observation window after probe.
   The deliberate ADC-conversion phase is skipped by the rate guard.

Both patches reconstruct the exact tested C sources; the second applies after
the first. They were compiled against the matching r4 ARM ABI using LLVM22 W=1
and loaded only from RAM with unsigned-module taint12288. The observer was unloaded
after the bounded observation. The result does not establish the electrical
cause of the interrupt activity or validate a single BATFET bit as a stable
indicator of battery isolation. It also does not identify which current reading
best represents battery current during the unresolved USB-idle discrepancy.

The patches modify Linux files under their existing GPL-2.0-only, dual GPL/BSD or
BSD licenses. Original license declarations remain in the source files. No raw
device dumps, firmware, calibration values or identifiers are included.
