"""Execute actual NXP NCI teardown with pending-IRQ and close-callback probes."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(os.environ.get('FX0_NFC_TEARDOWN_SOURCE', ROOT/'worktrees/linux-fx0-nfc-teardown'))


def function(text,name):
    match=re.search(r'^(?:static )?(?:int|void) '+re.escape(name)+r'\([^;]*?\)\n\{',text,re.M)
    if not match:raise ValueError('Missing actual function: '+name)
    end=text.index('{',match.start())+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[match.start():end]+'\n'


PREFIX=r'''
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do {if(!(x)){fprintf(stderr,"%d: %s\n",__LINE__,#x);exit(1);}}while(0)
#define ESHUTDOWN 108
enum nxp_nci_mode {NXP_NCI_MODE_COLD,NXP_NCI_MODE_NCI,NXP_NCI_MODE_FW};
struct clk {int votes;};
struct gpio_desc {int value;};
struct nci_dev;
struct i2c_client {int irq;void *data;};
struct nxp_nci_i2c_phy {struct i2c_client *i2c_dev;struct nci_dev *ndev;struct gpio_desc *gpiod_fw,*gpiod_en;struct clk *ref_clk;bool ref_clk_enabled;int hard_fault;};
struct nxp_nci_phy_ops {int (*set_mode)(void *,enum nxp_nci_mode);};
struct nxp_nci_fw_info {int work;};
struct nxp_nci_info {void *phy_id;const struct nxp_nci_phy_ops *phy_ops;enum nxp_nci_mode mode;int info_lock;struct nxp_nci_fw_info fw_info;};
struct nci_dev {struct nxp_nci_info *info;};
static bool irq_registered,freed,up;
static int irq_drained,unregistered,closed,fw_completed,work_drained;
static char events[128];
static void event(char code) {size_t n=strlen(events);CHECK(n+1<sizeof(events));events[n]=code;events[n+1]=0;}
static void mutex_lock(int *lock) {CHECK(!*lock);*lock=1;}
static void mutex_unlock(int *lock) {CHECK(*lock==1);*lock=0;}
static struct nxp_nci_info *nci_get_drvdata(struct nci_dev *d) {CHECK(!freed);return d->info;}
static int clk_prepare_enable(struct clk *clk) {if(clk){CHECK(!clk->votes);clk->votes++;}return 0;}
static void clk_disable_unprepare(struct clk *clk) {if(clk){CHECK(clk->votes==1);clk->votes--;}}
static void gpiod_set_value_cansleep(struct gpio_desc *gpio,int value) {if(gpio)gpio->value=value;}
static void usleep_range(int minimum,int maximum) {CHECK(minimum==10000 && maximum==15000);}
'''

MIDDLE=r'''
static void nxp_nci_fw_work_complete(struct nxp_nci_info *info,int error) {
 CHECK(error==-ESHUTDOWN && !freed);fw_completed++;event('F');
 if(info->phy_ops->set_mode)CHECK(!info->phy_ops->set_mode(info->phy_id,NXP_NCI_MODE_COLD));
 info->mode=NXP_NCI_MODE_COLD;
}
static void cancel_work_sync(int *work) {(void)work;CHECK(!freed);work_drained++;event('W');}
static void nci_unregister_device(struct nci_dev *d) {
 CHECK(!freed && !d->info->info_lock);event('U');unregistered++;
 /* NCI unregister calls ops->close while UP; close takes info_lock itself. */
 if(up){CHECK(!nxp_nci_close(d));closed++;up=false;}
 /* Its queue flush can also wait for callbacks needing the same mutex. */
 mutex_lock(&d->info->info_lock);mutex_unlock(&d->info->info_lock);
}
static void nci_free_device(struct nci_dev *d) {
 CHECK(!freed && !irq_registered && unregistered==1 && !d->info->info_lock);
 CHECK(d->info->mode==NXP_NCI_MODE_COLD);freed=true;event('D');
}
static void *i2c_get_clientdata(struct i2c_client *c) {return c->data;}
static void free_irq(int irq,void *data) {
 struct nxp_nci_i2c_phy *phy=data;CHECK(irq==42 && irq_registered && !freed);
 /* Drain a pending threaded callback while its NCI/driver data still exists. */
 struct nxp_nci_info *info=nci_get_drvdata(phy->ndev);mutex_lock(&info->info_lock);mutex_unlock(&info->info_lock);
 irq_registered=false;irq_drained++;event('I');
}
'''

MAIN=r'''
int main(int argc,char **argv) {
 CHECK(argc==2);struct clk clock={0};struct gpio_desc en={0},fw={0};
 struct nxp_nci_i2c_phy phy={.gpiod_en=&en,.gpiod_fw=&fw,.ref_clk=&clock};
 struct nxp_nci_phy_ops ops={.set_mode=nxp_nci_i2c_set_mode};
 struct nxp_nci_info info={.phy_id=&phy,.phy_ops=&ops,.mode=NXP_NCI_MODE_COLD};
 struct nci_dev dev={.info=&info};struct i2c_client client={.irq=42,.data=&phy};phy.ndev=&dev;phy.i2c_dev=&client;
 bool direct=!strncmp(argv[1],"core_",5);
 if(strstr(argv[1],"open")){up=true;info.mode=NXP_NCI_MODE_NCI;clock.votes=1;phy.ref_clk_enabled=true;en.value=1;}
 if(strstr(argv[1],"firmware")){info.mode=NXP_NCI_MODE_FW;clock.votes=1;phy.ref_clk_enabled=true;en.value=fw.value=1;}
 if(strstr(argv[1],"legacy"))ops.set_mode=NULL;
 irq_registered=!direct;
 if(direct)nxp_nci_remove(&dev);else nxp_nci_i2c_remove(&client);
 CHECK(freed && !irq_registered && unregistered==1 && work_drained==1 && !info.info_lock);
 CHECK(!clock.votes && !phy.ref_clk_enabled && !en.value && !fw.value);
 CHECK(info.mode==NXP_NCI_MODE_COLD && closed==(strstr(argv[1],"open")!=NULL));
 CHECK(fw_completed==(strstr(argv[1],"firmware")!=NULL));
 if(!direct)CHECK(irq_drained==1 && events[0]=='I');
 CHECK(events[strlen(events)-1]=='D');puts("actual NXP NCI teardown callbacks and IRQ lifetime pass");return 0;
}
'''


class NxpNciTeardownTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();base=Path(cls.tmp.name)
        i2c=(SOURCE/'drivers/nfc/nxp-nci/i2c.c').read_text();core=(SOURCE/'drivers/nfc/nxp-nci/core.c').read_text()
        code=PREFIX+function(i2c,'nxp_nci_i2c_set_mode')+function(core,'nxp_nci_close')+MIDDLE+function(core,'nxp_nci_remove')+function(i2c,'nxp_nci_i2c_remove')+MAIN
        p=base/'teardown.c';p.write_text(code);cls.binary=base/'teardown'
        subprocess.run(['cc','-std=gnu11','-O2','-Wall','-Wextra','-Werror',str(p),'-o',str(cls.binary)],check=True,capture_output=True,text=True)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def check_mode(self,mode):
        p=subprocess.run([str(self.binary),mode],capture_output=True,text=True,timeout=5)
        self.assertEqual(p.returncode,0,p.stderr)

    def test_pending_IRQ_drains_before_NCI_state_is_freed(self):
        for mode in ['cold','open','firmware']:
            with self.subTest(mode=mode):self.check_mode(mode)

    def test_unregister_close_and_flush_callbacks_do_not_reenter_held_mutex(self):
        for mode in ['core_cold','core_open','core_firmware','core_legacy']:
            with self.subTest(mode=mode):self.check_mode(mode)


if __name__=='__main__':unittest.main()
