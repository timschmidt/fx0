# SPDX-License-Identifier: GPL-2.0-only
"""Pin two shared-platform regressions in the exact LTS SPM catalogue/probe."""
from pathlib import Path
import hashlib,importlib.util,json,sys
sys.dont_write_bytecode=True
B=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('spm_model',B/'check-model.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
S=Path(sys.argv[1]);O=Path(sys.argv[2]);O.mkdir()
code,bindings=m.model(S)
code=code.replace('int main(void)\n{','int main(void)\n{\n    EXPECT(spm_reg_660_silver_l2.avs_ctl==0x1010031);',1)
anchor='        if(master_node) EXPECT(l2_calls==1&&!regulator_calls);'
assert code.count(anchor)==1
code=code.replace(anchor,'        EXPECT(seq_copies==(!master_node && ((const struct spm_reg_data *)p->data)->reg_offset[SPM_REG_SEQ_ENTRY]!=0));\n'+anchor)
positive=m.m.run_code(code,O/'positive');assert not positive['failures']
table=m.m.block(code,r'^static const struct spm_reg_data spm_reg_660_silver_l2  = \{')
assert table.count('0x1010031')==1
condition='if (drv->reg_data->reg_offset[SPM_REG_SEQ_ENTRY]) {'
assert code.count(condition)==1
variants=[('silver-L2-AVS-before',code.replace(table,table.replace('0x1010031','0x101c031')),'spm_reg_660_silver_l2.avs_ctl==0x1010031'),('zero-sequence-offset-before',code.replace(condition,'if (true) {'),'seq_copies==')]
rows=[]
for name,mutated,assertion in variants:
 r=m.m.run_code(mutated,O/name);assert r['failures']>0 and assertion in (O/name/'run.stderr').read_text()
 rows.append(dict(name=name,failures=r['failures'],rejected_by_intended_assertion=True))
report=dict(passed=True,positive=positive,controls=rows,actual_functions_and_tables=bindings,source_model_SHA256=hashlib.sha256(code.encode()).hexdigest(),all_services_synthetic=True,hardware_acceptance=False,normal_LSan_and_failfast_ASan_UBSan=True)
(O/'qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=positive['cases'],controls_rejected=len(rows))))
