# SPDX-License-Identifier: GPL-2.0-only
"""Check extracted panel/PM power-reference sequencing with mocked hardware.

The callback interleavings are host controls; they do not demonstrate that the
current driver enables runtime PM, or execute DRM, devres or the real PM core.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys

base = Path(__file__).resolve().parent
source = Path(sys.argv[1]).resolve()
label = sys.argv[2]
assert re.fullmatch(r'[a-z0-9-]+', label)
out = base / ('panel-' + label)
out.mkdir(mode=0o700)
text = source.read_text()
corepath = Path(sys.argv[3]).resolve()
core = corepath.read_text()


def extract(body, name):
    match = re.search(r'^(?:static )?(?:int|void) ' + name + r'\([^\n]*\)\n\{', body, re.M)
    assert match, name
    return body[match.start():body.index('\n}', match.end()) + 2]


names = ['rmi_i2c_regulator_bulk_disable', 'rmi_i2c_release_reset',
         'rmi_i2c_power_off', 'rmi_i2c_power_on', 'rmi_i2c_panel_prepared',
         'rmi_i2c_panel_unpreparing', 'rmi_i2c_suspend', 'rmi_i2c_resume',
         'rmi_i2c_runtime_suspend', 'rmi_i2c_runtime_resume']
functions = '\n\n'.join([extract(core, 'rmi_driver_suspend'),
                           extract(core, 'rmi_driver_resume')] +
                          [extract(text, n) for n in names])
shim = r'''
// SPDX-License-Identifier: GPL-2.0-only
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define container_of(ptr, type, member) ((type *)((char *)(ptr) - offsetof(type, member)))
struct device { void *data; };
struct i2c_client { struct device dev; };
struct rmi_device { struct device dev; };
struct drm_panel_follower { int unused; };
struct gpio_desc { int asserted; };
struct rmi_i2c_xport {
    struct { struct rmi_device *rmi_dev; } xport;
    struct i2c_client *client;
    int supplies[2]; unsigned int startup_delay;
    struct gpio_desc *reset_gpio;
    struct drm_panel_follower panel_follower;
    bool is_panel_follower, powered;
};
static int refs, irq, violations, suspend_error, resume_error, enable_error;
static int suspend_calls, resume_calls, enables, disables;
static struct i2c_client *to_i2c_client(struct device *d) { return (void *)d; }
static struct rmi_i2c_xport *i2c_get_clientdata(struct i2c_client *c) { return c->dev.data; }
static void *dev_get_drvdata(struct device *d) { return d->data; }
#define dev_warn(dev, ...) ((void)(dev))
static int rmi_suspend_functions(struct rmi_device *d) {
    (void)d; ++suspend_calls; return suspend_error;
}
static int rmi_resume_functions(struct rmi_device *d) {
    (void)d; ++resume_calls; return resume_error;
}
static void rmi_disable_irq(struct rmi_device *d, bool wake) {
    (void)d; (void)wake; irq = 0;
}
static void rmi_enable_irq(struct rmi_device *d, bool wake) {
    (void)d; (void)wake; irq = 1; if (refs <= 0) ++violations;
}
static int regulator_bulk_disable(unsigned int n, int *s) {
    assert(n == 2 && s); ++disables; --refs; if (refs < 0) ++violations; return 0;
}
static int regulator_bulk_enable(unsigned int n, int *s) {
    assert(n == 2 && s); ++enables; if (enable_error) return enable_error;
    ++refs; return 0;
}
static void msleep(unsigned int delay) { assert(delay == 10); }
static void usleep_range(unsigned int low, unsigned int high) {
    assert(low == 10000 && high == 20000);
}
static void gpiod_set_value_cansleep(struct gpio_desc *g, int value) {
    assert(g); g->asserted = value;
}
'''
harness = r'''
int main(void) {
    const struct { const char *steps; bool follower; } schedules[] = {
        {"psPc", true}, {"pSPc", true}, {"sdDSc", false}, {"sc", false},
        {"sSc", false}, {"pdDPc", true}, {"pPPppPc", true}, {"dDc", false},
    };
    int cases = 0, broken = 0;
    for (int reset = 0; reset <= 1; ++reset)
    for (int error = 0; error <= 1; ++error)
    for (unsigned int k = 0; k < ARRAY_SIZE(schedules); ++k) {
        struct rmi_device rmi = { .dev.data = &rmi };
        struct gpio_desc gpio = {0};
        struct i2c_client client;
        struct rmi_i2c_xport x = { .xport.rmi_dev = &rmi, .client = &client,
            .startup_delay = 10, .reset_gpio = reset ? &gpio : NULL,
            .powered = true, .is_panel_follower = schedules[k].follower };
        client.dev.data = &x;
        refs = irq = 1; violations = 0; suspend_error = error ? -110 : 0;
        resume_error = enable_error = 0;
        suspend_calls = resume_calls = enables = disables = 0;
        for (const char *step = schedules[k].steps; *step; ++step) {
            switch (*step) {
            case 'p': rmi_i2c_panel_unpreparing(&x.panel_follower); break;
            case 'P': rmi_i2c_panel_prepared(&x.panel_follower); break;
            case 's': rmi_i2c_runtime_suspend(&client.dev); break;
            case 'S': rmi_i2c_runtime_resume(&client.dev); break;
            case 'd': rmi_i2c_suspend(&client.dev); break;
            case 'D': rmi_i2c_resume(&client.dev); break;
            case 'c': rmi_i2c_regulator_bulk_disable(&x); break;
            default: assert(false);
            }
        }
        bool bad = violations || refs || x.powered || (reset && !gpio.asserted);
        broken += bad; ++cases;
        printf("schedule=%s reset=%d sleep_error=%d broken=%d refs=%d violations=%d\n",
               schedules[k].steps, reset, suspend_error, bad, refs, violations);
    }
    /* Failed enable must leave the vote absent, allowing a later retry. */
    struct rmi_device rmi = { .dev.data = &rmi };
    struct i2c_client client;
    struct gpio_desc gpio = { .asserted = 1 };
    struct rmi_i2c_xport x = { .xport.rmi_dev = &rmi, .client = &client,
        .startup_delay = 10, .reset_gpio = &gpio };
    client.dev.data = &x;
    refs = irq = violations = 0; suspend_error = resume_error = 0; enable_error = -5;
    assert(rmi_i2c_power_on(&x, false) == -5 && !x.powered && refs == 0 && gpio.asserted);
    enable_error = 0;
    assert(rmi_i2c_power_on(&x, false) == 0 && x.powered && refs == 1 && !gpio.asserted);
    rmi_i2c_regulator_bulk_disable(&x);
    assert(refs == 0 && !x.powered && gpio.asserted && !violations);
    ++cases;
    /* Function-resume failure is visible; a complete power cycle can retry. */
    resume_error = -110;
    assert(rmi_i2c_power_on(&x, false) == -110 && x.powered && refs == 1);
    rmi_i2c_power_off(&x, false); resume_error = 0;
    assert(rmi_i2c_power_on(&x, false) == 0 && refs == 1);
    rmi_i2c_regulator_bulk_disable(&x);
    assert(refs == 0 && !violations);
    ++cases;
    printf("cases=%d broken=%d\n", cases, broken);
    return broken ? 1 : 0;
}
'''
cpath = out / 'fixture.c'
cpath.write_text(shim + '\n' + functions + '\n' + harness)
command = ['clang-21', '-std=c11', '-Wall', '-Wextra', '-Werror', '-g', '-O1',
           '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
           str(cpath), '-o', str(out / 'fixture')]
compiled = subprocess.run(command, capture_output=True, text=True)
(out / 'compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr
run = subprocess.run([str(out / 'fixture')], capture_output=True, text=True,
                     env=os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                                       'UBSAN_OPTIONS': 'halt_on_error=1'})
(out / 'run.log').write_text(run.stdout + run.stderr)
summary = re.search(r'cases=(\d+) broken=(\d+)\n$', run.stdout)
assert summary and not run.stderr, (run.returncode, run.stderr)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
record = dict(source_SHA256=sha(source), core_SHA256=sha(corepath),
              checker_SHA256=sha(Path(__file__)), fixture_SHA256=sha(cpath),
              cases=int(summary[1]), broken=int(summary[2]), returncode=run.returncode,
              sanitizers='ASan and UBSan; no diagnostics',
              actual_hardware_or_PM_DRM_devres_core_executed=False,
              runtime_PM_enabled_by_current_driver=False,
              controls='Synthetic callback interleavings with mocked low-level IRQ/rail/function I/O',
              regulator_disable='modeled successful; real disable-failure recovery not qualified')
(out / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({k: record[k] for k in ['cases', 'broken', 'returncode']}))
