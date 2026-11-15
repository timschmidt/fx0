# SPDX-License-Identifier: GPL-2.0-only
"""Extract real mapper/driver functions; execute with synthetic core services."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path)
parser.add_argument('output', type=Path)
parser.add_argument('--mutation', choices=['no-limit', 'no-guard', 'single-segment'])
parser.add_argument('--baseline-video', type=Path)
args = parser.parse_args()
base = Path(__file__).resolve().parent
args.output.mkdir(mode=0o700)
sha = lambda b: hashlib.sha256(b).hexdigest()
sources = {}
pieces = []


def extract(path, name):
    data = (args.source / path).read_bytes()
    sources[path] = sha(data)
    text = data.decode()
    start = re.search(r'^static[^\n]*\b' + name + r'\(', text, re.M)
    assert start, name
    end = text.index('\n}', start.start()) + 2
    return text[start.start():end] + '\n'


pieces.append(extract('drivers/base/platform.c', 'setup_pdev_dma_masks'))
for name in ['dma_get_max_seg_size', 'dma_set_max_seg_size']:
    pieces.append(extract('include/linux/dma-mapping.h', name))
for name in ['__map_sg_chunk', 'arm_iommu_map_sg']:
    pieces.append(extract('arch/arm/mm/dma-mapping.c', name))
video_path = 'drivers/media/platform/qcom/camss/camss-video.c'
init = extract(video_path, 'video_buf_init')
if args.mutation == 'no-guard':
    before = args.baseline_video.read_text() if args.baseline_video else subprocess.check_output(
        ['git', '-C', str(args.source), 'show',
         '48fe5a7834cc10081887d7bcd9ff0a4cadc3fa8c:' + video_path], text=True)
    match = re.search(r'^static int video_buf_init\(', before, re.M)
    assert match
    init = before[match.start():before.index('\n}', match.start()) + 2] + '\n'
if args.mutation == 'single-segment':
    needle = '\t\tbuffer->addr[i] = sg_dma_address(sgt->sgl);'
    assert needle in init
    init = init.replace(needle, '\t\tif (sgt->nents != 1)\n\t\t\treturn -EFAULT;\n' + needle)
probe = extract('drivers/media/platform/qcom/camss/camss.c', 'camss_probe')
statement = 'dma_set_max_seg_size(dev, UINT_MAX);'
has_limit = statement in probe
if has_limit:
    assert probe.index('dma_set_mask_and_coherent') < probe.index(statement) < probe.index('media_device_init')
if args.mutation == 'no-limit':
    has_limit = False
pieces.append('static void apply_probe_statement(struct device *dev)\n{\n\t' +
              (statement if has_limit else '(void)dev;') + '\n}\n')
pieces.extend([init, extract(video_path, 'video_buf_prepare')])
body = '\n'.join(pieces)
(args.output / 'actual-functions.c').write_text(body)
program = (base / 'model-head.c').read_text() + '\n' + body + '\n' + (base / 'model-tail.c').read_text()
(args.output / 'model.c').write_text(program)
command = ['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
           '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
           str(args.output / 'model.c'), '-o', str(args.output / 'model')]
compile_result = subprocess.run(command, capture_output=True, text=True)
(args.output / 'compile.stdout').write_text(compile_result.stdout)
(args.output / 'compile.stderr').write_text(compile_result.stderr)
assert compile_result.returncode == 0, compile_result.stderr
run = subprocess.run([str(args.output / 'model')], capture_output=True, text=True)
(args.output / 'run.stdout').write_text(run.stdout)
(args.output / 'run.stderr').write_text(run.stderr)
result = json.loads(run.stdout.splitlines()[-1]) if run.stdout else {}
result.update(returncode=run.returncode, mutation=args.mutation,
              launcher_SHA256=sha(Path(__file__).read_bytes()),
              source_files=sources, extracted_body_SHA256=sha(body.encode()),
              program_SHA256=sha(program.encode()), diagnostics=bool(run.stderr),
              probe_statement_only_not_full_probe=True,
              hardware_DMA_and_real_IOVA_allocation=False,
              frame_sizes_are_synthetic_not_format_negotiation=True)
(args.output / 'qualification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
assert not run.stderr, run.stderr
assert run.returncode in [0, 1]
