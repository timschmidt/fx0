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
typedef uint16_t u16;
typedef uint8_t u8;
typedef uint64_t u64;
#define BIT(n) (1U<<(n))
#define U32_MAX UINT32_MAX
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define do_div(n,b) ((n)/=(b))
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
struct regmap { u32 regs[32];int reads,writes,drop_at,error_at,corrupt_read_at,read_error_at;bool apply_error,lock;int unsafe_program; };
struct clk_hw { const char *name; };
struct clk_regmap { struct clk_hw hw;struct regmap *regmap; };
struct clk_rate_request { unsigned long rate,best_parent_rate; };
struct clk_ops { int (*prepare)(struct clk_hw *);void (*unprepare)(struct clk_hw *);int (*enable)(struct clk_hw *);void (*disable)(struct clk_hw *);int (*set_rate)(struct clk_hw *,unsigned long,unsigned long);unsigned long (*recalc_rate)(struct clk_hw *,unsigned long);int (*determine_rate)(struct clk_hw *,struct clk_rate_request *); };
#define to_clk_regmap(hw) container_of(hw,struct clk_regmap,hw)
#define to_clk_pll(hw) container_of(to_clk_regmap(hw),struct clk_pll,clkr)
static int cases,checks,failures,panics,delays,warnings;
#define CHECK(x) do { checks++;if (!(x)) { if (failures++<12) fprintf(stderr,"%d: %s\n",__LINE__,#x); } } while (0)
static jmp_buf fatal;
static bool catching;
static void model_panic(const char *fmt,...) { panics++;if (!catching) {fprintf(stderr,"unexpected fatal: %s\n",fmt);exit(2);}longjmp(fatal,1); }
#define panic(...) model_panic(__VA_ARGS__)
static int model_warn(const char *fmt,...) { warnings++;return 1; }
#define WARN(c,...) ((c)?model_warn(__VA_ARGS__):0)
#define pr_err(...) ((void)0)
static const char *clk_hw_get_name(struct clk_hw *hw) { return hw->name; }
static void udelay(unsigned int n) { delays+=n; }
static int regmap_read(struct regmap *m,u32 off,u32 *value) {
 CHECK(off<sizeof(m->regs)&&!(off&3));m->reads++;
 if (m->reads==m->read_error_at)return -EIO;
 *value=m->regs[off/4];if (m->reads==m->corrupt_read_at)*value^=1;return 0;
}
static int regmap_update_bits(struct regmap *m,u32 off,u32 mask,u32 value) {
 CHECK(off<sizeof(m->regs)&&!(off&3));m->writes++;
 if (m->writes==m->error_at&&!m->apply_error)return -EIO;
 if (m->writes!=m->drop_at) {
  if ((off==4||off==8||off==12||off==0x14)&&(m->regs[0]&7))m->unsafe_program++;
  m->regs[off/4]=(m->regs[off/4]&~mask)|(value&mask);
  if (!off) { if (m->lock&&(m->regs[0]&6)==6&&m->regs[1])m->regs[7]|=BIT(16);else m->regs[7]&=~BIT(16); }
 }
 return m->writes==m->error_at?-EIO:0;
}
