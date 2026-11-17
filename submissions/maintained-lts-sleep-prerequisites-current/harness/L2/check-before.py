# SPDX-License-Identifier: GPL-2.0-only
"""Show the pinned L2 parent publishes arbitration without the new programs."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('l2_model', B / 'check-model.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
driver = (a.source / 'drivers/soc/qcom/spm.c').read_text()
header = (a.source / 'drivers/soc/qcom/spm-msm8226-l2.h').read_text()
table = json.loads((B / 'vendor-sequence-provenance.json').read_text())['bytes']
words = [int.from_bytes(bytes(table[i:i+4]), 'little') for i in range(0, len(table), 4)]
oracle = '\n/* Synthetic expected-program oracle; not a parent driver table. */\nstatic const u32 spm_8226_l2_sequence[] = {' + ','.join(hex(w) for w in words) + '};\n'
code = (B / 'model-services.c').read_text()
code = code.replace('/* ACTUAL_ENUM */', '')
code = code.replace('/* ACTUAL_HEADER */', re.sub(r'^#include[^\n]*\n', '', header, flags=re.M) + oracle)
tables = driver[driver.index('static const struct regmap_range spm_8226_l2_read_ranges'):
    driver.index('static int spm_8226_l2_register(')]
code = code.replace('/* ACTUAL_ACCESS_TABLES */', tables)
code = code.replace('/* ACTUAL_WRAPPER */', '')
registration = m.function(driver, 'spm_8226_l2_register')
code = code.replace('/* ACTUAL_REGISTER */', registration)
code += '''int main(void)
{
    (void)cases; (void)fatal_target; (void)ordinary;
    reset(); EXPECT(spm_8226_l2_register(&pdev,&driver)==0);
    EXPECT(published&&!control_writes&&!sequence_writes);
    preserved();
    printf("{\\"cases\\":1,\\"checks\\":%u,\\"failures\\":%u}\\n",checks,failures);
    return 0;
}
'''
result = m.run_code(code, a.output)
assert result['cases'] == 1 and result['failures'] == 21
result.update(actual_parent_master_init_SHA256=hashlib.sha256(m.function(header, 'spm_8226_l2_master_init').encode()).hexdigest(),
    actual_parent_registration_SHA256=hashlib.sha256(registration.encode()).hexdigest(),
    expected_program_table_is_synthetic_oracle_from_vendor=True,
    parent_unsupported_feature_not_claimed_as_generic_core_bug=True,
    full_new_feature_suite_not_claimed_on_parent=True,
    normal_LSan_and_failfast_ASan_UBSan=True, only_synthetic_services=True)
(a.output / 'qualification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({k:result[k] for k in ['cases','checks','failures']}))
