// SPDX-License-Identifier: GPL-2.0-only
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <errno.h>
#include <setjmp.h>
#include <stdarg.h>
typedef uint32_t u32;
#define BIT(n) (1U<<(n))
#define GENMASK(h,l) ((~0U<<(l))&(~0U>>(31-(h))))
#define MAX_UV 1337500
static int cases,checks,failures,panics,ops,fault_step,fault_kind,cache_skips;
static bool catching,corrupt_parent_on_mx,extra_pll_ref;
static jmp_buf fatal;
#define CHECK(x) do {checks++;if (!(x)) {if(failures++<16)fprintf(stderr,"%d: %s\n",__LINE__,#x);}}while(0)
static void model_panic(const char *fmt,...) {panics++;if(!catching){fprintf(stderr,"unexpected fatal: %s\n",fmt);exit(2);}longjmp(fatal,1);}
#define panic(...) model_panic(__VA_ARGS__)
struct regulator {int kind,request,voltage,refs,acks;};
struct clk;
struct clk_hw {struct clk *clock;};
struct clk {unsigned long rate;struct clk *parent;struct clk_hw hw;int exclusive,enabled,prepared;};
struct regmap {u32 cmd,cfg;};
static struct regulator *apc,*mx,*so;
static struct clk *cpuclk,*auxclk,*pllclk,*gpll;
static struct regmap *mux;
static bool quiescent=true,local_irqs=true;
static int fault(void) {ops++;return ops==fault_step?fault_kind:0;}
static void context(void) {CHECK(quiescent&&local_irqs);}
static struct clk *clk_get_parent(struct clk *c) {context();return c->parent;}
static unsigned long clk_get_rate(struct clk *c) {context();return fault()?0:c->rate;}
static struct clk_hw *__clk_get_hw(struct clk *c) {return &c->hw;}
static bool clk_hw_is_prepared(const struct clk_hw *h) {return h->clock->prepared;}
static unsigned int __clk_get_enable_count(struct clk *c) {return c->enabled;}
static int clk_rate_exclusive_get(struct clk *c) {context();if(fault())return -EBUSY;CHECK(!c->exclusive);c->exclusive++;return 0;}
static void clk_rate_exclusive_put(struct clk *c) {context();CHECK(c->exclusive==1);c->exclusive--;}
static int regulator_get_voltage(struct regulator *r) {context();if(fault())return -EIO;return r->kind==0?r->voltage:r->request;}
static int regulator_set_voltage(struct regulator *r,int low,int high) {
 context();CHECK(low>0&&low<=high);int f=fault();int old=r->request;
 if(f==1)return -EIO;
 r->request=low;
 if(low!=old) {r->voltage=low;r->acks++;}else cache_skips++;
 if(r==apc)CHECK(mx->voltage>=apc->voltage);
 if(r==mx) {CHECK(mx->voltage>=apc->voltage);if(corrupt_parent_on_mx&&low==MAX_UV)gpll->rate=800000000;}
 if(f==2) {r->request=old;return -EIO;}
 return 0;
}
static int regulator_sync_voltage(struct regulator *r) {
 context();int f=fault();if(f==1)return -EIO;
 r->voltage=r->request;r->acks++;
 if(r==apc)CHECK(mx->voltage>=apc->voltage&&mx->acks);
 if(r==mx)CHECK(mx->voltage>=apc->voltage);
 return f==2?-EIO:0;
}
static int regulator_enable(struct regulator *r) {context();if(fault())return -EIO;r->refs++;return 0;}
static int clk_set_rate(struct clk *c,unsigned long rate) {
 context();CHECK(c==cpuclk&&c->exclusive==1);CHECK(gpll->rate==600000000&&auxclk->rate==600000000);
 CHECK(mx->voltage==MAX_UV&&apc->voltage==MAX_UV&&so->request==MAX_UV&&apc->acks&&mx->acks);
 int f=fault();if(f==1)return -EIO;if(f==3)return 0;
 c->rate=rate;mux->cmd=0;mux->cfg=rate==300000000?(4<<8|3):(rate==600000000?(4<<8|1):(5<<8|1));
 pllclk->rate=rate>600000000?rate:pllclk->rate;
 pllclk->enabled=pllclk->prepared=(rate!=300000000&&rate!=600000000)||extra_pll_ref;
 return f==2?-EIO:0;
}
static int regmap_read(struct regmap *m,u32 off,u32 *value) {context();CHECK(m==mux&&(off==0x50||off==0x54));if(fault())return -EIO;*value=off==0x50?m->cmd:m->cfg;return 0;}
