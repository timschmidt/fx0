# RMI4 I2C suspend callback check

The checker compiles the four actual transport callbacks extracted from the
selected kernel sources. It uses small regulator and RMI-function stubs to
check sleep-command failures, ordinary resume, modeled PM unwind, preserved
resume failures, runtime behavior and 100 consecutive transitions.

Prepare a new source directory with these files:

| File | Source |
| --- | --- |
| `rmi_i2c-base.c` | Base `drivers/input/rmi4/rmi_i2c.c` |
| `rmi_i2c-patched.c` | Draft `drivers/input/rmi4/rmi_i2c.c` |
| `PM-core-current.c` | Base `drivers/base/power/main.c` |
| `rmi-driver-current.c` | Base `drivers/input/rmi4/rmi_driver.c` |

Run with Clang and working ASan/UBSan runtimes:

```sh
python3 diagnostics/rmi4-suspend/check-behavior.py \
  --source-dir /path/to/sources \
  --output-dir /path/to/new-results
```

The output directory must be new. The checker retains generated C fixtures,
compiler products, individual executions and `behavior-results.json`.
Successful execution passes 119 lifecycle cases, reproduces the original
defect and rejects four independently seeded regressions.

The test executes the extracted callbacks. Its PM-core decision is a
source-checked model; it does not execute kernel PM code or real regulators,
I2C, interrupts or suspend. Regulator-disable failures are outside this
fixture. A ptraced environment may prevent LeakSanitizer from operating;
run in a suitable environment with the sanitizers enabled.

See the [review draft](../../submissions/rmi4-suspend/README.md) for the exact
base, patch, ARM object checks and hardware limits.
