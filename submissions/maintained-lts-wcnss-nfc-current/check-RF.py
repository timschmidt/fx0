# SPDX-License-Identifier: GPL-2.0-only
"""Execute the actual RF classification block against synthetic OF matching."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';E=R/'worktrees/linux-fx0-cpu-current-01';ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=C);ap.add_argument('--output',type=Path,default=N/'RF-01');ap.add_argument('--experimental',type=Path);args=ap.parse_args();C=args.source;O=args.output;O.mkdir();path='drivers/net/wireless/ath/wcn36xx/main.c';source=(C/path).read_text();start=source.index('\tif (iris_node) {',source.index('/* External RF module */'));i=source.index('{',start)+1;depth=1
while depth:depth+=(source[i]=='{')-(source[i]=='}');i+=1
block=source[start:i];assert args.experimental is None or block in (args.experimental/path).read_text();header=(C/'drivers/net/wireless/ath/wcn36xx/wcn36xx.h').read_text();macros='\n'.join(l for l in header.splitlines() if re.match(r'#define RF_IRIS_WCN\d+\s',l));assert macros.count('#define')==3
head='''// SPDX-License-Identifier: ISC
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
struct device_node { const char *compatible; };
struct wcn36xx { unsigned int rf_id; };
static unsigned int released;
static bool of_device_is_compatible(struct device_node *n, const char *compat) { return !strcmp(n->compatible, compat); }
static void of_node_put(struct device_node *n) { (void)n; released++; }
'''+macros+'\nstatic void classify(struct wcn36xx *wcn, struct device_node *iris_node)\n{\n'
tail='''
}
int main(void) {
 const struct { const char *compatible; unsigned int expected; } cases[] = {
 {"qcom,wcn3620",RF_IRIS_WCN3620},{"qcom,wcn3660",RF_IRIS_WCN3660},
 {"qcom,wcn3660a",RF_IRIS_WCN3660},{"qcom,wcn3660b",RF_IRIS_WCN3660},
 {"qcom,wcn3680",RF_IRIS_WCN3680},{"unknown",0xdead},{NULL,0xdead}};
 unsigned int failures=0;
 for (unsigned int i=0; i<7; i++) {
  struct device_node node={cases[i].compatible};struct wcn36xx wcn={0xdead};released=0;
  classify(&wcn,cases[i].compatible?&node:NULL);
  failures += wcn.rf_id!=cases[i].expected || released!=(cases[i].compatible!=NULL);
 }
 printf("{\\"cases\\":7,\\"failures\\":%u}\\n",failures);return failures?1:0;
}
''';rows=[]
for mutant in [False,True]:
 code=head+(block.replace('"qcom,wcn3660a"','"qcom,wcn3660a-missing"')+'\n if (iris_node && of_device_is_compatible(iris_node,"qcom,wcn3660a")) wcn->rf_id=RF_IRIS_WCN3680;' if mutant else block)+tail;out=O/('wrong-3680' if mutant else 'candidate');out.mkdir();(out/'tmp').mkdir();p=out/'model.c';p.write_text(code);cmd=['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(p),'-o',str(out/'model')];r=subprocess.run(cmd,capture_output=True,text=True);(out/'compile.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr;r=subprocess.run([str(out/'model')],capture_output=True,text=True,env=os.environ|{'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1','TMPDIR':str(out/'tmp')});(out/'run.log').write_text(r.stdout+r.stderr);d=json.loads(r.stdout);assert not r.stderr and d['failures']==int(mutant) and r.returncode==int(mutant);rows.append(dict(mutant=mutant,cases=7,failures=d['failures'],fixture_SHA256=hashlib.sha256(p.read_bytes()).hexdigest()))
(O/'qualification.json').write_text(json.dumps(dict(passed=True,rows=rows,source_SHA256=hashlib.sha256((C/path).read_bytes()).hexdigest(),source_block_SHA256=hashlib.sha256(block.encode()).hexdigest(),actual_RF_classification_block_executed=True,OF_node_services_modeled=True,full_probe_or_radio_execution=False),indent=2)+'\n');print(json.dumps(rows))
