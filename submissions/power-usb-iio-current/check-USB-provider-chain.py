#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Link actual ChipIdea callbacks, power-supply dispatch and SMBB USB control.

Two translation units retain the existing separately qualified consumer and
provider primitive substitutes. Driver functions and class dispatch functions
are extracted unchanged. Work, firmware lookup, device links, registration,
reference counts, semaphores and SPMI I/O are host simulations.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import subprocess


def definition(text, name):
    start = text.index(name)
    brace = text.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


CORE_STUBS = r'''
struct rw_semaphore {pthread_rwlock_t lock;unsigned readers;};
static void read_acquire(struct rw_semaphore *s)
{CHECK(!s->readers);CHECK(!pthread_rwlock_rdlock(&s->lock));s->readers++;}
static void read_release(struct rw_semaphore *s)
{CHECK(s->readers==1);s->readers--;CHECK(!pthread_rwlock_unlock(&s->lock));}
struct read_guard {struct rw_semaphore *sem;bool active;};
static struct read_guard make_guard(struct rw_semaphore *s)
{read_acquire(s);return (struct read_guard){s,true};}
static void drop_guard(struct read_guard *g) {read_release(g->sem);}
#define guard(kind) TEST_GUARD_##kind
#define TEST_GUARD_rwsem_read(p) struct read_guard epc_guard __attribute__((cleanup(drop_guard)))=make_guard(p)
#define scoped_guard(kind,p) for(struct read_guard extension_guard __attribute__((cleanup(drop_guard)))=make_guard(p);extension_guard.active;extension_guard.active=false)
static int atomic_read(const int *value) {return *value;}
struct power_supply;
struct power_supply_ext {
 const enum power_supply_property *properties;int num_properties;
 int (*get_property)(struct power_supply *,const struct power_supply_ext *,void *,enum power_supply_property,union power_supply_propval *);
 int (*set_property)(struct power_supply *,const struct power_supply_ext *,void *,enum power_supply_property,const union power_supply_propval *);
};
struct power_supply_ext_registration {const struct power_supply_ext *ext;void *data;};
static bool power_supply_battery_info_has_prop(void *info,enum power_supply_property p)
{(void)p;CHECK(!info);return false;}
static int power_supply_battery_info_get_prop(void *info,enum power_supply_property p,union power_supply_propval *v)
{(void)info;(void)p;(void)v;abort();}
struct power_supply_desc {
 const char *name;int type;
 const enum power_supply_property *properties;int num_properties;
 int (*get_property)(struct power_supply *,enum power_supply_property,union power_supply_propval *);
 int (*set_property)(struct power_supply *,enum power_supply_property,const union power_supply_propval *);
 int (*property_is_writeable)(struct power_supply *,enum power_supply_property);
};
struct smbb_charger;
struct power_supply {
 struct smbb_charger *data;const struct power_supply_desc *desc;
 int use_cnt;bool initialized,removing;void *battery_info;
 struct rw_semaphore epc_sem,extensions_sem;
};
static struct power_supply_ext_registration *empty_extensions(struct power_supply *p)
{CHECK(p->extensions_sem.readers==1);return NULL;}
#define power_supply_for_each_extension(reg,psy) for((reg)=empty_extensions(psy);(reg);(reg)=NULL)
#define POWER_SUPPLY_TYPE_USB 2
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
static struct mutex *active_charge_lock;
static struct rw_semaphore *active_epc_sem,*active_extension_sem;
static bool initializing;
static void bus_lock_assert(void)
{
 CHECK(initializing || (active_charge_lock && active_charge_lock->held &&
       active_epc_sem->readers==1 && !active_extension_sem->readers));
}
'''

