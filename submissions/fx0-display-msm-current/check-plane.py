# SPDX-License-Identifier: GPL-2.0-only
"""Execute actual MDP5 ownership paths, with explicitly modeled core services."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

p = argparse.ArgumentParser()
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
p.add_argument('--mutation', choices=['left-only', 'ignore-error', 'drop-owned', 'right-old-only', 'right-new-only'])
args = p.parse_args()
base = Path(__file__).resolve().parent
args.output.mkdir(mode=0o700)
hashes = {}


def read(name):
    f = args.source/'drivers/gpu/drm/msm/disp'/name
    hashes[name] = hashlib.sha256(f.read_bytes()).hexdigest()
    return f.read_text()


def function(text, name):
    m = re.search(r'^(?=[A-Za-z_])[^\n]*?\b' + name + r'\(', text, re.M)
    assert m, name
    start = m.start()
    if text[start:].startswith(name):
        previous = text[:start].rstrip('\n').rsplit('\n', 1)[-1]
        assert previous.endswith('*'), (name, previous)
        start -= len(previous) + 1
    return text[start:text.index('\n}', m.start()) + 2] + '\n'


plane, kms, pipe, header, common = [read(n) for n in [
    'mdp5/mdp5_plane.c', 'mdp5/mdp5_kms.c', 'mdp5/mdp5_pipe.c',
    'mdp5/mdp5_pipe.h', 'mdp_kms.h']]
definitions = '\n'.join(line for line in common.splitlines()
                        if line.startswith('#define MDP_PIPE_CAP_') or
                        line.startswith('#define MDP_CAP_'))
# This model uses pipe type values from the generated source XML headers.
# Generate only the enum declaration, not the encoder fixture's support code.
generated = (base/'generated/mdp5.xml.h').read_text()
enum = re.search(r'enum mdp5_pipe \{.*?\n\};', generated, re.S).group()
types = header[header.index('struct mdp5_hw_pipe {'):header.index('int mdp5_pipe_assign')]
if args.mutation == 'right-old-only':
    pipe = pipe.replace('if (new_state->hwpipe_to_plane[r_cur->idx] ||\n\t\t\t\t\t    old_state->hwpipe_to_plane[r_cur->idx])',
                        'if (old_state->hwpipe_to_plane[r_cur->idx])')
elif args.mutation == 'right-new-only':
    pipe = pipe.replace('if (new_state->hwpipe_to_plane[r_cur->idx] ||\n\t\t\t\t\t    old_state->hwpipe_to_plane[r_cur->idx])',
                        'if (new_state->hwpipe_to_plane[r_cur->idx])')
pieces = [function(plane, 'get_kms'), function(plane, 'plane_enabled'),
          function(kms, 'mdp5_global_duplicate_state'),
          function(kms, 'mdp5_get_existing_global_state'), function(kms, 'mdp5_get_global_state'),
          function(pipe, 'mdp5_pipe_assign'), function(pipe, 'mdp5_pipe_release'),
          function(plane, 'mdp5_plane_duplicate_state')]
if 'static int mdp5_plane_drop_stale_hwpipes(' in plane:
    helper = function(plane, 'mdp5_plane_drop_stale_hwpipes')
    if args.mutation == 'left-only':
        helper = helper.replace('if (mdp5_state->r_hwpipe &&', 'if (false && mdp5_state->r_hwpipe &&')
    elif args.mutation == 'ignore-error':
        helper = helper.replace('return PTR_ERR(global_state);', 'return 0;')
    elif args.mutation == 'drop-owned':
        helper = helper.replace('!= state->plane', '== state->plane')
    pieces.append(helper)
else:
    assert args.mutation is None
pieces.append(function(plane, 'mdp5_plane_atomic_check_with_state'))
body = '\n'.join(pieces)
head = (base/'plane-head.c').read_text()
# The actual pipe header types require only forward declarations and the enum.
insert = '#define to_mdp5_mocks_unused /* no source transformation */'
head = head.replace(insert, enum+'\n'+definitions+'\n#define SSPP_MAX (SSPP_CURSOR1 + 1)\nstruct drm_plane;\n'+types)
program = head+'\n'+body+'\n'+(base/'plane-tail.c').read_text()
(args.output/'actual-functions.c').write_text(body)
(args.output/'model.c').write_text(program)
command = ['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
           '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
           str(args.output/'model.c'), '-o', str(args.output/'model')]
compiled = subprocess.run(command, capture_output=True, text=True)
(args.output/'compile.stderr').write_text(compiled.stderr)
assert compiled.returncode == 0, compiled.stderr
run = subprocess.run([str(args.output/'model')], capture_output=True, text=True)
(args.output/'run.stdout').write_text(run.stdout)
(args.output/'run.stderr').write_text(run.stderr)
result = json.loads(run.stdout.splitlines()[-1]) if run.stdout else {}
result.update(returncode=run.returncode, source_files=hashes,
              body_SHA256=hashlib.sha256(body.encode()).hexdigest(),
              program_SHA256=hashlib.sha256(program.encode()).hexdigest(), mutation=args.mutation,
              core_private_state_lock_PM_and_SMP_services_modeled=True,
              full_DRM_IOCTL_registration_concurrency_or_physical_resume_not_qualified=True,
              sanitizer_diagnostics=bool(run.stderr))
(args.output/'qualification.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
assert not run.stderr, run.stderr
assert run.returncode in [0, 1]
