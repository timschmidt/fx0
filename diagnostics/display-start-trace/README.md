# Native display initialization trace

This companion to [the shutdown trace](../display-power-trace/README.md) logs
DSI configuration, PHY clock registration, initial MDP probe and MDSS child
population. It changes logging only and is not an upstream fix. Apply to the
exact base and original hashes in source-hashes.json. Use the shutdown trace's
external-build, trusted-signature, RAM-boot and retained-log procedure.

Load every MSM dependency before inserting the replacement module; use
`modprobe -a` for multiple dependency names. Keep the stock module unloaded.
Test initial loading without runtime holds only with a verified recovery path
and persistent log capture. A reset during probe has been observed on this
board. Download each staged retained-log payload before the next boot.
