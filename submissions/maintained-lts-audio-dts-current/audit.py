#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Audit public audio descriptions and compiled nodes without executing audio."""
from pathlib import Path
import argparse, copy, hashlib, json, re
import dtschema
ap = argparse.ArgumentParser(description=__doc__)
for name in ['source', 'reference', 'dtbs', 'schema', 'prior', 'output']:
    ap.add_argument('--' + name, type=Path, required=True)
a = ap.parse_args()
O = a.output.resolve()
O.mkdir(mode=0o700)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
f = 'arch/arm/boot/dts/qcom/qcom-msm8226.dtsi'
current, reference = [(root / f).read_text() for root in [a.source, a.reference]]
def block(text, label):
    m = re.search(r'\b' + label + r'\s*:\s*[^{};]+\{', text)
    assert m, label
    pos = m.end()
    depth = 1
    while depth:
        depth += (text[pos] == '{') - (text[pos] == '}')
        pos += 1
    assert text[pos] == ';'
    return text[m.start():pos + 1]
labels = ['slimbam', 'slim_msm', 'apr', 'q6core', 'q6afe', 'q6afedai',
          'q6asm', 'q6asmdai', 'q6adm', 'q6routing']
blocks = {}
for label in labels:
    actual = block(current, label)
    assert actual == block(reference, label), label
    blocks[label] = hashlib.sha256(actual.encode()).hexdigest()
for label in ['slimbam', 'slim_msm', 'apr']:
    assert 'status = "disabled";' in block(current, label)
assert '#include <dt-bindings/soc/qcom,apr.h>' in current
def macro(text, name):
    m = re.search(r'^#define\s+' + name + r'\s+(0x[0-9a-fA-F]+|\d+)\b', text, re.M)
    assert m, name
    return int(m[1], 0)
constants = {}
for f, expected in [
    ('include/dt-bindings/soc/qcom,apr.h', {'APR_DOMAIN_ADSP':4, 'APR_SVC_ADSP_CORE':3, 'APR_SVC_AFE':4, 'APR_SVC_ASM':7, 'APR_SVC_ADM':8}),
    ('include/dt-bindings/sound/qcom,q6asm.h', {'MSM_FRONTEND_DAI_MULTIMEDIA1':0, 'MSM_FRONTEND_DAI_MULTIMEDIA2':1, 'MSM_FRONTEND_DAI_MULTIMEDIA3':2})]:
    for name, value in expected.items():
        assert macro((a.source / f).read_text(), name) == macro((a.reference / f).read_text(), name) == value
        constants[name] = value
validator = dtschema.DTValidator([str(a.schema)])
prior = json.loads(a.prior.read_text())
assert prior['passed'] and prior['full_current_19_board_schema_passed'] and len(prior['DTBs']) == 19
APR = '/soc/remoteproc@fe200000/smd-edge/apr'
BAM = '/soc/dma-controller@fe104000'
SLIM = '/soc/slimbus@fe12f000'
ASM = APR + '/service@7/dais'
def flatten(tree):
    out = {}
    def walk(node, path):
        out[path] = {k:v for k,v in node.items() if not isinstance(v, dict)}
        for name, value in node.items():
            if isinstance(value, dict): walk(value, path.rstrip('/') + '/' + name)
    walk(tree, '/')
    return out
def semantic(tree):
    nodes = flatten(tree)
    phandles = {n['phandle']:p for p,n in nodes.items() if 'phandle' in n}
    bam, slim, apr = [nodes[p] for p in [BAM, SLIM, APR]]
    assert bam['compatible'] == ['qcom,bam-v1.4.0'] and bam['reg'] == [[0xfe104000, 0x20000]]
    assert bam['interrupts'] == [[0,164,4]] and bam['#dma-cells'] == 1
    assert (bam['qcom,ee'], bam['qcom,num-ees'], bam['num-channels']) == (1,2,31)
    assert bam['qcom,controlled-remotely'] is True
    assert slim['compatible'] == ['qcom,slim-ngd-v1.5.0'] and slim['reg'] == [[0xfe12f000,0x35000]]
    assert slim['interrupts'] == [[0,163,4]] and slim['dma-names'] == ['rx','tx']
    assert [[phandles[v[0]], *v[1:]] for v in slim['dmas']] == [[BAM,3],[BAM,4]]
    assert nodes[SLIM+'/slim@1']['reg'] == [[1]]
    assert apr['compatible'] == ['qcom,apr-v2'] and apr['qcom,domain'] == 4
    assert apr['qcom,smd-channels'] == ['apr_audio_svc']
    assert apr['#address-cells'] == 1 and apr['#size-cells'] == 0
    for service, name in [(3,'q6core'),(4,'q6afe'),(7,'q6asm'),(8,'q6adm')]:
        node = nodes[APR+'/service@'+str(service)]
        assert node['compatible'] == ['qcom,'+name] and node['reg'] == [[service]]
    for path, name in [(APR+'/service@4/dais','q6afe-dais'),(ASM,'q6asm-dais')]:
        node = nodes[path]
        assert node['compatible'] == ['qcom,'+name] and node['#sound-dai-cells'] == 1
        assert node['#address-cells'] == 1 and node['#size-cells'] == 0
    assert nodes[APR+'/service@8/routing']['#sound-dai-cells'] == 0
    for ident in [0,1,2]: assert nodes[ASM+'/dai@'+str(ident)]['reg'] == [[ident]]
    return nodes
