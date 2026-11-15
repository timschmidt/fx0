# SPDX-License-Identifier: GPL-2.0-only
"""Exercise extracted RMI callbacks with modeled hardware and PM selection.

This host fixture does not run the kernel PM core or any physical hardware.
It extracts the two PM-core eligibility decisions, the real RMI core callbacks,
and four transport callbacks. All lower-level I/O is replaced by explicit stubs.
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
out = base / ('suspend-' + label)
out.mkdir(mode=0o700)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def function(text, name):
    match = re.search(r'^(?:static )?int ' + name + r'\([^\n]*\)\n\{', text, re.M)
    assert match, name
    end = text.index('\n}', match.end()) + 2
    return text[match.start():end]


paths = ['drivers/input/rmi4/rmi_i2c.c', 'drivers/input/rmi4/rmi_driver.c',
         'drivers/base/power/main.c']
texts = [(source / path).read_text() for path in paths]
i2c, core, pm = texts
mark = re.search(r'\tif \(!error\) \{\n\t\tdev->power.is_suspended = true;',
                 pm[pm.index('static void device_suspend(struct device *dev,'):])
assert mark
mark = mark.group() + '\n\t}'
resume = pm[pm.index('static void device_resume(struct device *dev,'):]
skip = re.search(r'\tif \(!dev->power.is_suspended\)\n\t\tgoto Complete;', resume)
assert skip
skip = skip.group()
names = ['rmi_driver_suspend', 'rmi_driver_resume', 'rmi_i2c_suspend',
         'rmi_i2c_resume', 'rmi_i2c_runtime_suspend', 'rmi_i2c_runtime_resume']
extracted = '\n\n'.join(function(core if n.startswith('rmi_driver') else i2c, n)
                         for n in names)
shim = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
struct device { void *data; struct { bool is_suspended; } power; };
struct rmi_device { struct device dev; };
struct rmi_i2c_xport {
    struct { struct rmi_device *rmi_dev; } xport;
    int supplies[2];
    unsigned int startup_delay;
};
struct i2c_client { struct device dev; };
static int suspend_error, resume_error, enable_error;
static int rails, irq, off_calls, on_calls, suspend_calls, resume_calls, sleeps;
static int warnings, wake_off, wake_on;
static struct i2c_client *to_i2c_client(struct device *dev) { return (void *)dev; }
static struct rmi_i2c_xport *i2c_get_clientdata(struct i2c_client *c) { return c->dev.data; }
static void *dev_get_drvdata(struct device *dev) { return dev->data; }
#define dev_warn(dev, ...) ((void)(dev), (void)++warnings)
static int rmi_suspend_functions(struct rmi_device *dev) {
    (void)dev; ++suspend_calls; return suspend_error;
}
static int rmi_resume_functions(struct rmi_device *dev) {
    (void)dev; ++resume_calls; return resume_error;
}
static void rmi_disable_irq(struct rmi_device *dev, bool wake) {
    (void)dev; irq = 0; wake_off += wake;
}
static void rmi_enable_irq(struct rmi_device *dev, bool wake) {
    (void)dev; irq = 1; wake_on += wake;
}
static int regulator_bulk_disable(unsigned int n, int *supplies) {
    assert(n == 2 && supplies); assert(rails == 1); rails = 0; ++off_calls; return 0;
}
static int regulator_bulk_enable(unsigned int n, int *supplies) {
    assert(n == 2 && supplies); ++on_calls;
    if (enable_error) return enable_error;
    assert(rails == 0); rails = 1; return 0;
}
static void msleep(unsigned int delay) { assert(delay == 10); ++sleeps; }
'''
harness = r'''
static int pm_cycle(struct device *dev) {
    int error = rmi_i2c_suspend(dev);
MARK
    /* Model the ordinary resume and aborted-suspend unwind decision alike. */
SKIP
    dev->power.is_suspended = false;
    return rmi_i2c_resume(dev);
Complete:
    return error;
}
int main(void) {
    const int errors[] = {0, -5, -110, -19, -22};
    int cases = 0, stranded = 0;
    for (int bound = 0; bound <= 1; ++bound)
    for (unsigned int e = 0; e < ARRAY_SIZE(errors); ++e)
    for (int runtime = 0; runtime <= 1; ++runtime) {
        struct rmi_device rmi = { .dev.data = bound ? &rmi : NULL };
        struct rmi_i2c_xport x = { .xport.rmi_dev = &rmi, .startup_delay = 10 };
        struct i2c_client client = { .dev.data = &x };
        suspend_error = errors[e]; resume_error = enable_error = 0;
        rails = irq = 1; off_calls = on_calls = suspend_calls = resume_calls = sleeps = 0;
        warnings = wake_off = wake_on = 0;
        int ret;
        if (runtime) {
            ret = rmi_i2c_runtime_suspend(&client.dev);
            assert(ret == 0 && rails == 0);
            ret = rmi_i2c_runtime_resume(&client.dev);
        } else {
            ret = pm_cycle(&client.dev);
        }
        bool bad = rails != 1 || irq != 1 || ret != 0;
        if (bad) ++stranded;
        assert(off_calls == 1);
        assert(suspend_calls == bound);
        if (bad) {
            assert(bound && errors[e] && !runtime);
            assert(rails == 0 && irq == 0 && on_calls == 0 && resume_calls == 0);
        } else {
            assert(on_calls == 1 && sleeps == 1 && resume_calls == bound);
            assert(wake_off == (bound && !runtime) && wake_on == (bound && !runtime));
        }
        printf("bound=%d suspend_error=%d runtime=%d stranded=%d\n",
               bound, errors[e], runtime, bad);
        ++cases;
    }
    /* Existing system resume propagates regulator and function errors. */
    for (int which = 0; which < 2; ++which) {
        struct rmi_device rmi = { .dev.data = &rmi };
        struct rmi_i2c_xport x = { .xport.rmi_dev = &rmi, .startup_delay = 10 };
        struct i2c_client client = { .dev.data = &x };
        rails = irq = 0; on_calls = resume_calls = sleeps = 0;
        enable_error = which == 0 ? -5 : 0;
        resume_error = which == 1 ? -110 : 0;
        int ret = rmi_i2c_resume(&client.dev);
        assert(ret == (which == 0 ? -5 : -110));
        assert(rails == which && resume_calls == which && sleeps == which);
        ++cases;
    }
    printf("cases=%d stranded=%d\n", cases, stranded);
    return stranded ? 1 : 0;
}
'''.replace('MARK', mark).replace('SKIP', skip)
cpath = out / 'fixture.c'
cpath.write_text(shim + '\n' + extracted + '\n' + harness)
compiler = ['clang-21', '-std=c11', '-Wall', '-Wextra', '-Werror', '-g', '-O1',
            '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
            str(cpath), '-o', str(out / 'fixture')]
compiled = subprocess.run(compiler, capture_output=True, text=True)
(out / 'compile.log').write_text(compiled.stdout + compiled.stderr)
assert compiled.returncode == 0, compiled.stderr
run = subprocess.run([str(out / 'fixture')], capture_output=True, text=True,
                     env=os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                                       'UBSAN_OPTIONS': 'halt_on_error=1'})
(out / 'run.log').write_text(run.stdout + run.stderr)
summary = re.search(r'cases=(\d+) stranded=(\d+)\n$', run.stdout)
assert summary and not run.stderr, (run.returncode, run.stderr)
record = dict(source_head=(subprocess.check_output(['git', '-C', str(source),
              'rev-parse', 'HEAD'], text=True).strip() if (source / '.git').exists() else None),
              source_files_SHA256={p: sha(t.encode()) for p, t in zip(paths, texts)},
              extracted_SHA256=sha(extracted.encode()), fixture_SHA256=sha(cpath.read_bytes()),
              checker_SHA256=sha(Path(__file__).read_bytes()),
              cases=int(summary[1]), stranded=int(summary[2]), returncode=run.returncode,
              compiler=compiler, sanitizer_diagnostics=False,
              actual_kernel_PM_core_executed=False, hardware_executed=False,
              lower_level_IO='stubbed; successful rail disable, explicit suspend/resume errors',
              PM_eligibility='two source-extracted decision fragments; ordinary non-direct-complete path')
(out / 'result.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({k: record[k] for k in ['cases', 'stranded', 'returncode']}))
