"""Qualify the retained LTS remove/reconfigure caller against owned transactions."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('response', B / 'check-response.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
source, output = map(Path, sys.argv[1:])
output.mkdir()
code, bindings = m.model(source)
body = m.function((source / 'drivers/slimbus/qcom-ngd-ctrl.c').read_text(), 'qcom_slim_ngd_disable_stream')
bindings['qcom_slim_ngd_disable_stream'] = hashlib.sha256(body.encode()).hexdigest()
types = 'struct slim_port {struct {u8 id;} ch;};\nstruct slim_stream_runtime {struct slim_device *dev;unsigned num_ports;struct slim_port *ports;};\n'
code = code.replace('static bool core_clock_bad;', types + body + '\nstatic bool core_clock_bad;')
assert m.function(code, 'qcom_slim_ngd_disable_stream') == body
main = r'''
int main(void) {
 unsigned counts[]={0,1,2,34,35,38,39,40},addresses[]={0,0x65,0xff};
 for(unsigned a=0;a<3;a++) for(unsigned n=0;n<8;n++) for(unsigned fault=0;fault<9;fault++) {
  unsigned count=counts[n];char label[100];snprintf(label,sizeof(label),"LTS-remove-ports-%u-address-%u-fault-%u",count,addresses[a],fault);reset_case(label,3);
  struct slim_port ports[40];for(unsigned p=0;p<40;p++)ports[p].ch.id=p+7;
  struct slim_device device={.ctrl=&ctrl.ctrl,.laddr=addresses[a]};
  struct slim_stream_runtime stream={.dev=&device,.num_ports=count,.ports=ports};
  requests[0].msg.num_bytes=0;calls[0].live=true;
  calls[0].prep_fail=fault==1;submit_error=fault==2?-ENOMEM:0;calls[0].tx_timeout=fault==3;
  pm_result=fault==4?-EIO:0;calls[0].tid_fail=fault==5;memory_fail=fault==6;
  reply_mode=fault==7?0:3;ctrl.dma_ready=fault!=8;
  int expected=count>38?-EINVAL:fault==5||fault==6?-ENXIO:fault==4?-EIO:
    count>34?-EINVAL:fault==1?-EINVAL:fault==2?-ENOMEM:fault==3||fault==7?-ETIMEDOUT:fault==8?-ESHUTDOWN:0;
  calls[0].result=qcom_slim_ngd_disable_stream(&stream);calls[0].live=calls[0].inner_live=false;
  audit_return(expected);
  if(!expected) {
   unsigned padded=(count+8)&~3u,second=padded+1;
   check(wire_length==padded+10 && submit_calls==2,"one remove and one reconfigure message emitted");
   check(wire_trace[0]==padded && (wire_trace[2]&0x7f)==SLIM_USR_MC_CHAN_CTRL,"remove message has LTS length and opcode");
   check(wire_trace[4]==((SLIM_USR_CHAN_CTRL_REMOVE<<6)|(addresses[a]&0x1f)),"remove command preserves LTS address encoding");
   check(wire_trace[5]==1,"first request embeds its allocated TID");
   for(unsigned p=0;p<count;p++)check(wire_trace[6+p]==ports[p].ch.id,"all requested channels retained in order");
   check(wire_trace[second]==8 && (wire_trace[second+2]&0x7f)==SLIM_USR_MC_RECONFIG_NOW,"second request reconfigures manager");
   check(wire_trace[second+4]==2 && wire_trace[second+5]==addresses[a],"reconfigure payload retains LTS address dispatch");
  }
  audit_late();audit_records();
 }
 for(unsigned n=0;n<allocation_count;n++)free(allocations[n].p);
 REQUIRE(!pthread_mutex_destroy(&ctrl.tx_lock.lock));REQUIRE(!pthread_mutex_destroy(&ctrl.tx_buf_lock));REQUIRE(!pthread_mutex_destroy(&ctrl.ctrl.txn_lock));
 printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n",cases,checks,failures);return 0;
}
'''
code = code[:code.index('int main(void){')] + main
controls = [('candidate', code, False)]
for name, old, new in [
    ('remove-address-shifted', '(sdev->laddr & 0x1f)', '(sdev->laddr & 0x0f)'),
    ('reconfigure-opcode-lost', 'txn.mc = SLIM_USR_MC_RECONFIG_NOW;', 'txn.mc = SLIM_USR_MC_CHAN_CTRL;'),
    ('valid-full-message-rejected', 'rt->num_ports + 2 >', 'rt->num_ports + 7 >')]:
    assert body.count(old) == 1
    controls.append((name, code.replace(body, body.replace(old, new)), True))
rows = []
for name, text, faulty in controls:
    src = output / (name + '.c')
    src.write_text(text)
    binary = output / name
    build = subprocess.run(['clang-21', '-std=gnu11', '-O1', '-g', '-pthread', '-Wall', '-Wextra', '-Werror',
        '-Wno-unused-parameter', '-Wno-unused-function', '-Wno-sign-compare', '-Wno-missing-field-initializers',
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
        str(src), '-o', str(binary)], capture_output=True, text=True, timeout=60)
    (output / (name + '-build.log')).write_text(build.stdout + build.stderr)
    assert build.returncode == 0, build.stderr
    env = os.environ | {'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1', 'UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
    env.pop('LSAN_OPTIONS', None)
    run = subprocess.run([str(binary)], env=env, capture_output=True, text=True, timeout=30)
    (output / (name + '.stdout')).write_text(run.stdout)
    (output / (name + '.stderr')).write_text(run.stderr)
    assert run.returncode == 0, run.stderr[-2000:]
    assert not any(s in run.stderr for s in ['AddressSanitizer', 'LeakSanitizer', 'runtime error:', 'fixture invariant'])
    row = dict(name=name, **json.loads(run.stdout))
    rows.append(row)
    assert row['cases'] == 216 and (row['failures'] > 0 if faulty else row['failures'] == 0), row
report = dict(passed=True, cases=216, checks=rows[0]['checks'], failures=0, controls=rows[1:],
    actual_function_bindings=bindings, retained_LTS_caller_byte_exact=True,
    normal_LSan_and_failfast_ASan_UBSan=True, all_kernel_and_packet_services_synthetic=True,
    real_DMA_audio_firmware_phone_or_network_execution=False)
(output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(rows))
