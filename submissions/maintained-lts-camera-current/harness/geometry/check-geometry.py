# SPDX-License-Identifier: GPL-2.0-only
"""Run extracted current VFE code with actual pinned vendor geometry reference."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import os

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path)
parser.add_argument('vendor', type=Path)
parser.add_argument('output', type=Path)
parser.add_argument('--mutation', choices=['no-hook', 'height', 'wm-index', 'no-bounds', 'no-limit', 'no-propagation'])
args = parser.parse_args()
base = Path(__file__).resolve().parent
args.output.mkdir(mode=0o700)
sha = lambda b: hashlib.sha256(b).hexdigest()
source_hashes = {}


def read(root, path):
    b = (root / path).read_bytes()
    source_hashes[('vendor/' if root == args.vendor else 'current/') + path] = sha(b)
    return b.decode()


def function(text, name):
    match = re.search(r'^(?:static[^\n]*|int|void|u32|u16)\s+' + name + r'\(', text, re.M)
    assert match, name
    return text[match.start():text.index('\n}', match.start()) + 2] + '\n'


prefix = 'drivers/media/platform/qcom/camss/'
gen = read(args.source, prefix + 'camss-vfe-gen1.c')
hw = read(args.source, prefix + 'camss-vfe-4-1.c')
header = read(args.source, prefix + 'camss-vfe-gen1.h')
core = read(args.source, prefix + 'camss-vfe.c')
video = read(args.source, prefix + 'camss-video.c')
video_header = read(args.source, prefix + 'camss-video.h')
vendor_hw = read(args.vendor, 'drivers/media/platform/msm/camera_v2/isp/msm_isp40.c')
vendor_util = read(args.vendor, 'drivers/media/platform/msm/camera_v2/isp/msm_isp_util.c')
vendor_header = read(args.vendor, 'include/media/msmb_isp.h')
ops = re.search(r'struct vfe_hw_ops_gen1 \{.*?\n\};', header, re.S).group()
has_geometry = '(*wm_frame_size)' in ops
pieces = [ops]
for line in hw.splitlines():
    if line.startswith('#define VFE_0_BUS_IMAGE_MASTER_n_WR_CFG') or line.startswith('#define VFE_0_BUS_IMAGE_MASTER_n_WR_BUFFER_CFG') or line.startswith('#define VFE_WM_BUFFER_CFG_'):
        pieces.append(line)
for line in vendor_hw.splitlines():
    if line.startswith('#define VFE40_BURST_LEN ') or line.startswith('#define VFE40_WM_BASE('): pieces.append(line)
for line in vendor_util.splitlines():
    if line.startswith('#define CAL_WORD('): pieces.append(line)
for line in vendor_header.splitlines():
    match = re.match(r'#define (V4L2_PIX_FMT_(?:Q\w+|META|NV14|NV41))\s', line)
    if match: pieces.append('#ifndef ' + match[1] + '\n' + line + '\n#endif')
pieces += [function(vendor_util, 'msm_isp_cal_word_per_line'), function(vendor_hw, 'msm_vfe40_axi_cfg_wm_reg')]
for name in ['vfe_reg_clr', 'vfe_reg_set', 'vfe_wm_enable', 'vfe_wm_frame_based']:
    pieces.append(function(hw, name))
if has_geometry:
    geometry = function(hw, 'vfe_wm_frame_size')
    assert re.search(r'\.wm_frame_size\s*=\s*vfe_wm_frame_size\b', hw)
    if args.mutation == 'height':
        assert '(pix->height - 1) << 4' in geometry
        geometry = geometry.replace('(pix->height - 1) << 4', 'pix->height << 4')
    if args.mutation == 'wm-index':
        assert 'VFE_0_BUS_IMAGE_MASTER_n_WR_BUFFER_CFG(wm)' in geometry
        geometry = geometry.replace('VFE_0_BUS_IMAGE_MASTER_n_WR_BUFFER_CFG(wm)', 'VFE_0_BUS_IMAGE_MASTER_n_WR_BUFFER_CFG((void)wm, 0)')
        geometry = geometry.replace('WR_BUFFER_CFG((void)wm, 0)', 'WR_BUFFER_CFG(((void)wm, 0))')
    if args.mutation == 'no-bounds':
        start = geometry.index('\tif (')
        end = geometry.index('\n', geometry.index('return -EINVAL;', start))
        geometry = geometry[:start] + geometry[end + 1:]
    pieces.append(geometry)
actual = {'wm_enable': 'vfe_wm_enable', 'wm_frame_based': 'vfe_wm_frame_based'}
if has_geometry: actual['wm_frame_size'] = 'vfe_wm_frame_size'
initializers = []
for result_type, name, parameters in re.findall(r'\b(void|int|u16)\s+\(\*(\w+)\)\((.*?)\);', ops, re.S):
    if name in actual:
        initializers.append('.' + name + ' = ' + actual[name])
        continue
    names = [re.search(r'(\w+)\s*$', param.strip()).group(1) for param in parameters.split(',')]
    body = ''.join('(void)' + n + '; ' for n in names)
    body += 'event("' + name + '", ' + ('wm' if 'wm' in names else '0') + ', ' + ('addr' if 'addr' in names else '0') + '); '
    if result_type != 'void': body += 'return ' + ('model_ub_size' if name == 'get_ub_size' else '0') + ';'
    pieces.append('static ' + result_type + ' model_' + name + '(' + parameters + ') { ' + body + ' }')
    initializers.append('.' + name + ' = model_' + name)
has_limit = 'max_frame_height;' in ops
if has_limit:
    limit = re.search(r'\.max_frame_height\s*=\s*([^,\n]+)', hw)
    assert limit and 'unsigned int max_height;' in video_header
    initializers.append('.max_frame_height = ' + ('0' if args.mutation == 'no-limit' else limit[1]))
pieces.append('static const struct vfe_hw_ops_gen1 qualified_ops = { ' + ', '.join(initializers) + ' };')
for name in ['vfe_output_init_addrs', 'vfe_output_frame_drop', 'vfe_enable_output']:
    if name == 'vfe_output_init_addrs':
        # The unchanged upstream helper has an unused line parameter. Native
        # kernel builds do not enable this host-only -Wextra diagnostic.
        pieces.append('#pragma clang diagnostic push\n#pragma clang diagnostic ignored "-Wunused-parameter"')
    pieces.append(function(gen, name))
    if name == 'vfe_output_init_addrs':
        pieces.append('#pragma clang diagnostic pop')
pieces.append('#define HAS_GEOMETRY ' + str(int(has_geometry)))
pieces.append('#define MUTANT_NO_HOOK ' + str(int(args.mutation == 'no-hook')))
pieces.append('#define HAS_HEIGHT_LIMIT ' + str(int(has_limit)))
for line in video.splitlines():
    if line.startswith('#define CAMSS_FRAME_'): pieces.append(line)
pieces.append(function(core, 'vfe_try_format'))
pieces.append('#pragma clang diagnostic push\n#pragma clang diagnostic ignored "-Wunused-parameter"')
pieces.append(function(video, 'video_enum_framesizes'))
pieces.append('#pragma clang diagnostic pop')
pieces.append(function(video, '__video_try_fmt'))
assignment = re.search(r'video_out->max_height =.*?;', core, re.S)
pieces.append('static void register_rdi_limit(struct vfe_device *vfe, struct camss_video *video_out) { (void)vfe; (void)video_out; ' + (assignment.group() if assignment and args.mutation != 'no-propagation' else '') + ' }')
body = '\n'.join(pieces) + '\n'
(args.output / 'actual-functions.c').write_text(body)
program = (base / 'model-head.c').read_text() + '\n' + body + '\n' + (base / 'model-tail.c').read_text()
(args.output / 'model.c').write_text(program)
command = ['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
           '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
           str(args.output / 'model.c'), '-o', str(args.output / 'model')]
compiled = subprocess.run(command, capture_output=True, text=True)
(args.output / 'compile.stdout').write_text(compiled.stdout)
(args.output / 'compile.stderr').write_text(compiled.stderr)
assert compiled.returncode == 0, compiled.stderr
(args.output / 'tmp').mkdir(mode=0o700)
run = subprocess.run([str(args.output / 'model')], capture_output=True, text=True,
                     env=os.environ | {'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1',
                                       'UBSAN_OPTIONS':'halt_on_error=1',
                                       'TMPDIR':str(args.output / 'tmp')})
(args.output / 'run.stdout').write_text(run.stdout)
(args.output / 'run.stderr').write_text(run.stderr)
result = json.loads(run.stdout.splitlines()[-1]) if run.stdout else {}
result.update(returncode=run.returncode, mutation=args.mutation, source_files=source_hashes,
              launcher_SHA256=sha(Path(__file__).read_bytes()), program_SHA256=sha(program.encode()),
              body_SHA256=sha(body.encode()), sanitizer_diagnostics=bool(run.stderr),
              full_pipeline_and_physical_capture=False, core_services_and_other_ops_mocked=True)
result['unchanged_init_addrs_unused_parameter_diagnostic_scoped'] = True
result['registration_limit_assignment_only_not_full_registration'] = True
result['inherited_enum_framesizes_unused_fh_parameter_diagnostic_scoped'] = True
(args.output / 'qualification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
assert not run.stderr, run.stderr
assert run.returncode in [0, 1]
