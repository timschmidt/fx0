# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib, json, subprocess
N = Path(__file__).resolve().parent
C = N.parents[2] / 'worktrees/linux-fx0-lts-integration-current-01'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
prepared = read(N / 'prepared.json')
paths = list(prepared['source_files'])
O = N / 'candidate'
assert not O.exists()
for f, h in prepared['source_files'].items():
    assert sha(C / f) == h
    p = O / f
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes((C / f).read_bytes())
stages = []
for h in ['96f46405219d', '1330597c7480', '8f4b627656fa', '82bd09ce4fd3',
          'b1c3c51b0916', '3785dffc7c68', '0d695709ed38']:
    origin = read(N / ('upstream-' + h + '.json'))
    selected = [f for f in origin['files'] if f['filename'] in paths]
    stage = dict(origin=origin['commit'], prerequisite_only=h in ['96f46405219d', '1330597c7480'],
        excluded_unrelated_paths=[f['filename'] for f in origin['files'] if f['filename'] not in paths], files=[])
    patch = ''
    for f in selected:
        p = f['filename']
        before = N / 'stages' / h / (p + '.before')
        before.parent.mkdir(parents=True, exist_ok=True)
        before.write_bytes((O / p).read_bytes())
        patch += '--- a/' + p + '\n+++ b/' + p + '\n' + f['patch'] + '\n'
    pp = N / (h + '.patch')
    pp.write_text(patch)
    r = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(pp)],
        cwd=O, capture_output=True, text=True)
    (N / (h + '-apply.log')).write_text(r.stdout + r.stderr)
    assert r.returncode == 0 and 'fuzz' not in r.stdout and 'FAILED' not in r.stdout
    if h == '3785dffc7c68':
        p = O / paths[0]
        text = p.read_text()
        assert text.count('\t\tts->init = true;\n\n\t}') == 1
        p.write_text(text.replace('\t\tts->init = true;\n\n\t}', '\t\tts->init = true;\n\t}'))
        p = O / paths[1]
        text = p.read_text()
        needle = ' * @chip_period:\taccumulator for computing internal chip period\n'
        assert text.count(needle) == 1
        p.write_text(text.replace(needle, needle + ' * @init:\t\tfirst interrupt has initialized timestamp alignment\n'))
        stage['adaptation'] = 'Document new init field; remove redundant blank before closing brace'
    for f in selected:
        p = f['filename']
        after = N / 'stages' / h / (p + '.after')
        after.write_bytes((O / p).read_bytes())
        stage['files'].append(dict(path=p, before_SHA256=sha(after.with_suffix('.before')),
            after_SHA256=sha(after)))
    stages.append(stage)
for f in paths:
    upstream = (N / 'upstream-final' / f).read_text()
    current = (O / f).read_text()
    if f.endswith('.c'):
        current = current.replace('\t\tts->init = true;\n\t}', '\t\tts->init = true;\n\n\t}')
    else:
        current = current.replace(' * @init:\t\tfirst interrupt has initialized timestamp alignment\n', '')
    assert current == upstream, f
(N / 'composition.json').write_text(json.dumps(dict(base=prepared['base'], stages=stages,
    source_files={f:sha(O / f) for f in paths}, upstream_endpoint='0d695709ed380f1bc9303a91f57525d33766a07e',
    endpoint_matches_except_init_documentation_and_blank_line=True,
    runtime_changes=5, prerequisite_only_changes=2, phone_access=False), indent=2) + '\n')
print('Seven timestamp changes applied; endpoint matches official source except documentation and whitespace')
