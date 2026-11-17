# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,re,signal,subprocess,sys,tarfile
trial=sys.argv[1];assert trial in ['32','33'];prefix='normalized-ARM-'+trial;B=Path(__file__).resolve().parent;R=B.parents[1];prior_out=R/'local/fx0-cpu-port-current-01/full-ARM-out';source=B/'committed-replay-01/workspace/worktrees/linux-fx0-cpu-current-01';O=B/(prefix+'-out');O.mkdir(exist_ok=False);(O/'tmp').mkdir();controller=B/(prefix+'-controller.json');assert not controller.exists();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();accepted=json.loads((B/'feature-source-current.json').read_text());replay=json.loads((B/'committed-replay-01/controller.json').read_text());prior=json.loads((B/'full-ARM-30-build-controller.json').read_text());assert replay['passed'] and prior['passed'] and replay['source_head']==prior['source_head']==accepted['head'];head=accepted['head'];assert not (source/'.git').exists();assert prior['source_files']=={p:sha(source/p) for p in prior['source_files']}
if trial=='33':
 source=B/'normalized-source-33';source.mkdir(exist_ok=False)
 archive=B/'committed-replay-01/committed-linux-source.tar';assert sha(archive)==replay['source_archive_SHA256']
 with tarfile.open(archive) as tar:tar.extractall(source,filter='data')
 assert not (source/'.git').exists();assert prior['source_files']=={p:sha(source/p) for p in prior['source_files']}

(O/'.config').write_bytes((prior_out/'.config').read_bytes());assert sha(O/'.config')==prior['config_SHA256']
version=re.search(r'#define UTS_VERSION "#([0-9]+) ',(prior_out/'include/generated/utsversion.h').read_text());assert version;build_version=version[1]
# The normal build tools may use the existing development key. The audit never
# reads, hashes or copies that key; only its public certificate is compared.
key_for_build_tools=prior_out/'certs/signing_key.pem'
env=os.environ|{'TMPDIR':str(O/'tmp'),'PATH':str(B/'committed-replay-01/git-denied')+os.pathsep+os.environ['PATH'],'GIT_NO_LAZY_FETCH':'1','KBUILD_BUILD_USER':'fx0-review','KBUILD_BUILD_HOST':'source-check','KBUILD_BUILD_TIMESTAMP':'2026-11-16 00:00:00 UTC','KBUILD_BUILD_VERSION':build_version,'SOURCE_DATE_EPOCH':'1794787200'}
prefix_maps='-fdebug-prefix-map='+str(source)+'=/usr/src/linux -fdebug-prefix-map='+str(O)+'=/usr/src/linux-build'
make=['make','O='+str(O),'ARCH=arm','LLVM=-21','W=1','KCFLAGS=-Werror=incompatible-function-pointer-types '+prefix_maps,'KAFLAGS='+prefix_maps,'LOCALVERSION=-g'+head[:12],'CONFIG_MODULE_SIG_KEY='+str(key_for_build_tools),'--jobserver-style=pipe','-j4']
j=dict(started_UTC=datetime.now(timezone.utc).isoformat(),passed=False,state='prepared',source_head=head,source_tree=accepted['source_tree'],source_archive_SHA256=replay['source_archive_SHA256'],source_files=prior['source_files'],source_export_no_Git_metadata=True,Git_denied_during_build=True,network_requested=False,ARCH='arm',LLVM='-21',W=1,COMPILE_TEST=False,clean_output_directory=True,incremental=False,prior_config_SHA256=prior['config_SHA256'],explicit_source_release_suffix='-g'+head[:12],normalized_debug_paths=True,debug_prefix_maps=prefix_maps,source_directory=str(source),fixed_SOURCE_DATE_EPOCH='1794787200',fixed_build_version=build_version,fixed_build_user='fx0-review',fixed_build_host='source-check',fixed_build_timestamp='2026-11-16 00:00:00 UTC',controlled_same_development_certificate=True,existing_private_key_used_only_by_normal_build_tools=True,key_not_read_hashed_or_copied_by_audit=True,independent_public_recipe_without_private_signing_inputs_not_qualified=True,maintained_LTS_acceptance=False,full_package_update_recovery_or_physical_acceptance=False,phone_access=False,published=False,stages=[]);child=None

def save():controller.write_text(json.dumps(j,indent=2)+'\n')
def interrupted(sig,frame):raise InterruptedError(str(sig))
signal.signal(signal.SIGTERM,interrupted)
def run(label,cmd,timeout):
 global child
 with (B/(prefix+'-'+label+'.log')).open('xb') as stream:
  child=subprocess.Popen(cmd,cwd=source,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True);j.update(state='running '+label,active_PID=child.pid);save();ret=child.wait(timeout=timeout)
 j.pop('active_PID',None);j['stages'].append(dict(label=label,returncode=ret,log_SHA256=sha(B/(prefix+'-'+label+'.log')),diagnostics=[l for l in (B/(prefix+'-'+label+'.log')).read_text(errors='replace').splitlines() if 'warning:' in l.lower() or 'error:' in l.lower()]));save();assert ret==0,(label,ret)
try:
 run('config',make+['olddefconfig'],180);assert sha(O/'.config')==prior['config_SHA256'];j['config_SHA256']=sha(O/'.config');save()
 run('kernel-modules',make+['zImage','modules'],7200)
 assert prior['source_files']=={p:sha(source/p) for p in prior['source_files']};assert sha(O/'.config')==prior['config_SHA256'];release=(O/'include/config/kernel.release').read_text().strip();assert release==prior['release'],release
 assert sha(O/'certs/signing_key.x509')==sha(prior_out/'certs/signing_key.x509')
 artifacts={p:sha(O/p) for p in prior['artifacts']};modules=sorted(O.rglob('*.ko'));assert len(modules)==459,len(modules)
 comparisons={p:dict(clean_SHA256=value,prior_SHA256=prior['artifacts'][p],byte_identical=value==prior['artifacts'][p]) for p,value in artifacts.items()}
 j.update(passed=True,state='terminal success',release=release,module_artifacts={str(p.relative_to(O)):sha(p) for p in modules},artifacts=artifacts,comparison_with_original_unmapped_incremental= comparisons,modules_built=459,public_certificate_SHA256=sha(O/'certs/signing_key.x509'),all_core_artifacts_byte_identical=all(v['byte_identical'] for v in comparisons.values()))
except BaseException as e:j.update(state='terminal failure',error_type=type(e).__name__,error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;j['finished_UTC']=datetime.now(timezone.utc).isoformat();save()
print(json.dumps(dict(passed=j['passed'],release=j.get('release'),modules=j.get('modules_built'),all_core_artifacts_byte_identical=j.get('all_core_artifacts_byte_identical'))))
