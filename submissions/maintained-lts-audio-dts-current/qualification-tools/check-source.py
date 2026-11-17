# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib, json, re, subprocess
N = Path(__file__).resolve().parent
R = N.parents[2]
C = R / 'worktrees/linux-fx0-lts-integration-current-01'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
prepared = read(N / 'prepared.json')
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=C, text=True).strip() == prepared['base']
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=C)
assert read(N / 'audit-03/qualification.json')['passed']
assert read(N / 'native-02/controller.json')['passed']
assert read(N / 'native-source-binding.json')['objects'] == 90
assert read(N / 'original-patch-style.json')['passed']
old = '2eae6938469b792720462ed5c37b97f4f12dd9c9'
unchanged = subprocess.check_output(['git', 'diff', '--name-only', old, 'HEAD', '--',
    'arch/arm/boot/dts', 'include/dt-bindings', 'Documentation/devicetree/bindings'], cwd=C, text=True)
assert not unchanged
f = prepared['DTS']
assert sha(C / f) == prepared['DTS_SHA256'] == read(N.parent / 'wcnss-nfc-01/source-current.json')['source_files'][f]
matches = {
    'drivers/soc/qcom/apr.c':['qcom,apr-v2'],
    'drivers/dma/qcom/bam_dma.c':['qcom,bam-v1.4.0'],
    'drivers/slimbus/qcom-ngd-ctrl.c':['qcom,slim-ngd-v1.5.0'],
    'drivers/remoteproc/qcom_q6v5_pas.c':['qcom,msm8226-adsp-pil'],
    'sound/soc/qcom/qdsp6/q6core.c':['qcom,q6core'],
    'sound/soc/qcom/qdsp6/q6afe.c':['qcom,q6afe'],
    'sound/soc/qcom/qdsp6/q6asm.c':['qcom,q6asm'],
    'sound/soc/qcom/qdsp6/q6adm.c':['qcom,q6adm'],
    'sound/soc/qcom/qdsp6/q6afe-dai.c':['qcom,q6afe-dais'],
    'sound/soc/qcom/qdsp6/q6asm-dai.c':['qcom,q6asm-dais'],
    'sound/soc/qcom/qdsp6/q6routing.c':['qcom,q6adm-routing'],
    'sound/soc/qcom/apq8096.c':['qcom,apq8096-sndcard'],
}
for path, values in matches.items():
    text = (C / path).read_text()
    assert all(re.search(r'\.compatible\s*=\s*"' + re.escape(value) + r'"', text) for value in values), path
bam = (C / 'drivers/dma/qcom/bam_dma.c').read_text()
for name in ['qcom,controlled-remotely', 'qcom,ee', 'qcom,num-ees', 'num-channels']: assert '"' + name + '"' in bam
ngd = (C / 'drivers/slimbus/qcom-ngd-ctrl.c').read_text()
assert 'ctrl->dma_rx_channel = dma_request_chan(dev, "rx");' in ngd
assert 'ctrl->dma_tx_channel = dma_request_chan(dev, "tx");' in ngd
asm = (C / 'sound/soc/qcom/qdsp6/q6asm-dai.c').read_text()
assert 'of_property_read_u32(node, "reg", &id)' in asm and '*dai_drv = q6asm_fe_dais_template[id];' in asm
assert 'id >= MAX_SESSIONS || id < 0' in asm and 'pdata->sid = -1;' in asm
template = re.search(r'q6asm_fe_dais_template\[\] = \{(.*?)\n\};', asm, re.S).group(1)
assert re.findall(r'Q6ASM_FEDAI_DRIVER\((\d+)\)', template) == list(map(str, range(1,9)))
assert re.search(r'#define MAX_SESSIONS\s+8\b', (C / 'sound/soc/qcom/qdsp6/q6asm.h').read_text())
selected = ['soc/qcom/qcom,apr.yaml', 'soc/qcom/qcom,apr-services.yaml',
    'dma/qcom,bam-dma.yaml', 'slimbus/qcom,slim-ngd.yaml',
    'sound/qcom,q6core.yaml', 'sound/qcom,q6afe.yaml', 'sound/qcom,q6asm.yaml',
    'sound/qcom,q6asm-dais.yaml', 'sound/qcom,q6adm.yaml', 'sound/qcom,q6adm-routing.yaml',
    'sound/qcom,q6dsp-lpass-ports.yaml']
files = set(read(N / 'native-02/controller.json')['source_files'])
files |= {'sound/soc/qcom/qdsp6/q6asm.h', 'sound/soc/qcom/Kconfig'}
files |= {'Documentation/devicetree/bindings/' + p for p in selected}
files |= {'arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai' + s + '.dts' for s in ['', '-cpr', '-suspend']}
origins = prepared['origins']
scopes = [
    ['APR transport compatible/domain/channel and core service'],
    ['BAM windows/IRQ/remote EE and SLIMbus windows/IRQ/RX3/TX4/NGD child'],
    ['AFE/ASM/ADM services and DAI/routing cell declarations'],
    ['ASM front-end DAI registers 0, 1 and 2 with matching template/header indices'],
]
j = dict(passed=True, source_head=prepared['base'], source_files={f:sha(C / f) for f in sorted(files)},
    existing_equivalents=[dict(origin=h, scope=s, evidence='audit-03/qualification.json') for h,s in zip(origins,scopes)],
    kernel_source_changes=False, source_branch_unchanged=True,
    common_audio_blocks_exactly_match_frozen_reference=True,
    driver_compatibles_and_property_consumers=matches, ASM_frontend_template_indices_bound=True,
    omitted_audio_IOMMU_uses_existing_sid_minus_one_fallback=True,
    driver_behavior_or_hardware_execution_qualified=False,
    prior_full19_schema_source_head=old, all_DTS_binding_and_constant_inputs_unchanged=True,
    full_schema_evidence_reused=True, new_full_schema_run=False,
    native_objects=90, semantic_board_cases=19, semantic_controls=6, binding_controls=6,
    remaining_SLIMbus_BAM_runtime_audits_not_closed_here=True,
    phone_access=False, audio_execution=False, WiFi_scans=False, network_changes=False)
(N / 'source-equivalence.json').write_text(json.dumps(j, indent=2) + '\n')
print('Four scoped DTS equivalents, unchanged schema inputs and actual driver consumers verified')
