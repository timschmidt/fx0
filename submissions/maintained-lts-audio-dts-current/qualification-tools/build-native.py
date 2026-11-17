# SPDX-License-Identifier: GPL-2.0-only
"""Compile audio-description consumers only; never execute audio or firmware."""
from pathlib import Path
import hashlib, json, os, signal, subprocess
N = Path(__file__).resolve().parent
C = N.parents[2] / 'worktrees/linux-fx0-lts-integration-current-01'
O = N / 'native-02'
O.mkdir()
objects = ['sound/soc/qcom/qdsp6/' + n + '.o' for n in [
    'q6core', 'q6afe', 'q6afe-dai', 'q6afe-clocks', 'q6asm', 'q6asm-dai',
    'q6adm', 'q6routing', 'q6dsp-common', 'q6dsp-lpass-ports', 'q6dsp-lpass-clocks']]
objects += ['drivers/slimbus/' + n + '.o' for n in ['core', 'messaging', 'sched', 'stream', 'qcom-ngd-ctrl']]
objects += ['drivers/soc/qcom/apr.o', 'drivers/dma/qcom/bam_dma.o',
    'drivers/rpmsg/rpmsg_core.o', 'drivers/rpmsg/qcom_smd.o']
objects += ['drivers/remoteproc/' + n + '.o' for n in ['qcom_q6v5', 'qcom_q6v5_pas', 'qcom_pil_info', 'qcom_common']]
objects += ['drivers/soc/qcom/' + n + '.o' for n in ['pdr_interface', 'qmi_interface', 'qmi_encdec', 'mdt_loader']]
objects += ['sound/soc/qcom/apq8096.o', 'sound/soc/qcom/common.o']
assert len(objects) == 30
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
files = [p[:-2] + '.c' for p in objects]
files += ['arch/arm/boot/dts/qcom/qcom-msm8226.dtsi', 'include/dt-bindings/soc/qcom,apr.h',
    'include/dt-bindings/sound/qcom,q6asm.h', 'include/dt-bindings/sound/qcom,q6afe.h']
j = dict(passed=False, state='prepared', source_files={f:sha(C / f) for f in files},
    profiles=[], stages=[], phone_access=False, audio_firmware_or_hardware_execution=False,
    ARM32_RT_unsupported_not_counted=True)
child = None
save = lambda: (O / 'controller.json').write_text(json.dumps(j, indent=2) + '\n')
principals = ['QCOM_APR', 'SND_SOC_QCOM', 'SND_SOC_MSM8996', 'SND_SOC_QDSP6', 'SLIMBUS',
    'SLIM_QCOM_NGD_CTRL', 'QCOM_BAM_DMA', 'RPMSG_QCOM_SMD', 'QCOM_Q6V5_PAS']
try:
    for arch, rt, mode, seed in [
        ('arm', False, 'y', 'native-01/arm-normal-CPU-enabled-system-on-out'),
        ('arm64', False, 'm', 'native-01/arm64-normal-CPU-enabled-system-off-out'),
        ('arm64', True, 'm', 'native-02/arm64-rt-CPU-enabled-system-off-out')]:
        label = arch + ('-rt' if rt else '-normal') + '-audio-description-' + mode
        out = O / (label + '-out')
        out.mkdir()
        (out / 'tmp').mkdir()
        (out / '.config').write_bytes((N.parent / 'system-coordinator-01' / seed / '.config').read_bytes())
        args = ['scripts/config', '--file', str(out / '.config'), '--disable', 'COMPILE_TEST', '--enable', 'MODULES']
        for sym in ['ARCH_QCOM', 'NET', 'SOUND', 'SND', 'SND_SOC', 'DMADEVICES', 'DMA_ENGINE',
                    'REMOTEPROC', 'RPMSG', 'QCOM_SMEM', 'QCOM_SMP2P', 'QCOM_SMD_RPM',
                    'COMMON_CLK', 'OF', 'PM', 'QCOM_RPROC_COMMON']:
            args += ['--enable', sym]
        for sym in principals:
            args += ['--enable' if mode == 'y' else '--module', sym]
        subprocess.run(args, cwd=C, check=True)
        make = ['make', 'O=' + str(out), 'ARCH=' + arch, 'LLVM=-21', 'W=1',
            'KCFLAGS=-Werror=incompatible-function-pointer-types', '-j2']
        for phase, targets in [('config', ['olddefconfig']), ('objects', objects)]:
            log = O / (label + '-' + phase + '.log')
            with log.open('xb') as stream:
                child = subprocess.Popen(make + targets, cwd=C,
                    env=os.environ | {'TMPDIR':str(out / 'tmp'), 'GIT_NO_LAZY_FETCH':'1'},
                    stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                j.update(state='running ' + label + ' ' + phase, active_PID=child.pid)
                save()
                code = child.wait(timeout=600)
            diagnostics = [l for l in log.read_text().splitlines() if 'warning:' in l.lower() or 'error:' in l.lower()]
            j['stages'].append(dict(profile=label, phase=phase, returncode=code,
                diagnostics=diagnostics, log_SHA256=sha(log)))
            save()
            assert code == 0 and not diagnostics, diagnostics
            if phase == 'config':
                config = (out / '.config').read_text()
                for sym in principals: assert 'CONFIG_' + sym + '=' + mode + '\n' in config, (sym, mode)
        cfg = (out / '.config').read_text()
        for sym in principals: assert 'CONFIG_' + sym + '=' + mode + '\n' in cfg, (sym, mode)
        assert ('CONFIG_PREEMPT_RT=y\n' in cfg) == rt
        assert 'CONFIG_CFI=y\n' in cfg and '# CONFIG_CFI_PERMISSIVE is not set\n' in cfg
        assert '# CONFIG_COMPILE_TEST is not set\n' in cfg
        assert not (out / 'certs/signing_key.pem').exists()
        assert all(sha(C / f) == h for f, h in j['source_files'].items())
        j['profiles'].append(dict(profile=label, ARCH=arch, PREEMPT_RT=rt, mode=mode,
            CFI=True, CFI_PERMISSIVE=False, config_SHA256=sha(out / '.config'),
            objects={p:sha(out / p) for p in objects}))
    j.update(passed=True, state='terminal success', native_objects=90)
finally:
    if child is not None and child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        try: child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)
    j.pop('active_PID', None)
    j['owned_child_terminal_and_reaped'] = child is None or child.returncode is not None
    if not j['passed']: j['state'] = 'terminal failure'
    save()
print(json.dumps(dict(passed=j['passed'], native_objects=90)))
