# SPDX-License-Identifier: GPL-2.0-only
"""Reject readiness, endpoint and producer-lifetime regressions in logical services."""
from pathlib import Path
import argparse,importlib.util,json,os,subprocess
B=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('qmi',B/'check-qmi.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists();a.output.mkdir()
code,_=m.model(a.source);controls=[]
def change(label,old,new,expected):
 assert code.count(old)==1,(label,code.count(old));assert old!=new;controls.append((label,code.replace(old,new),expected))
new=m.function(code,'qcom_slim_ngd_qmi_new_server');delete=m.function(code,'qcom_slim_ngd_qmi_del_server');worker=m.function(code,'qcom_slim_ngd_up_worker');stop=m.function(code,'qcom_slim_ngd_stop_up');notify=m.function(code,'qcom_slim_ngd_ssr_pdr_notify');parent=m.function(code,'qcom_slim_ngd_ctrl_remove')
queue='\tif (ctrl->parent_ready && ctrl->child_ready && ctrl->up_requested)\n\t\tschedule_work(&ctrl->ngd_up_work);\n'
change('late-service-not-requeued',new,new.replace(queue,''),'service-after-expired-UP')
change('readiness-consumed-by-worker',worker,worker.replace('\t\tqcom_slim_ngd_enable(ctrl, true);','\t\tqcom_slim_ngd_enable(ctrl, true), WRITE_ONCE(ctrl->qmi_ready, false);'),'repeated-UP-retains-readiness')
change('missing-post-wait-readiness',worker,worker.replace(' && ctrl->qmi_ready',''),'server-deleted-after-positive-wait')
change('delete-endpoint-update-unlocked',delete,delete.replace('\tmutex_lock(&ctrl->ssr_lock);\n','').replace('\tmutex_unlock(&ctrl->ssr_lock);\n',''),'delete-serialized-with-client-initialization')
change('new-endpoint-update-unlocked',new,new.replace('\tmutex_lock(&ctrl->ssr_lock);\n','').replace('\tmutex_unlock(&ctrl->ssr_lock);\n',''),'new-server-serialized-with-client-initialization')
condition='if (qmi->svc_info.sq_node == service->node &&\n\t    qmi->svc_info.sq_port == service->port)'
change('stale-delete-clears-latest-endpoint',delete,delete.replace(condition,'if (true)'),'old-delete-does-not-clear-replacement')
change('delete-ignores-port',delete,delete.replace(condition,'if (qmi->svc_info.sq_node == service->node)'),'stale-delete-endpoint-component-0')
change('delete-ignores-node',delete,delete.replace(condition,'if (qmi->svc_info.sq_port == service->port)'),'stale-delete-endpoint-component-1')
change('stop-does-not-close-admission',stop,stop.replace('\tWRITE_ONCE(ctrl->child_ready, false);\n',''),'cancel-wait-action-0')
change('cancel-under-worker-mutex',stop,stop.replace('\tmutex_unlock(&ctrl->ssr_lock);\n\tcancel_work_sync(&ctrl->ngd_up_work);','\tcancel_work_sync(&ctrl->ngd_up_work);\n\tmutex_unlock(&ctrl->ssr_lock);'),'service-before-UP')
change('QMI-producer-ignores-child-gate',new,new.replace('ctrl->parent_ready && ctrl->child_ready && ctrl->up_requested','ctrl->parent_ready && ctrl->up_requested'),'child-rebind-QMI-arrival-during-probe')
change('QMI-producer-ignores-last-DOWN',new,new.replace('ctrl->parent_ready && ctrl->child_ready && ctrl->up_requested','ctrl->parent_ready && ctrl->child_ready'),'new-service-after-DOWN-stays-idle')
change('new-service-does-not-notify-waiters',new,new.replace('\twake_up_all(&ctrl->qmi_wait);\n',''),'service-arrives-during-wait')
change('stop-does-not-notify-waiters',stop,stop.replace('\twake_up_all(&ctrl->qmi_wait);\n',''),'cancel-wait-action-0')
change('DOWN-does-not-notify-waiters',notify,notify.replace('\t\twake_up_all(&ctrl->qmi_wait);\n',''),'cancel-wait-action-1')
change('parent-cancel-leaves-QMI-producer-open',parent,parent.replace('\tqcom_slim_ngd_stop_parent_up(ctrl);','\tcancel_work_sync(&ctrl->ngd_up_work);'),'QMI-arrival-during-parent-cancel')
parent_stop=m.function(code,'qcom_slim_ngd_stop_parent_up');probe=m.function(code,'qcom_slim_ngd_ctrl_probe');child=m.function(code,'qcom_slim_ngd_probe')
change('QMI-producer-ignores-parent',new,new.replace('ctrl->parent_ready && ',''),'partial-parent-QMI-after-UP')
change('UP-producer-ignores-parent',notify,notify.replace('ctrl->parent_ready && ctrl->child_ready','ctrl->child_ready'),'partial-parent-probe-stage-1-last-DOWN-0')
change('child-probe-ignores-parent',child,child.replace('ctrl->parent_ready && ctrl->up_requested','ctrl->up_requested'),'partial-parent-probe-stage-0-last-DOWN-0')
change('worker-pre-wait-ignores-parent',worker,worker.replace('!ctrl->parent_ready || ',''),'closed-parent-forced-queued-worker')
change('worker-post-wait-ignores-parent',worker,worker.replace('ctrl->parent_ready && ctrl->child_ready &&','ctrl->child_ready &&'),'parent-close-after-positive-wait')
change('wait-ignores-parent-closure',worker,worker.replace('\t\t\t\t\t       !READ_ONCE(ctrl->parent_ready) ||\n',''),'cancel-wait-action-2')
change('parent-stop-leaves-parent-open',parent_stop,parent_stop.replace('\tWRITE_ONCE(ctrl->parent_ready, false);\n',''),'parent-cancel-child-bind-producer-0')
change('parent-stop-closes-only-child',parent_stop,parent_stop.replace('ctrl->parent_ready, false','ctrl->child_ready, false'),'parent-cancel-child-bind-producer-0')
change('parent-stop-does-not-notify',parent_stop,parent_stop.replace('\twake_up_all(&ctrl->qmi_wait);\n',''),'cancel-wait-action-2')
change('parent-stop-cancels-under-SSR',parent_stop,parent_stop.replace('\tmutex_unlock(&ctrl->ssr_lock);\n\tcancel_work_sync(&ctrl->ngd_up_work);','\tcancel_work_sync(&ctrl->ngd_up_work);\n\tmutex_unlock(&ctrl->ssr_lock);'),'service-before-UP')
change('parent-ready-published-before-child-registration',probe,probe.replace('\tret = of_qcom_slim_ngd_register(dev, ctrl);','\tWRITE_ONCE(ctrl->parent_ready, true);\n\tret = of_qcom_slim_ngd_register(dev, ctrl);'),'partial-parent-probe-stage-0-last-DOWN-0')
change('parent-success-does-not-replay-UP',probe,probe.replace('\tif (ctrl->child_ready && ctrl->up_requested)\n\t\tschedule_work(&ctrl->ngd_up_work);\n',''),'partial-parent-probe-stage-0-last-DOWN-0')
change('DOWN-ignores-parent-closure',notify,notify.replace('!ctrl->parent_ready || ',''),'DOWN-during-parent-provider-release')
env=os.environ|{'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'};env.pop('LSAN_OPTIONS',None);records=[]
for label,text,expected in controls:
 src=a.output/(label+'.c');src.write_text(text);binary=a.output/label
 c=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-Wno-sign-compare','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',str(src),'-o',str(binary)],capture_output=True,text=True,timeout=60)
 (a.output/(label+'-build.log')).write_text(c.stdout+c.stderr);assert c.returncode==0,c.stderr
 r=subprocess.run([str(binary)],env=env,capture_output=True,text=True,timeout=30);(a.output/(label+'.stdout')).write_text(r.stdout);(a.output/(label+'.stderr')).write_text(r.stderr);assert r.returncode==0,r.stderr
 assert not any(t in r.stderr for t in ['AddressSanitizer','LeakSanitizer','runtime error:','model invariant']),r.stderr
 j=json.loads(r.stdout);assert j['cases']==71 and j['checks']==1079 and j['failures']>0 and expected+':' in r.stderr,(label,j,expected)
 records.append(dict(control=label,failures=j['failures'],expected_case=expected,rejected=True,sanitizer_diagnostics=False))
(a.output/'qualification.json').write_text(json.dumps(dict(passed=True,controls=records,normal_LSan_and_failfast_ASan_UBSan=True,invalid_sync_cancellation_logged_without_performing_deadlock=True,all_services_synthetic=True,hardware_audio_firmware_or_phone_execution=False),indent=2)+'\n');print(json.dumps(records))