BRIDGE = r'''
void bridge_reset(void)
{
 CHECK(!psy.epc_sem.readers && !psy.extensions_sem.readers);
 reset(false);active_charge_lock=&charger.charge_lock;
 active_epc_sem=&psy.epc_sem;active_extension_sem=&psy.extensions_sem;
 initializing=true;charger.usb_budget_managed=true;
 CHECK(smbb_usb_input_supported(&charger));
 CHECK(!smbb_usb_input_set_limit(&charger,smbb_charger_attrs[ATTR_USBIN_IMAX].min,true));
 struct smbb_charger *chg=&charger;
 DESCRIPTOR_ASSIGNMENTS
 psy.desc=&charger.usb_desc;psy.initialized=true;psy.removing=false;psy.use_cnt=1;
 initializing=false;map.operations=0;
}
int bridge_get(int *value)
{
 union power_supply_propval v={.intval=-1};
 int ret=power_supply_get_property(&psy,POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT,&v);
 if(!ret)*value=v.intval;
 CHECK(!psy.epc_sem.readers && !psy.extensions_sem.readers);
 return ret;
}
int bridge_set(int value)
{
 map.operations=0;
 union power_supply_propval v={.intval=value};
 int ret=power_supply_set_property(&psy,POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT,&v);
 CHECK(!psy.epc_sem.readers && !psy.extensions_sem.readers);
 return ret;
}
int bridge_physical_limit(void)
{
 CHECK((map.registers[SMBB_USB_SUSPEND]&~USB_SUSPEND_EN)==0xa0);
 if(map.registers[SMBB_USB_SUSPEND]&USB_SUSPEND_EN)return 0;
 unsigned selector=map.registers[SMBB_USB_IMAX];
 return selector==0?100000:selector==1?150000:selector*100000;
}
void bridge_bus_fault(unsigned at,bool after,bool persistent,unsigned drop)
{map.fail_at=at;map.fail_after_write=after;map.fail_from=persistent?at:0;map.drop_offset=drop;}
void bridge_clear_fault(void)
{map.fail_at=map.fail_from=map.drop_offset=0;map.fail_after_write=false;}
unsigned bridge_bus_operations(void) {return map.operations;}
void bridge_battery(bool present)
{map.registers[SMBB_BAT_PRES_STATUS]=present?PRES_STATUS_BAT_PRES:0;}
void bridge_lifetime(int mode)
{psy.removing=mode==1;psy.use_cnt=mode==2?0:1;}
unsigned bridge_suspend_offset(void) {return SMBB_USB_SUSPEND;}
void bridge_close(void)
{
 CHECK(!psy.epc_sem.readers && !psy.extensions_sem.readers);
 CHECK(!pthread_rwlock_destroy(&psy.epc_sem.lock));
 CHECK(!pthread_rwlock_destroy(&psy.extensions_sem.lock));
 CHECK(!pthread_mutex_destroy(&charger.charge_lock.lock));
 CHECK(!pthread_mutex_destroy(&charger.statlock.lock));
}
'''

