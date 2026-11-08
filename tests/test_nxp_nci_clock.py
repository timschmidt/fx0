"""Execute actual NXP NCI mode/open/close code with instrumented clock/GPIO ops."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('FX0_NFC_SOURCE', ROOT / 'worktrees/linux-fx0-nfc'))


def function(text, name):
    match = re.search(r'^static int ' + re.escape(name) + r'\([^;]*?\)\n\{', text, re.M)
    if not match:
        raise ValueError('Missing function: ' + name)
    end = text.index('{', match.start()) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[match.start():end] + '\n'


HARNESS = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define EBUSY 16
#define CHECK(x) do {if(!(x)){fprintf(stderr,"%d: %s\n",__LINE__,#x);exit(1);}}while(0)
enum nxp_nci_mode {NXP_NCI_MODE_COLD,NXP_NCI_MODE_NCI,NXP_NCI_MODE_FW};
struct clk {int votes,error;};
struct gpio_desc {char name;int value;};
struct i2c_client;
struct nci_dev;
struct nxp_nci_i2c_phy {struct i2c_client *i2c_dev;struct nci_dev *ndev;struct clk *ref_clk;bool ref_clk_enabled;struct gpio_desc *gpiod_fw,*gpiod_en;int hard_fault;};
struct nxp_nci_phy_ops {int (*set_mode)(void *,enum nxp_nci_mode);};
struct nxp_nci_info {void *phy_id;const struct nxp_nci_phy_ops *phy_ops;enum nxp_nci_mode mode;int info_lock;};
struct nci_dev {struct nxp_nci_info *info;};
static char events[256];
static void event(char code) {size_t n=strlen(events);CHECK(n+1<sizeof(events));events[n]=code;events[n+1]=0;}
static int clk_prepare_enable(struct clk *clk) {if(!clk)return 0;event('C');if(clk->error)return clk->error;clk->votes++;return 0;}
static void clk_disable_unprepare(struct clk *clk) {if(!clk)return;CHECK(clk->votes==1);clk->votes--;event('c');}
static void gpiod_set_value_cansleep(struct gpio_desc *gpio,int value) {if(!gpio)return;gpio->value=value;event(gpio->name);event(value?'1':'0');}
static void usleep_range(int minimum,int maximum) {CHECK(minimum==10000 && maximum==15000);event('s');}
static struct nxp_nci_info *nci_get_drvdata(struct nci_dev *device) {return device->info;}
static void mutex_lock(int *lock) {CHECK(!*lock);*lock=1;}
static void mutex_unlock(int *lock) {CHECK(*lock==1);*lock=0;}
'''

PROBE = r'''
#define ENODEV 19
#define ENOMEM 12
#define GFP_KERNEL 0
#define I2C_FUNC_I2C 1
#define GPIOD_OUT_LOW 0
#define IRQF_TRIGGER_RISING 1
#define IRQF_ONESHOT 0x2000
#define NXP_NCI_I2C_MAX_PAYLOAD 32
#define NXP_NCI_I2C_DRIVER_NAME "test"
#define IS_ERR(p) ((uintptr_t)(p)>=(uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define nfc_err(...) ((void)0)
#define dev_dbg(...) ((void)0)
#define ACPI_COMPANION(dev) (acpi)
struct device {int dummy;};
struct i2c_client {struct device dev;void *adapter,*data;int irq;};
static bool acpi;
static int lookup_error,irq_error,gpio_gets,registered,removed;
static int acpi_nxp_nci_gpios[1];
static unsigned long trigger_type=1,requested_flags;
static struct clk probe_clock;
static struct gpio_desc probe_fw={'f',0},probe_en={'e',0};
static struct nxp_nci_i2c_phy probe_phy;
static struct nxp_nci_info probe_info;
static struct nci_dev probe_device={.info=&probe_info};
static const struct nxp_nci_phy_ops i2c_phy_ops={.set_mode=nxp_nci_i2c_set_mode};
static bool i2c_check_functionality(void *adapter,int kind) {CHECK(kind==1);return adapter!=NULL;}
static void *devm_kzalloc(struct device *dev,size_t size,int flags) {(void)dev;(void)flags;CHECK(size==sizeof(probe_phy));memset(&probe_phy,0,size);return &probe_phy;}
static void i2c_set_clientdata(struct i2c_client *client,void *data) {client->data=data;}
static struct clk *devm_clk_get_optional(struct device *dev,const char *name) {(void)dev;CHECK(!strcmp(name,"ref"));return lookup_error?(struct clk *)(intptr_t)lookup_error:&probe_clock;}
static int dev_err_probe(struct device *dev,int error,const char *message) {(void)dev;(void)message;return error;}
static int devm_acpi_dev_add_driver_gpios(struct device *dev,int *mapping) {(void)dev;(void)mapping;return 0;}
static struct gpio_desc *devm_gpiod_get(struct device *dev,const char *name,int flags) {(void)dev;CHECK(!strcmp(name,"enable") && !flags);gpio_gets++;probe_en.value=0;return &probe_en;}
static struct gpio_desc *devm_gpiod_get_optional(struct device *dev,const char *name,int flags) {(void)dev;CHECK(!strcmp(name,"firmware") && !flags);gpio_gets++;probe_fw.value=0;return &probe_fw;}
static int nxp_nci_probe(void *phy,struct device *dev,const struct nxp_nci_phy_ops *ops,unsigned int payload,struct nci_dev **ndev) {
 (void)dev;CHECK(payload==32);CHECK(!ops->set_mode(phy,NXP_NCI_MODE_COLD));
 probe_info=(struct nxp_nci_info){.phy_id=phy,.phy_ops=ops,.mode=NXP_NCI_MODE_COLD};*ndev=&probe_device;registered++;return 0;
}
static void nxp_nci_remove(struct nci_dev *dev) {CHECK(dev==&probe_device && registered==1);CHECK(!nxp_nci_close(dev));registered--;removed++;}
static unsigned long irq_get_trigger_type(int irq) {CHECK(irq==42);return trigger_type;}
static int nxp_nci_i2c_irq_thread_fn(int irq,void *phy) {(void)irq;(void)phy;return 0;}
static int request_threaded_irq(int irq,void *handler,int (*thread)(int,void *),unsigned long flags,const char *name,void *phy) {
 CHECK(irq==42 && !handler && thread==nxp_nci_i2c_irq_thread_fn && !strcmp(name,"test") && phy==&probe_phy);requested_flags=flags;return irq_error;
}
'''

MAIN = r'''
int main(int argc,char **argv) {
 CHECK(argc==2);
 struct clk clk={0};struct gpio_desc fw={'f',0},en={'e',0};
 struct nxp_nci_i2c_phy phy={.ref_clk=&clk,.gpiod_fw=&fw,.gpiod_en=&en,.hard_fault=-5};
 const struct nxp_nci_phy_ops ops={.set_mode=nxp_nci_i2c_set_mode};
 struct nxp_nci_info info={.phy_id=&phy,.phy_ops=&ops,.mode=NXP_NCI_MODE_COLD};
 struct nci_dev device={.info=&info};
 if(!strcmp(argv[1],"cycle")) {
  CHECK(!nxp_nci_i2c_set_mode(&phy,NXP_NCI_MODE_COLD));CHECK(!strcmp(events,"f0e0s") && !clk.votes && !phy.ref_clk_enabled && !phy.hard_fault);
  events[0]=0;CHECK(!nxp_nci_open(&device));CHECK(!strcmp(events,"Cf0e1s") && clk.votes==1 && phy.ref_clk_enabled && info.mode==NXP_NCI_MODE_NCI);
  events[0]=0;CHECK(nxp_nci_open(&device)==-EBUSY && !*events && clk.votes==1);
  CHECK(!nxp_nci_i2c_set_mode(&phy,NXP_NCI_MODE_FW));CHECK(!strcmp(events,"f1e1s") && clk.votes==1);
  events[0]=0;CHECK(!nxp_nci_i2c_set_mode(&phy,NXP_NCI_MODE_NCI));CHECK(!strcmp(events,"f0e1s") && clk.votes==1);
  events[0]=0;CHECK(!nxp_nci_close(&device));CHECK(!strcmp(events,"f0e0sc") && !clk.votes && !phy.ref_clk_enabled && info.mode==NXP_NCI_MODE_COLD);
  events[0]=0;CHECK(!nxp_nci_close(&device));CHECK(!strcmp(events,"f0e0s") && !clk.votes);
 } else if(!strcmp(argv[1],"failure_retry")) {
  clk.error=-5;CHECK(nxp_nci_open(&device)==-5);CHECK(info.mode==NXP_NCI_MODE_COLD && !phy.ref_clk_enabled && !clk.votes && !fw.value && !en.value && !info.info_lock && !strcmp(events,"C"));
  clk.error=0;events[0]=0;CHECK(!nxp_nci_open(&device));CHECK(info.mode==NXP_NCI_MODE_NCI && clk.votes==1 && !strcmp(events,"Cf0e1s"));
  CHECK(!nxp_nci_close(&device));CHECK(!clk.votes && !phy.ref_clk_enabled);
 } else if(!strcmp(argv[1],"legacy_no_clock")) {
  phy.ref_clk=NULL;CHECK(!nxp_nci_open(&device));CHECK(!strcmp(events,"f0e1s") && !clk.votes);
  events[0]=0;CHECK(!nxp_nci_close(&device));CHECK(!strcmp(events,"f0e0s") && !clk.votes && !phy.ref_clk_enabled);
 } else if(!strcmp(argv[1],"missing_firmware_pin")) {
  phy.gpiod_fw=NULL;CHECK(!nxp_nci_open(&device));CHECK(!strcmp(events,"Ce1s") && clk.votes==1);
  events[0]=0;CHECK(!nxp_nci_close(&device));CHECK(!strcmp(events,"e0sc") && !clk.votes);
 } else if(!strcmp(argv[1],"firmware_clock_failure")) {
  clk.error=-517;CHECK(nxp_nci_i2c_set_mode(&phy,NXP_NCI_MODE_FW)==-517);
  CHECK(!strcmp(events,"C") && !clk.votes && !phy.ref_clk_enabled && !fw.value && !en.value);
  events[0]=0;CHECK(!nxp_nci_i2c_set_mode(&phy,NXP_NCI_MODE_COLD));CHECK(!strcmp(events,"f0e0s") && !clk.votes && !phy.hard_fault);
 } else if(!strncmp(argv[1],"probe_",6)) {
  struct i2c_client client={.adapter=&clk,.irq=42};
  if(!strcmp(argv[1],"probe_defer"))lookup_error=-517;
  else if(!strcmp(argv[1],"probe_irq_failure"))irq_error=-16;
  else if(!strcmp(argv[1],"probe_DT"))trigger_type=2;
  else if(!strcmp(argv[1],"probe_ACPI")){acpi=true;trigger_type=4;}
  else CHECK(0);
  int result=nxp_nci_i2c_probe(&client);
  if(lookup_error)CHECK(result==-517 && !gpio_gets && !registered && !removed && !*events);
  else if(irq_error)CHECK(result==-16 && gpio_gets==2 && !registered && removed==1 && !probe_clock.votes && !probe_phy.ref_clk_enabled);
  else {CHECK(!result && registered==1 && !removed && requested_flags==(IRQF_ONESHOT|(acpi?1:2)) && !probe_en.value && !probe_fw.value && !probe_clock.votes);nxp_nci_remove(probe_phy.ndev);CHECK(!registered && removed==1);}
 } else CHECK(0);
 CHECK(!info.info_lock);puts("actual NXP NCI clock/mode transitions pass");return 0;
}
'''


class NxpNciClockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        base = Path(cls.directory.name)
        code = HARNESS + function((SOURCE / 'drivers/nfc/nxp-nci/i2c.c').read_text(), 'nxp_nci_i2c_set_mode')
        core = (SOURCE / 'drivers/nfc/nxp-nci/core.c').read_text()
        code += function(core, 'nxp_nci_open') + function(core, 'nxp_nci_close')
        code += PROBE + function((SOURCE / 'drivers/nfc/nxp-nci/i2c.c').read_text(), 'nxp_nci_i2c_probe') + MAIN
        source = base / 'clock.c'
        source.write_text(code)
        cls.binary = base / 'clock'
        subprocess.run(['cc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-function', str(source), '-o', str(cls.binary)],
                       check=True, capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def check_mode(self, mode):
        result = subprocess.run([str(self.binary), mode], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_clock_and_GPIO_order_balanced_across_modes(self):
        self.check_mode('cycle')

    def test_clock_failure_leaves_cold_state_and_allows_retry(self):
        self.check_mode('failure_retry')

    def test_legacy_optional_clock_and_firmware_GPIO(self):
        self.check_mode('legacy_no_clock')
        self.check_mode('missing_firmware_pin')

    def test_firmware_clock_failure_does_not_raise_enable_or_mode(self):
        self.check_mode('firmware_clock_failure')

    def test_clock_provider_defer_precedes_GPIO_claims_or_NCI_registration(self):
        self.check_mode('probe_defer')

    def test_IRQ_failure_unregisters_the_already_registered_NCI_device(self):
        self.check_mode('probe_irq_failure')

    def test_DT_trigger_is_preserved_and_ACPI_override_is_retained(self):
        self.check_mode('probe_DT')
        self.check_mode('probe_ACPI')


if __name__ == '__main__':
    unittest.main()