rows = []
madai = None
for row in prior['DTBs']:
    dtb = a.dtbs / row['board']
    assert sha(dtb) == row['DTB_SHA256'] and row['full_schema_silent']
    tree = validator.decode_dtb(dtb.read_bytes())[0]
    nodes = semantic(tree)
    validated = 0
    for path, filters in [(BAM,['dma/qcom,bam-dma.yaml']), (SLIM,['slimbus/qcom,slim-ngd.yaml']),
        (APR,['soc/qcom/qcom,apr.yaml'])] + [(APR+'/service@'+str(i), ['sound/qcom,'+name+'.yaml'])
        for i,name in [(3,'q6core'),(4,'q6afe'),(7,'q6asm'),(8,'q6adm')]]:
        # Keep children for their binding's recursive validation.
        node = tree
        for component in path.strip('/').split('/'): node = node[component]
        errors = list(validator.iter_errors(node, filter=filters))
        assert not errors, (row['board'], path, [e.message for e in errors])
        validated += 1
    target = row['board'].startswith('qcom-msm8926-lg-madai')
    if target:
        assert all(nodes[p]['status'] == ['okay'] for p in [APR,BAM,SLIM])
        assert 'iommus' not in nodes[ASM]
    rows.append(dict(board=row['board'], DTB_SHA256=row['DTB_SHA256'], semantic_contract_passed=True,
        focused_recursive_binding_nodes=validated, target_Madai_variant=target,
        APR_status=nodes[APR].get('status'), BAM_status=nodes[BAM].get('status')))
    if row['board'] == 'qcom-msm8926-lg-madai.dtb': madai = tree
assert madai is not None
semantic_controls = []
for name, path, prop, value in [
    ('swapped-DMA-pipes',SLIM,'dmas',list(reversed(flatten(madai)[SLIM]['dmas']))),
    ('wrong-BAM-EE',BAM,'qcom,ee',0), ('wrong-APR-domain',APR,'qcom,domain',3),
    ('wrong-core-service',APR+'/service@3','reg',[[4]]),
    ('one-based-front-end',ASM+'/dai@0','reg',[[1]]),
    ('wrong-DMA-window',BAM,'reg',[[0xfe104000,0x10000]])]:
    bad = copy.deepcopy(madai)
    node = bad
    for component in path.strip('/').split('/'): node = node[component]
    node[prop] = value
    try: semantic(bad)
    except AssertionError: semantic_controls.append(dict(label=name, rejected=True))
    else: raise AssertionError(name)
binding_controls = []
for name, path, schema, prop, value in [
    ('wrong-SMD-channel',APR,'soc/qcom/qcom,apr.yaml','qcom,smd-channels',['wrong']),
    ('domain-out-of-range',APR,'soc/qcom/qcom,apr.yaml','qcom,domain',0),
    ('missing-remote-EE-count',BAM,'dma/qcom,bam-dma.yaml','qcom,num-ees',None),
    ('wrong-DMA-name-order',SLIM,'slimbus/qcom,slim-ngd.yaml','dma-names',['tx','rx']),
    ('wrong-ASM-DAI-cells',ASM,'sound/qcom,q6asm-dais.yaml','#sound-dai-cells',2),
    ('missing-ASM-DAI-reg',ASM+'/dai@0','sound/qcom,q6asm-dais.yaml','reg',None)]:
    # Validate the ASM parent when corrupting its child.
    root_path = ASM if path.startswith(ASM+'/') else path
    node = copy.deepcopy(madai)
    target = node
    for component in path.strip('/').split('/'): target = target[component]
    if value is None: target.pop(prop)
    else: target[prop] = value
    for component in root_path.strip('/').split('/'): node = node[component]
    errors = list(validator.iter_errors(node, filter=[schema]))
    assert errors, name
    binding_controls.append(dict(label=name, rejected=True, diagnostics=len(errors)))
j = dict(passed=True, source_DTS_SHA256=sha(a.source / 'arch/arm/boot/dts/qcom/qcom-msm8226.dtsi'),
    exact_current_and_reference_block_SHA256=blocks, protocol_and_frontend_constants=constants,
    boards=rows, semantic_board_cases=19, semantic_corruption_controls=semantic_controls,
    binding_invalid_input_controls=binding_controls, full19_schema_evidence_reused=True,
    new_full_schema_build=False, processed_schema_SHA256=sha(a.schema),
    firmware_audio_or_driver_runtime_executed=False, phone_access=False,
    physical_audio_and_full_runtime_chain_qualified=False)
(O / 'qualification.json').write_text(json.dumps(j, indent=2) + '\n')
print(json.dumps(dict(passed=True, boards=19, semantic_controls=len(semantic_controls),
    binding_controls=len(binding_controls))))
