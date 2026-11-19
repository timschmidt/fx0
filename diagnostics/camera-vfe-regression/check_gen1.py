#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compile actual gen1 functions/dispatchers with host-only hardware endpoints."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

CASES = ['empty0','empty1','pending1_0','pending1_1','pending2_0','pending2_1',
         'pix_empty','pix_pending1','pix_pending2','pix_comp_only','pix_wm_only',
         'reg_only','queue_after_ack','old_ack','continuous','pix_continuous',
         'missing_active','unexpected_idle','unmapped','late_unexpected',
         'wait_ack','gen2_wait_ack','two_drains','unrelated_active',
         'no_last_pending','pix_no_last','reassigned_wm','pix_unrelated_active']
STOPPING_CASES = ['stopping_handoff','rdi_stopping_phase0','rdi_stopping_phase1',
                  'pix_stopping_phase0','pix_stopping_phase1']
SOF_CASES = ['rdi_sof_rearm','rdi_sof_coalesced','rdi_sof_drain','rdi_sof_unsupported','pix_sof_unchanged']
VERSIONS = ['4-1','4-7','4-8']
GEN1 = ['vfe_output_init_addrs','vfe_output_frame_drop','vfe_output_update_ping_addr',
        'vfe_output_update_pong_addr','vfe_buf_update_wm_on_next','vfe_buf_update_wm_on_last',
        'vfe_buf_update_wm_on_new','vfe_isr_halt_ack','vfe_isr_sof','vfe_isr_reg_update','vfe_isr_wm_done']
SHARED = ['vfe_buf_get_pending','vfe_buf_add_pending','vfe_isr_comp_done','vfe_isr_reset_ack']


def balanced(text, opening):
    depth = 0; state = 'code'; i = opening
    while i < len(text):
        char, nxt = text[i], text[i:i+2]
        if state == 'line':
            if char == '\n': state = 'code'
        elif state == 'comment':
            if nxt == '*/': state = 'code'; i += 1
        elif state in ['string','char']:
            if char == '\\': i += 1
            elif char == ('"' if state == 'string' else "'"): state = 'code'
        elif nxt == '//': state = 'line'; i += 1
        elif nxt == '/*': state = 'comment'; i += 1
        elif char == '"': state = 'string'
        elif char == "'": state = 'char'
        elif char == '{': depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0: return i + 1
        i += 1
    raise ValueError('unbalanced source block')


def function(text, name):
    pattern = r'(?m)^(?:static\s+)?(?:irqreturn_t|u32|void|int|struct camss_buffer\s*\*)\s*' + re.escape(name) + r'\s*\('
    for match in re.finditer(pattern, text):
        opening = text.find('{', match.start())
        semi = text.find(';', match.start())
        if opening >= 0 and (semi < 0 or opening < semi):
            return text[match.start():balanced(text, opening)]
    raise ValueError('function not found: ' + name)


def block(text, kind, name):
    match = re.search(r'(?m)^' + kind + r' ' + name + r'\s*\{', text)
    if match is None: raise ValueError('type not found: ' + name)
    end = balanced(text, text.index('{', match.start()))
    return text[match.start():end] + ';'


def defines(text, predicate):
    lines = text.splitlines(); output = []; i = 0
    while i < len(lines):
        match = re.match(r'^#define\s+(\w+)', lines[i])
        if match and predicate(match[1]):
            item = [lines[i]]
            while item[-1].endswith('\\'):
                i += 1; item.append(lines[i])
            output.append('\n'.join(item))
        i += 1
    return '\n'.join(output)


