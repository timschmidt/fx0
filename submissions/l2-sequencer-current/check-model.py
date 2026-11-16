# SPDX-License-Identifier: GPL-2.0-only
"""Compose actual L2 setup/arm/disarm/publication with synthetic regmap services."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess

B = Path(__file__).resolve().parent


def block(text, pattern):
    match = re.search(pattern, text, re.M)
    assert match, pattern
    end = text.index('{', match.start()) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    if text[end:end+1] == ';':
        end += 1
    return text[match.start():end] + '\n'


def function(text, name):
    return block(text, r'^(?:static\s+(?:inline\s+)?)?(?:int|void)\s+' + re.escape(name) + r'\([^;{}]*\)\n\{')


def model(source):
    driver = (source / 'drivers/soc/qcom/spm.c').read_text()
    header = (source / 'drivers/soc/qcom/spm-msm8226-l2.h').read_text()
    public = (source / 'include/soc/qcom/spm.h').read_text()
    names = ['spm_8226_l2_sequence_verify', 'spm_8226_l2_sequence_init', 'spm_8226_l2_disarm',
             'spm_8226_l2_set_mode', 'spm_8226_l2_master_init']
    bindings = {n:hashlib.sha256(function(header, n).encode()).hexdigest() for n in names}
    for n in ['spm_set_l2_low_power_mode', 'spm_8226_l2_register']:
        bindings[n] = hashlib.sha256(function(driver, n).encode()).hexdigest()
    tables = driver[driver.index('static const struct regmap_range spm_8226_l2_read_ranges'):
        driver.index('static int spm_8226_l2_register(')]
    code = (B / 'model-services.c').read_text()
    code = code.replace('/* ACTUAL_ENUM */', block(public, r'^enum spm_l2_sleep_mode \{'))
    code = code.replace('/* ACTUAL_HEADER */', re.sub(r'^#include[^\n]*\n', '', header, flags=re.M))
    code = code.replace('/* ACTUAL_ACCESS_TABLES */', tables)
    code = code.replace('/* ACTUAL_WRAPPER */', function(driver, 'spm_set_l2_low_power_mode'))
    code = code.replace('/* ACTUAL_REGISTER */', function(driver, 'spm_8226_l2_register'))
    code += (B / 'model-cases.c').read_text()
    for name in names:
        assert function(code, name) == function(header, name), name
    for name in ['spm_set_l2_low_power_mode', 'spm_8226_l2_register']:
        assert function(code, name) == function(driver, name), name
    words = re.findall(r'0x[0-9a-f]+', block(header, r'^static const u32 spm_8226_l2_sequence\[\] = \{'))
    data = b''.join(int(w,16).to_bytes(4, 'little') for w in words)
    provenance = json.loads((B / 'vendor-sequence-provenance.json').read_text())
    assert list(data) == provenance['bytes'] and len(data) == 84
    return code, bindings


def run_code(code, output):
    assert not output.exists()
    output.mkdir()
    (output / 'compiler-temporary').mkdir()
    (output / 'model.c').write_text(code)
    env = os.environ | {'TMPDIR':str(output.resolve() / 'compiler-temporary'),
        'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1', 'UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
    env.pop('LSAN_OPTIONS', None)
    r = subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror',
        '-Wno-unused-parameter','-Wno-unused-function','-fsanitize=address,undefined',
        '-fno-sanitize-recover=all','-fno-omit-frame-pointer',str(output / 'model.c'),'-o',str(output / 'model')],
        env=env,capture_output=True,text=True,timeout=60)
    (output / 'build.log').write_text(r.stdout+r.stderr)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([str(output / 'model')],env=env,capture_output=True,text=True,timeout=120)
    (output / 'run.stdout').write_text(r.stdout)
    (output / 'run.stderr').write_text(r.stderr)
    assert r.returncode == 0, r.stderr
    assert not any(s in r.stderr for s in ['AddressSanitizer','LeakSanitizer','runtime error:'])
    return json.loads(r.stdout)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    p.add_argument('output',type=Path)
    a = p.parse_args()
    code, bindings = model(a.source)
    result = run_code(code, a.output)
    result.update(actual_functions=bindings, all_actual_function_bodies_byte_exact=True,
        source_model_SHA256=hashlib.sha256(code.encode()).hexdigest(),
        normal_LSan_and_failfast_ASan_UBSan=True,
        only_synthetic_MMIO_regmap_context_devres_and_syscon_services=True,
        all_four_vendor_programs_and_END_padding_byte_verified=True,
        firmware_electrical_behavior_and_real_kernel_concurrency_qualified=False,
        full_CPU_APC_RPM_MPM_system_entry_qualified=False,
        no_phone_radio_network_audio_or_firmware_execution=True)
    (a.output / 'qualification.json').write_text(json.dumps(result,indent=2)+'\n')
    assert result['failures'] == 0, result
    print(json.dumps({k:result[k] for k in ['cases','checks','failures']}))
