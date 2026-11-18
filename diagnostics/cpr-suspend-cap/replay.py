# SPDX-License-Identifier: GPL-2.0-only
"""Replay the maintained CPR suspend fixture at the diagnostic DTB ceiling."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


DIAGNOSTIC_COMMIT = '4cb942677a07683bc8c7341829a96ad004704630'
SUSPEND_DTB_SHA256 = '577d54838cd0d739297ce1c9c9143c1c7623da33e18d38df9d0806cd4b4fbc63'
QCOM = Path('drivers/pmdomain/qcom')
L3_NODES = '/remoteproc/smd-edge/rpm-requests/regulators'
PACKET = (Path(__file__).resolve().parents[2] /
          'submissions/maintained-lts-system-coordinator-current')


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def committed_file(linux, path):
    return subprocess.check_output(
        ['git', '-C', str(linux), 'show', f'{DIAGNOSTIC_COMMIT}:{path}'])


def dt_words(dtb, node, property_name):
    values = subprocess.check_output(
        ['fdtget', '-t', 'u', str(dtb), node, property_name], text=True)
    return tuple(map(int, values.split()))


def wake_routes(linux, dtb):
    mpm = '/remoteproc/interrupt-controller'
    tlmm = '/soc/pinctrl@fd510000'
    spmi = '/soc/spmi@fc4cf000'
    pmic = spmi + '/pm8226@0'
    mpm_handle, = dt_words(dtb, mpm, 'phandle')
    tlmm_handle, = dt_words(dtb, tlmm, 'phandle')
    pmic_parent, pmic_pin, irq_type = dt_words(dtb, spmi, 'interrupts-extended')
    spi_pairs = dt_words(dtb, mpm, 'qcom,mpm-pin-map')
    mpm_to_spi = dict(zip(spi_pairs[::2], spi_pairs[1::2], strict=True))
    if (dt_words(dtb, tlmm, 'wakeup-parent') != (mpm_handle,) or
            (pmic_parent, pmic_pin, irq_type) != (mpm_handle, 62, 4) or
            mpm_to_spi.get(pmic_pin) != 190):
        raise ValueError('unexpected packaged TLMM, SPMI or MPM parent')

    pinctrl = committed_file(linux, 'drivers/pinctrl/qcom/pinctrl-msm8226.c').decode()
    _, marker, mapping = pinctrl.partition('msm8226_mpm_map[] = {')
    if not marker:
        raise ValueError('MSM8226 GPIO wake mapping was not found')
    gpio_to_mpm = {int(gpio): int(pin) for gpio, pin in
                   re.findall(r'\{\s*(\d+),\s*(\d+)\s*\}', mapping.split('};', 1)[0])}
    parent, motion_gpio, trigger = dt_words(dtb, '/soc/i2c@f9924000/imu@68',
                                            'interrupts-extended')
    if (parent, motion_gpio, trigger) != (tlmm_handle, 69, 1):
        raise ValueError('unexpected packaged IMU IRQ')

    gpio_routes = {'motion': (motion_gpio, gpio_to_mpm[motion_gpio])}
    for key in ('volume-down', 'home', 'volume-up'):
        node = '/gpio-keys/button-' + key
        parent, gpio, _ = dt_words(dtb, node, 'gpios')
        properties = subprocess.check_output(['fdtget', '-p', str(dtb), node], text=True)
        if parent != tlmm_handle or 'wakeup-source' not in properties.splitlines():
            raise ValueError(f'unexpected packaged wake property for {key}')
        gpio_routes[key] = (gpio, gpio_to_mpm[gpio])
    if gpio_routes != {'motion': (69, 33), 'volume-down': (106, 36),
                       'home': (107, 37), 'volume-up': (108, 38)}:
        raise ValueError('unexpected GPIO wake mapping')

    rtc = dt_words(dtb, pmic + '/rtc@6000', 'interrupts')
    power_key = dt_words(dtb, pmic + '/pon@800/pwrkey', 'interrupts')
    if rtc != (0, 97, 1, 1) or power_key != (0, 8, 0, 3):
        raise ValueError('unexpected packaged RTC or power-key IRQ')
    return dict(gpio_to_MPM=gpio_routes, PMIC_MPM_pin=pmic_pin,
                PMIC_parent_GIC_SPI=mpm_to_spi[pmic_pin],
                RTC_alarm_specifier=rtc, power_key_specifier=power_key)


def run_fixture(harness, name, tree, output, *options):
    result = subprocess.run([sys.executable, '-B', str(harness / name),
                             str(tree), str(output), *options],
                            capture_output=True, text=True, timeout=120)
    output.with_suffix('.stdout').write_text(result.stdout)
    output.with_suffix('.stderr').write_text(result.stderr)
    result.check_returncode()
    receipt = json.loads((output / 'qualification.json').read_text())
    if receipt.get('passed') is not True:
        raise ValueError(f'{name} did not pass')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('linux', type=Path, help='Git checkout with the pinned diagnostic commit')
    parser.add_argument('dtb', type=Path, help='packaged Madai suspend DTB')
    parser.add_argument('output', type=Path, help='new local output directory')
    args = parser.parse_args()
    if sha256(args.dtb) != SUSPEND_DTB_SHA256:
        raise ValueError('DTB does not match the packaged suspend diagnostic')

    ceilings = {name: dt_words(args.dtb, f'{L3_NODES}/{name}', 'regulator-max-microvolt')[0]
                for name in ('l3-ao', 'l3-so')}
    if set(ceilings.values()) != {1287500}:
        raise ValueError('unexpected active or sleep MX ceiling')
    routes = wake_routes(args.linux, args.dtb)

    output = args.output.resolve()
    output.mkdir(parents=True)
    tree = output / 'source'
    (tree / QCOM).mkdir(parents=True)
    for name in ('cpr-voltage.h', 'cpr-msm8926-suspend.h', 'cpr.c'):
        path = QCOM / name
        (tree / path).write_bytes(committed_file(args.linux, path.as_posix()))

    source = (tree / QCOM / 'cpr.c').read_text()
    if ('cpr_sleep_vote_init(drv->dev, data->plan.bootstrap_mx_uV,' not in source or
            'drv->rails.mx_max_uV = data->plan.bootstrap_mx_uV;' not in source):
        raise ValueError('diagnostic no longer uses the same covered plan for both MX guards')

    original = PACKET / 'harness'
    fixture_hashes = json.loads((PACKET / 'manifest.json').read_text())['files']
    harness = output / 'harness'
    harness.mkdir()
    for name in ('check-cpr-suspend.py', 'check-sleep-controls.py',
                 'cpr-suspend-cases.c', 'cpr-suspend-services.c'):
        if sha256(original / name) != fixture_hashes[f'harness/{name}']:
            raise ValueError(f'original fixture changed: {name}')
        shutil.copyfile(original / name, harness / name)
    services = harness / 'cpr-suspend-services.c'
    fixture = services.read_text()
    old_guard = '#define MAX_UV 1337500\n'
    if fixture.count(old_guard) != 1:
        raise ValueError('expected one synthetic MX ceiling in the original fixture')
    services.write_text(fixture.replace(old_guard, f'#define MAX_UV {ceilings["l3-so"]}\n'))

    model = run_fixture(harness, 'check-cpr-suspend.py', tree, output / 'transaction')
    controls = run_fixture(harness, 'check-sleep-controls.py', tree, output / 'controls',
                           '--groups', 'cpr-transaction')
    if model['failures'] or controls['controls'] != 4:
        raise ValueError('incomplete transaction or fault-injection results')

    summary = dict(passed=True, source_commit=DIAGNOSTIC_COMMIT,
                   suspend_DTB_sha256=SUSPEND_DTB_SHA256,
                   DTB_MX_ceilings_microvolt=ceilings,
                   packaged_wake_routes=routes,
                   simulated_transactions=model['cases'], invariant_checks=model['checks'],
                   synthetic_fault_controls=[record['name'] for record in controls['records']],
                   actual_helper_functions_sha256=model['bindings'],
                   capped_fixture_services_sha256=sha256(services),
                   only_model_services_ceiling_changed=True,
                   physical_suspend_attempted=False)
    (output / 'qualification.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