def generate(tree, version, mutation):
    base = tree / 'drivers/media/platform/qcom/camss'
    paths = [base/'camss-vfe.h', base/'camss-vfe.c', base/'camss-vfe-gen1.c',
             base/'camss-vfe-17x.c', base/('camss-vfe-'+version+'.c')]
    header, shared, gen1, gen2, dispatch = [path.read_text() for path in paths]
    types = defines(header, lambda n: n in ['MSM_VFE_IMAGE_MASTERS_NUM','MSM_VFE_COMPOSITE_IRQ_NUM','VFE_FRAME_DROP_VAL'])
    types += '\n' + '\n'.join(block(header,kind,name) for kind,name in
                               [('enum','vfe_output_state'),('enum','vfe_line_id'),('struct','vfe_output'),('struct','vfe_isr_ops')])
    returns_mask = 'u32 (*reg_update)' in block(header,'struct','vfe_isr_ops')
    pieces = [defines(gen1,lambda n:n=='VFE_FRAME_DROP_UPDATES'),
              defines(dispatch,lambda n:n.startswith('VFE_0_IRQ_STATUS_') or n=='VFE_0_IRQ_MASK_0_IMAGE_MASTER_n_PING_PONG')]
    pieces.extend(function(shared,name) for name in SHARED)
    for name in GEN1:
        body = function(gen1,name)
        if mutation == 'idle-guard' and name == 'vfe_isr_wm_done':
            needle = '\toutput = &vfe->line[vfe->wm_output_map[wm]].output;'
            assert body.count(needle)==1
            body=body.replace(needle,needle+'\n\tif (output->state == VFE_OUTPUT_IDLE)\n\t\tgoto out_unlock;')
        pieces.append(body)
    match = re.search(r'(?m)^const struct vfe_isr_ops vfe_isr_ops_gen1\s*=\s*\{',gen1);assert match
    pieces.append(gen1[match.start():balanced(gen1,gen1.index('{',match.start()))]+';')
    pieces.extend(['#define vfe_isr_reg_update vfe17x_isr_reg_update',function(gen2,'vfe_isr_reg_update'),'#undef vfe_isr_reg_update'])
    irq = function(dispatch,'vfe_isr')
    if mutation == 'irq-reorder':
        start=irq.index('\tfor (i = VFE_LINE_RDI0;');end=irq.index('\n\tif (value0 & VFE_0_IRQ_STATUS_0_CAMIF_SOF)',start)
        reg=irq[start:end];irq=irq[:start]+irq[end:]
        irq=irq.replace('\treturn IRQ_HANDLED;',reg+'\n\treturn IRQ_HANDLED;')
    elif mutation == 'drop-all-coalesced':
        needle='\tfor (i = 0; i < MSM_VFE_IMAGE_MASTERS_NUM; i++)'
        assert irq.count(needle)==1
        irq=irq.replace(needle,'\tif (value0 & (BIT(4) | BIT(5) | BIT(6) | BIT(7)))\n\t\tvalue0 &= ~(0x7fU << 8);\n'+needle)
    pieces.append(irq)
    manifest={'files_SHA256':{path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
              'gen1_functions':GEN1,'shared_functions':SHARED,'dispatcher':'camss-vfe-'+version+'.c',
              'reg_update_returns_mask':returns_mask,'synthetic_mutation':mutation}
    return types, '\n\n'.join(pieces), manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel-tree',type=Path,required=True)
    parser.add_argument('--baseline-tree',type=Path,required=True)
    parser.add_argument('--stopping-baseline-tree',type=Path,
                        help='enable the pre-ack STOPPING cases and use this pre-fix tree as their control')
    parser.add_argument('--sof-baseline-tree',type=Path,
                        help='enable start-of-frame rearm cases and use this pre-change tree as their control')
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--cc',default='clang-21')
    parser.add_argument('--sanitize',action='store_true')
    args=parser.parse_args();os.umask(0o077)
    root=args.output_dir.resolve();root.mkdir(mode=0o700)
    here=Path(__file__).resolve().parent
    report={'scope':'host C bookkeeping regression; fake MMIO/locking/IRQ inputs, not hardware or concurrency qualification',
            'candidate':str(args.kernel_tree.resolve()),'baseline':str(args.baseline_tree.resolve()),
            'harness_SHA256':{name:hashlib.sha256((here/name).read_bytes()).hexdigest() for name in ['check_gen1.py','shim.h','cases.c']},
            'sanitize':args.sanitize,'compiler':subprocess.check_output([args.cc,'--version'],text=True).splitlines()[0],
            'positive':[],'negative':[],'builds':[]}
    def save(): (root/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    def build(tree,version,mutation,label):
        work=root/(label+'-'+version);work.mkdir(mode=0o700)
        types,code,manifest=generate(tree,version,mutation)
        (work/'kernel-types.h').write_text(types+'\n');shutil.copyfile(here/'shim.h',work/'shim.h')
        source='#include "shim.h"\n'+code+'\n'+(here/'cases.c').read_text();(work/'test.c').write_text(source)
        (work/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        command=[args.cc,'-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter',
                 '-Wno-unused-function','-Wno-sign-compare','-DREG_RETURNS_MASK='+str(int(manifest['reg_update_returns_mask']))]
        if args.sanitize:command+=['-fsanitize=address,undefined','-fno-omit-frame-pointer']
        command += [str(work/'test.c'),'-o',str(work/'test')]
        done=subprocess.run(command,capture_output=True,text=True,timeout=45)
        (work/'compile.stdout').write_text(done.stdout);(work/'compile.stderr').write_text(done.stderr)
        report['builds'].append({'label':label,'version':version,'manifest':manifest,'command':command,'returncode':done.returncode});save()
        if done.returncode:raise RuntimeError('compile failed: '+str(work/'compile.stderr'))
        return work/'test'
    def run(binary,case,expect=None):
        done=subprocess.run([str(binary),case],capture_output=True,text=True,timeout=5)
        if expect is None:
            assert done.returncode==0 and done.stdout.strip()=='PASS:'+case,(binary,case,done.returncode,done.stdout,done.stderr)
            report['positive'].append({'version':binary.parent.name,'case':case,'passed':True})
        else:
            assert done.returncode==2 and done.stderr.strip() in ['FAIL:'+value for value in expect],(binary,case,done.returncode,done.stdout,done.stderr)
            report['negative'].append({'version':binary.parent.name,'case':case,'expected_failure_observed':done.stderr.strip()})
        save()
    cases = CASES + STOPPING_CASES if args.stopping_baseline_tree else CASES
    if args.sof_baseline_tree:
        cases = cases + SOF_CASES
    for version in VERSIONS:
        candidate=build(args.kernel_tree,version,None,'candidate')
        for case in cases:run(candidate,case)
        baseline=build(args.baseline_tree,version,None,'baseline')
        run(baseline,'empty0',['STALE_DIAGNOSTIC'])
        run(baseline,'pending2_1',['NEW_BUFFER_TOUCHED'])
        guarded=build(args.baseline_tree,version,'idle-guard','idle-guard')
        run(guarded,'pending1_1',['NEW_BUFFER_TOUCHED'])
        reordered=build(args.kernel_tree,version,'irq-reorder','irq-reorder')
        run(reordered,'old_ack',['ACK_BEFORE_RETURN'])
        dropped=build(args.kernel_tree,version,'drop-all-coalesced','drop-all-coalesced')
        run(dropped,'continuous',['NORMAL_COMPLETION_LOST'])
        if args.stopping_baseline_tree:
            before=build(args.stopping_baseline_tree,version,None,'stopping-baseline')
            run(before,STOPPING_CASES[0],['STOPPING_OWNER_AT_UNLOCK'])
            for case in STOPPING_CASES[1:]:run(before,case,['STOPPING_STRAY_DIAGNOSTIC'])
        if args.sof_baseline_tree:
            before=build(args.sof_baseline_tree,version,None,'sof-baseline')
            run(before,'rdi_sof_rearm',['REARMED_BEFORE_RDI_SOF'])
    report.update(passed=True,positive_scenarios=len(cases),positive_dispatcher_cases=len(report['positive']),
                  negative_controls=len(report['negative']),phone_access=False)
    save();print(json.dumps({key:report[key] for key in ['passed','positive_scenarios','positive_dispatcher_cases','negative_controls','sanitize','phone_access']}))


if __name__=='__main__':main()
