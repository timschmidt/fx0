# SPDX-License-Identifier: MIT
"""Read-only unchanged-r2 candidate health, parameterized by accepted baseline hashes."""
from pathlib import Path
import argparse, hashlib, json, os, re, subprocess, sys

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()
def out(*command): return subprocess.check_output(command,text=True,timeout=15).strip()

def kernel_pattern_counts(log):
    """Count error tokens without matching normal debug/ramoops/default text."""
    patterns = {
        r'BUG:': r'\bBUG:',
        r'Oops:': r'\bOops:',
        r'Kernel panic': r'Kernel panic',
        r'CFI failure': r'CFI failure',
        r'soft lockup': r'soft lockup',
        r'rcu.*stall': r'rcu.*stall',
        r'mdp5.*underrun': r'mdp5.*underrun',
        r'IOMMU.*fault': r'IOMMU.*\bfault\b',
    }
    return {name: len(re.findall(pattern, log, re.I))
            for name, pattern in patterns.items()}

def main():
    if sys.flags.optimize:raise RuntimeError('Optimized Python is forbidden')
    parser=argparse.ArgumentParser()
    for name in ['baseline-boot-id','package-db-sha256','world-sha256','boot-sha256']:parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    for value in [args.package_db_sha256,args.world_sha256,args.boot_sha256]:assert re.fullmatch('[a-f0-9]{64}',value)
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert boot!=args.baseline_boot_id
    assert Path('/proc/sys/kernel/osrelease').read_text().strip()=='6.18.63-fx0-vibrator-alpine'
    assert 'fx0.native_trial=reproducible-r2-01' in Path('/proc/cmdline').read_text().split()
    assert sha('/sys/kernel/notes')=='1e9be71c9bb7ed42d12826a039097bd853bb6f9781325b47008ed46c679353e0'
    assert Path('/proc/sys/kernel/tainted').read_text().strip()=='0'
    assert Path('/sys/module/module/parameters/sig_enforce').read_text().strip()=='Y'
    assert sha('/lib/apk/db/installed')==args.package_db_sha256
    assert sha('/etc/apk/world')==args.world_sha256
    assert sha('/dev/mmcblk0p15')==args.boot_sha256
    assert out('findmnt','-n','-o','FSTYPE','-T','/usr/lib/modules')=='tmpfs'
    modules=Path('/usr/lib/modules/6.18.63-fx0-vibrator-alpine')
    paths=sorted(p for p in modules.rglob('*') if p.is_file());assert len(paths)==478
    manifest=''.join(sha(p)+'  '+str(p.relative_to(modules))+'\n' for p in paths)
    assert hashlib.sha256(manifest.encode()).hexdigest()=='e5844d5ba3b12935b73a3517d7be67a9d18e6013ac5f59d547c4177b1fd8cdfb'
    armed=dict(row.split('=',1) for row in Path('/run/fx0-native-trial/return-armed').read_text().splitlines())
    assert armed['TOKEN']=='fx0.native_trial=reproducible-r2-01' and armed['DEADLINE']=='420'
    pid=int(armed['PID']);os.kill(pid,0)
    assert sha('/proc/'+str(pid)+'/exe')=='ba0ed0f2b670f0e270b7c61fbf95ed13180d0f59208bb57b4827a8c919bb1f02'
    assert out('systemctl','is-active','fx0-native-return.timer')=='active'
    assert out('systemctl','is-system-running')=='running'
    sway=out('pgrep','-x','sway');gesture=out('pgrep','-x','lisgd');assert len(sway.splitlines())==len(gesture.splitlines())==1
    assert any(os.readlink(p)=='/dev/input/event2' for p in Path('/proc',gesture,'fd').iterdir())
    assert Path('/sys/devices/system/cpu/online').read_text().strip()=='0-3'
    policies=list(Path('/sys/devices/system/cpu/cpufreq').glob('policy*'));assert policies
    for p in policies:
        assert (p/'scaling_governor').read_text().strip()=='schedutil' and (p/'scaling_max_freq').read_text().strip()=='787200'
    log=subprocess.check_output(['dmesg'],text=True)
    counts=kernel_pattern_counts(log);assert not any(counts.values()),counts
    print(json.dumps(dict(boot_id=boot,exact_r2_notes_verified=True,all478_new_module_metadata_files_verified=True,
        early_static_helper_alive_and_exact_binary=True,primary_return_timer_active=True,
        four_cpus_schedutil_787200_max=True,Sway_PID=int(sway),gesture_PID=int(gesture),touch_device_open=True,
        systemd='running',taint=0,serious_kernel_pattern_counts=counts,kernel_log_SHA256=hashlib.sha256(log.encode()).hexdigest(),
        package_DB_world_and_raw_boot_unchanged=True,read_only=True)))

if __name__ == "__main__":
    main()
