#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Execute complete LK SPMI transfers against delayed/faulted fake MMIO."""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path)
args = parser.parse_args()
source = args.source.resolve()
test = r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
static uint32_t readl(uintptr_t address);
static void writel(uint32_t value, uintptr_t address);
static void udelay(unsigned int usecs);
static unsigned int platform_get_max_periph(void) {return 0;}
static void mask_interrupt(unsigned int irq) {assert(irq==17);}
#include "IMPLEMENTATION"
static unsigned int polls, delays, ready_after, status, data_reads;
static struct {uintptr_t address;uint32_t value;} writes[16];
static unsigned int nwrites;
static bool reading;
static uint8_t channels[4096];
static uint32_t readl(uintptr_t address)
{
 uintptr_t expected=PMIC_ARB_CHNLn_STATUS(pmic_arb_chnl_num);
#if SPMI_CORE_V2
 if(reading)expected=PMIC_ARB_OBS_CHNLn_STATUS(pmic_arb_chnl_num);
#endif
 if(address==expected) {polls++;return polls>ready_after?status:0;}
 assert(reading);data_reads++;
#if SPMI_CORE_V2
 assert(address==PMIC_ARB_OBS_CHNLn_RDATA(pmic_arb_chnl_num,0) || address==PMIC_ARB_OBS_CHNLn_RDATA(pmic_arb_chnl_num,1));
 return address==PMIC_ARB_OBS_CHNLn_RDATA(pmic_arb_chnl_num,0)?0x04030201:0x08070605;
#else
 assert(address==PMIC_ARB_CHNLn_RDATA(pmic_arb_chnl_num,0) || address==PMIC_ARB_CHNLn_RDATA(pmic_arb_chnl_num,1));
 return address==PMIC_ARB_CHNLn_RDATA(pmic_arb_chnl_num,0)?0x04030201:0x08070605;
#endif
}
static void writel(uint32_t value, uintptr_t address)
{assert(nwrites<16);writes[nwrites].address=address;writes[nwrites++].value=value;}
static void udelay(unsigned int usecs) {assert(usecs==1);delays++;}
int main(void)
{
 unsigned int count=0;
 const unsigned int pending[]={0,1,5,998,999,1000,1001,1000000};
 const unsigned int states[]={1,3,5,9};
 for(unsigned int revision=0;revision<2;revision++)
 for(unsigned int direction=0;direction<2;direction++)
 for(unsigned int size=1;size<=8;size++)
 for(unsigned int p=0;p<sizeof(pending)/sizeof(pending[0]);p++)
 for(unsigned int s=0;s<sizeof(states)/sizeof(states[0]);s++) {
  polls=delays=data_reads=nwrites=0;ready_after=pending[p];status=states[s];reading=direction;
  memset(channels,0,sizeof(channels));channels[CHNL_IDX(2,0x10)]=7;chnl_tbl=channels;
  pmic_arb_ver=revision?PMIC_ARB_V2:0;pmic_arb_chnl_num=4;
  uint8_t data[8],original[8];for(unsigned int i=0;i<8;i++)data[i]=0xa0+i;
  memcpy(original,data,8);
  struct pmic_arb_cmd cmd={.slave_id=2,.address=0x10,.offset=0x49,.priority=0};
  struct pmic_arb_param param={.buffer=data,.size=size};
  unsigned int ret=reading?pmic_arb_read_cmd(&cmd,&param):pmic_arb_write_cmd(&cmd,&param);
  assert(pmic_arb_chnl_num==(revision?7:4));
  assert(polls==(ready_after<1000?ready_after+1:1000));
  assert(delays==(ready_after<1000?ready_after:1000));
  assert(ret==(ready_after>=1000?BIT(PMIC_ARB_CMD_FAILURE):status^BIT(PMIC_ARB_CMD_DONE)));
  if(reading && !ret) {
   for(unsigned int i=0;i<size;i++)assert(data[i]==i+1);
   for(unsigned int i=size;i<8;i++)assert(data[i]==original[i]);
   assert(data_reads==(size>4?2:1));
  } else {assert(!memcmp(data,original,8));assert(!data_reads);}
  if(!reading) {
   assert(writes[1].address==PMIC_ARB_CHNLn_WDATA(pmic_arb_chnl_num,0));
   uint32_t expected=0;for(unsigned int i=0;i<size && i<4;i++)expected|=(uint32_t)original[i]<<(8*i);
   assert(writes[1].value==expected);
  }
  count++;
 }
 printf("PASS: %u complete SPMI transfer/delay/error cases, coreV2=%u\n",count,CORE_V2);
}
'''
with tempfile.TemporaryDirectory(prefix='fx0-spmi-timeout-') as directory:
    root = Path(directory)
    headers = {
        'debug.h': '#define dprintf(...) ((void)0)\n#define ASSERT(x) assert(x)\n',
        'reg.h': '', 'bits.h': '#define BIT(n) (1U<<(n))\n', 'platform.h': '',
        'platform/irqs.h': '#define EE0_KRAIT_HLOS_SPMI_PERIPH_IRQ 17\n',
        'platform/interrupts.h': '', 'platform/timer.h': '',
        'platform/iomap.h': '#define SPMI_BASE 0x01000000\n#define SPMI_PIC_BASE 0x02000000\n#define SPMI_GENI_BASE 0x03000000\n#define PMIC_ARB_CORE 0x04000000\n',
    }
    for name, text in headers.items():
        path = root/name
        path.parent.mkdir(exist_ok=True)
        path.write_text(text)
    (root/'check.c').write_text(test.replace('IMPLEMENTATION', str(source/'platform/msm_shared/spmi.c')))
    for version in [0, 1]:
        command = ['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                   '-Wno-sign-compare', '-Wno-unused-variable', '-Wno-unused-but-set-variable',
                   '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                   '-I', str(root), '-I', str(source/'platform/msm_shared/include'),
                   '-DCORE_V2='+str(version)]
        if version:
            command.append('-DSPMI_CORE_V2=1')
        binary = root/('check-'+str(version))
        subprocess.run([*command, str(root/'check.c'), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True, timeout=10)