EXTRA = r'''
    /* These cases exercise the connected pipeline, including actual class
     * removal/use-count checks. Native driver-core teardown is not executed. */
    reset();PASS(!ci_vbus_draw_init(&ci));EVENT(VBUS,1);EVENT(PULLUP,1);applied(100000);
    EVENT(CONFIG_BEGIN,1);EVENT(REQUEST,500);PASS(!complete(&ep0in,0,0));applied(500000);
    const unsigned requests[]={100,125,149,150,199,200,299,300,350,399,400,499,500,800};
    const int expected[]={100000,100000,100000,150000,150000,200000,200000,300000,300000,300000,400000,400000,500000,500000};
    for(unsigned i=0;i<sizeof(requests)/sizeof(requests[0]);i++) {
        PASS(!ci_udc_vbus_draw(&ci.gadget,requests[i]));
        flush_work(&ci.vbus_draw->work);int observed=-1;
        PASS(!bridge_get(&observed) && observed==expected[i] && bridge_physical_limit()==expected[i]);
    }
    for(unsigned at=1;at<=5;at++)for(unsigned after=0;after<2;after++) {
        bridge_bus_fault(at,after,false,0);unsigned before_warnings=warnings;
        EVENT(REQUEST,100);flush_work(&ci.vbus_draw->work);
        PASS(last_bridge_result==-EREMOTEIO && warnings==before_warnings+1);
        PASS(bridge_physical_limit()==0);
        bridge_clear_fault();EVENT(REQUEST,500);flush_work(&ci.vbus_draw->work);
        PASS(!last_bridge_result && bridge_physical_limit()==500000);
    }
    bridge_bus_fault(0,false,false,bridge_suspend_offset());
    unsigned before_warnings=warnings;EVENT(BUS_SUSPEND,1);flush_work(&ci.vbus_draw->work);
    PASS(last_bridge_result==-EIO && warnings==before_warnings+1 && bridge_physical_limit()==500000);
    bridge_clear_fault();EVENT(BUS_SUSPEND,0);flush_work(&ci.vbus_draw->work);
    bridge_battery(false);before_warnings=warnings;EVENT(BUS_SUSPEND,1);flush_work(&ci.vbus_draw->work);
    PASS(last_bridge_result==-ENODEV && warnings==before_warnings+1);
    PASS(bridge_physical_limit()==100000); /* Cannot suspend the only source. */
    bridge_battery(true);EVENT(BUS_SUSPEND,0);flush_work(&ci.vbus_draw->work);
    for(int mode=1;mode<=2;mode++) {
        bridge_lifetime(mode);before_warnings=warnings;
        EVENT(REQUEST,100);flush_work(&ci.vbus_draw->work);
        PASS(last_bridge_result==-ENODEV && !bridge_bus_operations() && warnings==before_warnings+1);
        bridge_lifetime(0);EVENT(REQUEST,500);flush_work(&ci.vbus_draw->work);
        PASS(!last_bridge_result && bridge_physical_limit()==500000);
    }
    bridge_bus_fault(1,false,true,0);before_warnings=warnings;
    EVENT(REQUEST,100);flush_work(&ci.vbus_draw->work);
    PASS(last_bridge_result==-EREMOTEIO && warnings==before_warnings+1);
    PASS(bridge_physical_limit()==500000); /* Permanent bus loss cannot prove inhibition. */
    bridge_clear_fault();EVENT(REQUEST,100);flush_work(&ci.vbus_draw->work);
    PASS(!last_bridge_result && bridge_physical_limit()==100000);
    cleanup(cleanup_data);cleanup=NULL;reset();bridge_close();
'''


