# SPDX-License-Identifier: GPL-2.0-only
"""Execute actual MDP5 CRTC/CTL/video paths with synthetic MMIO epochs."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

p = argparse.ArgumentParser()
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
p.add_argument('--mutation', choices=['late-flush', 'no-start'])
args = p.parse_args()
base = Path(__file__).resolve().parent
args.output.mkdir(mode=0o700)
hashes = {}


def read(name):
    f = args.source/'drivers/gpu/drm/msm/disp/mdp5'/name
    hashes[name] = hashlib.sha256(f.read_bytes()).hexdigest()
    return f.read_text()


def function(text, name):
    m = re.search(r'^[A-Za-z_][^\n]*\b' + name + r'\(', text, re.M)
    assert m, name
    start = m.start()
    if text[start:].startswith(name):
        previous = text[:start].rstrip('\n').rsplit('\n', 1)[-1]
        assert previous.endswith('*'), (name, previous)
        start -= len(previous) + 1
    return text[start:text.index('\n}', m.start()) + 2] + '\n'


encoder, ctl, crtc, header = [read(name) for name in ['mdp5_encoder.c', 'mdp5_ctl.c', 'mdp5_crtc.c', 'mdp5_kms.h']]
pieces = [function(encoder, 'get_kms'), function(header, 'intf2vblank')]
for name in ['start_signal_needed', 'send_start_signal', 'mdp5_ctl_set_encoder_state',
             'mdp_ctl_flush_mask_encoder', 'mdp_ctl_flush_mask_lm', 'fix_sw_flush', 'mdp5_ctl_commit']:
    pieces.append(function(ctl, name))
pieces += [function(crtc, 'mdp5_crtc_get_pipeline'), function(crtc, 'mdp5_crtc_get_mixer'), function(crtc, 'crtc_flush'),
           function(encoder, 'mdp5_vid_encoder_disable')]
enable = function(encoder, 'mdp5_vid_encoder_enable')
if args.mutation == 'late-flush':
    first = '\tmdp5_ctl_commit(ctl, pipeline, mdp_ctl_flush_mask_encoder(intf), true);\n'
    assert first in enable
    enable = enable.replace(first, '')
    where = '\tspin_unlock_irqrestore(&mdp5_encoder->intf_lock, flags);\n'
    enable = enable.replace(where, where + first)
if args.mutation == 'no-start':
    enable = enable.replace('mdp_ctl_flush_mask_encoder(intf), true)', 'mdp_ctl_flush_mask_encoder(intf), false)')
pieces += [enable, function(encoder, 'mdp5_encoder_disable'), function(encoder, 'mdp5_encoder_enable')]
body = '\n'.join(pieces)
(args.output/'actual-functions.c').write_text(body)
program = (base/'encoder-head.c').read_text()+'\n'+body+'\n'+(base/'encoder-tail.c').read_text()
(args.output/'model.c').write_text(program)
command = ['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
           '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-I'+str(base/'generated'),
           str(args.output/'model.c'), '-o', str(args.output/'model')]
c = subprocess.run(command, capture_output=True, text=True)
(args.output/'compile.stderr').write_text(c.stderr)
assert c.returncode == 0, c.stderr
run = subprocess.run([str(args.output/'model')], capture_output=True, text=True)
(args.output/'run.stdout').write_text(run.stdout)
(args.output/'run.stderr').write_text(run.stderr)
result = json.loads(run.stdout.splitlines()[-1]) if run.stdout else {}
result.update(returncode=run.returncode, source_files=hashes, body_SHA256=hashlib.sha256(body.encode()).hexdigest(),
              program_SHA256=hashlib.sha256(program.encode()).hexdigest(), mutation=args.mutation,
              MMIO_frame_epochs_and_modeset_services_mocked=True, command_operations_mocked=True,
              actual_scanout_underrun_or_original_r2_fault_not_proven_fixed=True, sanitizer_diagnostics=bool(run.stderr))
(args.output/'qualification.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
assert not run.stderr, run.stderr
assert run.returncode in [0, 1]
