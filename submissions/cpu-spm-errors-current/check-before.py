# SPDX-License-Identifier: GPL-2.0-only
"""Observe the actual parent's unbounded write under a logical watchdog."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('support', B / 'model-support.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source',type=Path)
p.add_argument('output',type=Path)
a = p.parse_args()
driver = (a.source/'drivers/soc/qcom/spm.c').read_text()
body = m.function(driver,'spm_register_write_sync')
assert body.startswith('static inline void') and '} while (1);' in body
code = '''#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <setjmp.h>
typedef uint32_t u32;
typedef uint16_t u16;
static jmp_buf watchdog;
static unsigned writes,reads,relaxes;
static bool returned;
'''
code += m.block(driver,r'^enum spm_reg \{')
code += m.block(driver,r'^static const u16 spm_reg_offset_v2_1\[SPM_REG_NR\] = \{')
code += '''struct spm_reg_data { const u16 *reg_offset; };
struct spm_driver_data { void *reg_base; const struct spm_reg_data *reg_data; };
static u32 bank[64];
static void writel_relaxed(u32 value,void *address)
{
    if(address!=(void *)((char *)bank+0x30)||value!=0x59) abort();
    if(++writes==101) longjmp(watchdog,1);
    /* Every write is dropped: logical MMIO only. */
}
static u32 readl_relaxed(const void *address)
{
    if(address!=(const void *)((char *)bank+0x30)) abort();
    ++reads; return 0x9;
}
static void cpu_relax(void) { ++relaxes; }
'''
code += body
code += '''int main(void)
{
    struct spm_reg_data data={.reg_offset=spm_reg_offset_v2_1};
    struct spm_driver_data driver={.reg_base=bank,.reg_data=&data};
    if(!setjmp(watchdog)) { spm_register_write_sync(&driver,SPM_REG_SPM_CTL,0x59); returned=true; }
    if(writes!=101||reads!=100||relaxes!=100||returned) abort();
    unsigned failures=(writes>50||!returned);
    printf("{\\"cases\\":1,\\"checks\\":1,\\"failures\\":%u}\\n",failures);
    return 0;
}
'''
report = m.run_code(code,a.output)
assert report==dict(cases=1,checks=1,failures=1)
report.update(actual_parent_function_SHA256=hashlib.sha256(body.encode()).hexdigest(),
    synthetic_watchdog_after_write_attempts=101,read_attempts=100,parent_function_had_not_returned=True,
    logical_watchdog_does_not_claim_function_returned_or_timed_out=True,
    normal_LSan_and_failfast_ASan_UBSan=True,all_MMIO_and_watchdog_services_synthetic=True,
    no_phone_network_radio_audio_or_firmware_execution=True)
(a.output/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['cases','checks','failures']}))
