#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise extracted actual transport callbacks with explicit PM unwind semantics."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-dir', required=True, type=Path,
                    help='Directory containing rmi_i2c-base.c, rmi_i2c-patched.c, PM-core-current.c and rmi-driver-current.c')
parser.add_argument('--output-dir', required=True, type=Path,
                    help='New directory for generated fixtures and results')
args = parser.parse_args()
source_base = args.source_dir.resolve()
base = args.output_dir.resolve()
base.mkdir(parents=True, exist_ok=False)
target = base / 'behavior-results.json'
assert not target.exists()
before = (source_base / 'rmi_i2c-base.c').read_text()
after = (source_base / 'rmi_i2c-patched.c').read_text()
names = ['rmi_i2c_suspend', 'rmi_i2c_resume',
         'rmi_i2c_runtime_suspend', 'rmi_i2c_runtime_resume']

def function(source, name):
    start = source.index('static int ' + name + '(struct device *dev)\n')
    end = source.index('\n}\n', start) + 3
    return source[start:end]

functions = {name: function(after, name) for name in names}
for name in names[1:]:
    assert function(before, name) == functions[name]
core = (source_base / 'PM-core-current.c').read_text()
assert 'if (!dev->power.is_suspended)\n\t\tgoto Complete;' in core
assert 'if (!error) {\n\t\tdev->power.is_suspended = true;' in core
driver = (source_base / 'rmi-driver-current.c').read_text()
assert 'rmi_disable_irq(rmi_dev, enable_wake);\n\treturn retval;' in driver
prefix = r'''
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define ARRAY_SIZE(array) (sizeof(array) / sizeof((array)[0]))
#define CHECK(expression) do { if (!(expression)) { \
 fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #expression); exit(2); } } while (0)
struct device { int unused; };
struct i2c_client { int unused; };
struct rmi_i2c_xport { struct { void *rmi_dev; } xport; int supplies[2]; unsigned startup_delay; };
static struct i2c_client client;
static struct rmi_i2c_xport transport;
static int sleep_error, power_error, resume_error, powered, sequence, warnings, checks;
static bool expect_system;
static const char *warning;
static struct i2c_client *to_i2c_client(struct device *dev) { (void)dev; return &client; }
static struct rmi_i2c_xport *i2c_get_clientdata(struct i2c_client *c) { CHECK(c == &client); return &transport; }
static int rmi_driver_suspend(void *rmi, bool wake) {
 (void)rmi; CHECK(wake == expect_system); sequence = sequence * 10 + 1; return sleep_error;
}
static int rmi_driver_resume(void *rmi, bool wake) {
 (void)rmi; CHECK(wake == expect_system); CHECK(powered); sequence = sequence * 10 + 5; return resume_error;
}
static int regulator_bulk_disable(unsigned count, int *supplies) {
 CHECK(count == 2 && supplies == transport.supplies); sequence = sequence * 10 + 2; powered = 0; return 0;
}
static int regulator_bulk_enable(unsigned count, int *supplies) {
 CHECK(count == 2 && supplies == transport.supplies); sequence = sequence * 10 + 3;
 if (!power_error) powered = 1;
 return power_error;
}
static void msleep(unsigned delay) { CHECK(delay == transport.startup_delay); sequence = sequence * 10 + 4; }
static void dev_warn(struct device *dev, const char *format, int error) {
 (void)dev; CHECK(error < 0); warnings++; warning = format;
}
static void reset_case(bool system) {
 sleep_error = power_error = resume_error = sequence = warnings = 0;
 warning = NULL; powered = 1; expect_system = system; transport.startup_delay = 37;
}
'''
suffix = r'''
int main(void) {
 struct device dev = {0};
 int errors[] = {0, -5, -6, -19, -110};
 for (unsigned i = 0; i < ARRAY_SIZE(errors); i++) {
  /* Both ordinary resume and unwind after another device fails call the same
   * transport resume callback once the PM core has marked this device suspended.
   * This models that documented core decision; it does not execute the PM core. */
  for (int later_device_failed = 0; later_device_failed < 2; later_device_failed++) {
   reset_case(true); sleep_error = errors[i];
   int result = rmi_i2c_suspend(&dev);
   bool marked_suspended = result == 0;
   CHECK(result == 0 && sequence == 12 && !powered);
   CHECK(warnings == (errors[i] != 0));
   if (errors[i]) CHECK(strcmp(warning, "Failed to suspend device: %d\n") == 0);
   CHECK(marked_suspended);
   sequence = warnings = 0;
   if (marked_suspended) CHECK(rmi_i2c_resume(&dev) == 0);
   CHECK(sequence == 345 && powered && warnings == 0);
   checks++;
  }
 }
 reset_case(true); CHECK(rmi_i2c_suspend(&dev) == 0); sequence = 0; power_error = -5;
 CHECK(rmi_i2c_resume(&dev) == -5 && sequence == 3 && !powered); checks++;
 reset_case(true); CHECK(rmi_i2c_suspend(&dev) == 0); sequence = 0; resume_error = -110;
 CHECK(rmi_i2c_resume(&dev) == -110 && sequence == 345 && powered && warnings == 1);
 CHECK(strcmp(warning, "Failed to resume device: %d\n") == 0); checks++;
 for (unsigned i = 0; i < ARRAY_SIZE(errors); i++) {
  reset_case(false); sleep_error = errors[i];
  CHECK(rmi_i2c_runtime_suspend(&dev) == 0 && sequence == 12 && !powered);
  sequence = warnings = 0;
  CHECK(rmi_i2c_runtime_resume(&dev) == 0 && sequence == 345 && powered); checks++;
 }
 reset_case(false); CHECK(rmi_i2c_runtime_suspend(&dev) == 0); sequence = 0; power_error = -5;
 CHECK(rmi_i2c_runtime_resume(&dev) == -5 && sequence == 3 && !powered); checks++;
 reset_case(false); CHECK(rmi_i2c_runtime_suspend(&dev) == 0); sequence = 0; resume_error = -110;
 CHECK(rmi_i2c_runtime_resume(&dev) == 0 && sequence == 345 && powered && warnings == 1); checks++;
 reset_case(true);
 for (int cycle = 0; cycle < 100; cycle++) {
  sleep_error = errors[cycle % ARRAY_SIZE(errors)]; sequence = warnings = 0;
  CHECK(rmi_i2c_suspend(&dev) == 0 && sequence == 12 && !powered);
  sequence = warnings = 0;
  CHECK(rmi_i2c_resume(&dev) == 0 && sequence == 345 && powered);
  checks++;
 }
 printf("PASS %d callback lifecycle cases\n", checks);
 return 0;
}
'''
cases = {
    'candidate': functions,
    'original-current-tree': {name: function(before, name) for name in names},
    'regression-propagate-sleep-error': functions | {
        names[0]: functions[names[0]].replace('\treturn 0;', '\treturn ret;')},
    'regression-skip-supply-disable': functions | {
        names[0]: functions[names[0]].replace(
            '\tregulator_bulk_disable(ARRAY_SIZE(rmi_i2c->supplies),\n\t\t\t       rmi_i2c->supplies);', '')},
    'regression-ignore-resume-supply-error': functions | {
        names[1]: functions[names[1]].replace('\tif (ret)\n\t\treturn ret;', '\tif (ret)\n\t\treturn 0;')},
    'regression-wrong-diagnostic': functions | {
        names[0]: functions[names[0]].replace('Failed to suspend device:', 'Failed to resume device:')},
}
results = []
for name, callbacks in cases.items():
    fixture = base / ('fixture-' + name + '.c')
    fixture.write_text(prefix + '\n'.join(callbacks[value] for value in names) + suffix)
    binary = base / ('fixture-' + name)
    compile_argv = ['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-O1', '-g',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    str(fixture), '-o', str(binary)]
    built = subprocess.run(compile_argv, capture_output=True)
    assert built.returncode == 0 and not built.stderr, built.stderr.decode()
    ran = subprocess.run([str(binary)], capture_output=True)
    (base / ('execution-' + name + '.json')).write_text(json.dumps(dict(
        returncode=ran.returncode, stdout=ran.stdout.decode(),
        stderr=ran.stderr.decode()), indent=2) + '\n')
    expected = 0 if name == 'candidate' else 2
    assert ran.returncode == expected, (name, ran.returncode, ran.stderr.decode())
    if expected:
        assert ran.stderr.startswith(b'FAIL line ') and b'AddressSanitizer' not in ran.stderr
        assert b'runtime error:' not in ran.stderr
    else:
        assert ran.stdout == b'PASS 119 callback lifecycle cases\n' and not ran.stderr
    results.append(dict(name=name, returncode=ran.returncode,
                        compiler_diagnostics=0, stdout=ran.stdout.decode(),
                        stderr=ran.stderr.decode(), fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest()))
result = dict(recorded_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    extracted_actual_callbacks=True, candidate_lifecycle_cases=119,
    original_defect_rejected=True, independent_regression_controls_rejected=4,
    sanitizer='ASan and UBSan', results=results,
    runtime_and_system_resume_callbacks_byte_unchanged=True,
    PM_core_behavior='Source-checked model; the kernel PM core is not executed by this host fixture',
    power_disable_failure_injection=False,
    actual_regulators_I2C_IRQs_or_hardware=False,
    full_kernel_or_module_link=False, physical_test=False)
target.write_text(json.dumps(result, indent=2) + '\n')
print('119 actual-callback cases passed; original defect and four regression controls rejected')