def replace_once(text, before, after):
    assert text.count(before) == 1, before[:80]
    return text.replace(before, after)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel', type=Path)
    parser.add_argument('--support', type=Path, default=Path(__file__).with_name('USB-chain-support'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--negative-controls', action='store_true')
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    k, out = args.kernel.resolve(), args.output.resolve()
    out.mkdir(mode=0o700)
    smbb = (k / 'drivers/power/supply/qcom_smbb.c').read_text()
    usb = (k / 'drivers/usb/chipidea/udc.c').read_text()
    core = (k / 'drivers/power/supply/power_supply_core.c').read_text()
    provider = (args.support / 'smbb-usb-input-harness.c').read_text()
    consumer = (args.support / 'chipidea-usb-budget-harness.c').read_text()
    provider = provider[:provider.index('\nint main(void)')]
    provider = provider.replace('static unsigned cases;\n', '')
    enum = provider[provider.index('enum power_supply_property {'):provider.index('static struct smbb_charger *power_supply_get_drvdata')]
    provider = provider.replace(enum, '')
    provider = provider.replace('struct power_supply { struct smbb_charger *data; };', enum + CORE_STUBS)
    provider = provider.replace('struct mutex { pthread_mutex_t lock; };', 'struct mutex { pthread_mutex_t lock; bool held; };')
    provider = provider.replace('CHECK(!pthread_mutex_lock(&m->lock));', 'CHECK(!pthread_mutex_lock(&m->lock));CHECK(!m->held);m->held=true;')
    provider = provider.replace('CHECK(!pthread_mutex_unlock(&m->lock));', 'CHECK(m->held);m->held=false;CHECK(!pthread_mutex_unlock(&m->lock));')
    # Supply descriptor type must precede the synthetic charger structure.
    first = provider.index('struct smbb_charger {')
    last = provider.index('};', first) + 2
    charger_struct = provider[first:last]
    provider = provider[:first] + provider[last:]
    charger_struct = charger_struct.replace('    unsigned attr[_ATTR_CNT];', '    unsigned attr[_ATTR_CNT];\n    struct power_supply_desc usb_desc;')
    marker = 'static struct smbb_charger *power_supply_get_drvdata'
    provider = provider.replace(marker, charger_struct + '\n' + marker, 1)
    provider = provider.replace('    unsigned offset = register_offset(address);', '    bus_lock_assert();unsigned offset = register_offset(address);')
    provider = provider.replace('{ PTHREAD_MUTEX_INITIALIZER }', '{ .lock=PTHREAD_MUTEX_INITIALIZER }')
    provider = provider.replace('static struct power_supply psy = { .data = &charger };',
        'static struct power_supply psy = { .data=&charger, .epc_sem={.lock=PTHREAD_RWLOCK_INITIALIZER}, .extensions_sem={.lock=PTHREAD_RWLOCK_INITIALIZER} };')
    definitions = '\n'.join(re.findall(r'^#define (?:SMBB_\w+|STATUS_\w+|USB_TYPE_CHGPTH|USB_SUBTYPE_SMBP|USB_SUSPEND_EN|PRES_STATUS_BAT_PRES)\s+[^\n]+$', smbb, re.M))
    definitions += '\n' + smbb[smbb.index('enum smbb_attr {'):smbb.index('struct smbb_charger {')]
    provider = provider.replace('#include "driver-definitions.h"', definitions)
    functions = smbb[smbb.index('static int smbb_vbat_weak_fn('):smbb.index('static int smbb_charger_attr_read(')]
    for name in ['smbb_usb_input_supported', 'smbb_usb_input_suspend', 'smbb_usb_input_get_limit',
                 'smbb_usb_input_set_limit', 'smbb_usbin_get_property', 'smbb_usbin_set_property',
                 'smbb_charger_writable_property', 'smbb_usbin_writable_property']:
        functions += definition(smbb, 'static int ' + name + '(') + '\n' if name != 'smbb_usb_input_supported' else definition(smbb, 'static bool ' + name + '(') + '\n'
    for name in ['static enum power_supply_property smbb_charger_properties[] =',
                 'static enum power_supply_property smbb_usb_input_properties[] =',
                 'static const struct power_supply_desc usb_psy_desc =']:
        functions += definition(smbb, name) + ';\n'
    for name in ['static bool psy_desc_has_property(', 'bool power_supply_ext_has_property(',
                 'static int __power_supply_get_property(', 'int power_supply_get_property(',
                 'static int __power_supply_set_property(', 'int power_supply_set_property(']:
        functions += definition(core, name) + '\n'
    provider = provider.replace('#include "driver-functions.c"', functions)
    assignments = smbb[smbb.index('\tchg->usb_desc = usb_psy_desc;'):smbb.index('\n\tusb_cfg.drv_data = chg;')]
    provider += BRIDGE.replace('DESCRIPTOR_ASSIGNMENTS', assignments)
    prototypes = '\n'.join(['void bridge_reset(void);', 'int bridge_get(int *);', 'int bridge_set(int);',
        'int bridge_physical_limit(void);', 'void bridge_bus_fault(unsigned,bool,bool,unsigned);',
        'void bridge_clear_fault(void);', 'unsigned bridge_bus_operations(void);',
        'void bridge_battery(bool);', 'void bridge_lifetime(int);', 'void bridge_close(void);',
        'unsigned bridge_suspend_offset(void);', 'static int last_bridge_result;']) + '\n'
    consumer = consumer.replace('typedef bool spinlock_t;', prototypes + 'typedef bool spinlock_t;')
    consumer = consumer.replace('programmed[64]', 'programmed[512]')
    consumer = replace_once(consumer, '    limit->intval = 100000;\n    return read_error;',
                            '    return read_error?read_error:bridge_get(&limit->intval);')
    consumer = replace_once(consumer, '    return write_error;', '''    if(write_error)return write_error;
    last_bridge_result=bridge_set(limit->intval);
    if(!last_bridge_result) {
        int observed=-1;CHECK(!bridge_get(&observed));
        int expected=limit->intval==0?0:limit->intval<150000?100000:limit->intval<200000?150000:(limit->intval/100000)*100000;
        CHECK(observed==expected && bridge_physical_limit()==expected);
    }
    return last_bridge_result;''')
    consumer = replace_once(consumer, 'static void reset(void)\n{', 'static void reset(void)\n{\n    bridge_reset();')
    block = usb[usb.index('enum ci_vbus_draw_event {'):usb.index('/**\n * isr_reset_handler:', usb.index('enum ci_vbus_draw_event {'))]
    for name in ['static int ci_udc_vbus_draw(', 'static int isr_tr_complete_low(']:
        block += definition(usb, name)
    consumer = consumer.replace('#include "driver-functions.c"', block)
    consumer = replace_once(consumer, '    printf("USB_BUDGET_CASES %u\\n", cases);',
                            EXTRA + '    printf("USB_PROVIDER_CHAIN_CASES %u\\n", cases);')
    variants = [('candidate', provider, consumer)]
    if args.negative_controls:
        variants += [('wrong-budget-units', provider, replace_once(consumer, '.intval = ma * 1000', '.intval = ma')),
                     ('missing-core-removal-check', provider.replace('if (psy->removing)', 'if (false)'), consumer),
                     ('missing-suspend-readback', replace_once(provider,
                      'return (reg & USB_SUSPEND_EN) == value ? 0 : -EIO;', 'return 0;'), consumer)]
    record = {'started_UTC': datetime.now(timezone.utc).isoformat(), 'variants': [],
              'actual_ChipIdea_power_supply_class_and_SMBB_callbacks_linked': True,
              'actual_power_supply_registration_driver_core_USB_workqueue_or_hardware_executed': False,
              'source_SHA256': {p: hashlib.sha256((k / p).read_bytes()).hexdigest() for p in [
                  'drivers/usb/chipidea/udc.c', 'drivers/power/supply/qcom_smbb.c',
                  'drivers/power/supply/power_supply_core.c']},
              'checker_SHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'support_SHA256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted(args.support.glob('*.c'))},
              'phone_access': False}
    try:
        for name, pcode, ccode in variants:
            p, c, binary = out / (name + '-provider.c'), out / (name + '-consumer.c'), out / name
            p.write_text(pcode);c.write_text(ccode)
            compile_run = subprocess.run(['clang', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-sign-compare',
                '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                '-pthread', str(p), str(c), '-o', str(binary)], capture_output=True, timeout=60)
            (out / (name + '-compile.stdout')).write_bytes(compile_run.stdout)
            (out / (name + '-compile.stderr')).write_bytes(compile_run.stderr)
            assert compile_run.returncode == 0, name
            run = subprocess.run([str(binary)], capture_output=True, timeout=20,
                env=os.environ | {'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
            (out / (name + '.stdout')).write_bytes(run.stdout)
            (out / (name + '.stderr')).write_bytes(run.stderr)
            if name == 'candidate':
                assert run.returncode == 0 and not run.stderr, name
                match = re.fullmatch(rb'USB_PROVIDER_CHAIN_CASES (\d+)\n', run.stdout)
                assert match
                record['cases'] = int(match[1])
            else:
                assert run.returncode == 1 and run.stderr and b'ERROR: AddressSanitizer' not in run.stderr, name
                expected = {'wrong-budget-units': b'programmed[0] == 100000',
                            'missing-core-removal-check': b'!bridge_bus_operations()',
                            'missing-suspend-readback': b'observed==expected && bridge_physical_limit()==expected'}[name]
                assert expected in run.stderr, name
            record['variants'].append({'name':name,'returncode':run.returncode,'expected_result_verified':True,
                'provider_C_SHA256':hashlib.sha256(pcode.encode()).hexdigest(),
                'consumer_C_SHA256':hashlib.sha256(ccode.encode()).hexdigest()})
        record['passed'] = True
    finally:
        record['finished_UTC'] = datetime.now(timezone.utc).isoformat()
        (out / 'qualification.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
