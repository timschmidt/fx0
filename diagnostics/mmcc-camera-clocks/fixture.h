/* SPDX-License-Identifier: GPL-2.0-only */
/* Host interfaces only. Driver descriptors and rate helpers are extracted. */
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <limits.h>
#include <errno.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define BIT(n) (1U << (n))
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define container_of(p, t, m) ((t *)((char *)(p) - offsetof(t, m)))
#define clamp_t(t, v, lo, hi) ((t)(v) < (t)(lo) ? (t)(lo) : (t)(v) > (t)(hi) ? (t)(hi) : (t)(v))
#define clamp(v, lo, hi) clamp_t(unsigned long, v, lo, hi)
#define mult_frac(v, n, d) ((unsigned long)(((__uint128_t)(v) * (n)) / (d)))
#define CLK_SET_RATE_PARENT (1UL << 2)
#define lockdep_assert_held(p) ((void)(p))
#define trace_clk_rate_request_start(p) ((void)(p))
#define trace_clk_rate_request_done(p) ((void)(p))
#define pr_warn(...) assert(0)
#define WARN(cond, ...) ((void)(cond), (void)name)
#define udelay(n) ((void)(n))
struct clk_hw;
struct clk_rate_request {
    unsigned long rate, min_rate, max_rate, best_parent_rate;
    struct clk_hw *best_parent_hw;
};
struct clk_ops {
    int (*determine_rate)(struct clk_hw *, struct clk_rate_request *);
    int (*enable)(struct clk_hw *);
    void (*disable)(struct clk_hw *);
    int (*is_enabled)(struct clk_hw *);
};
struct clk_parent_data { const char *fw_name, *name; const struct clk_hw *hw; };
struct clk_init_data {
    const char *name;
    const struct clk_parent_data *parent_data;
    const struct clk_hw **parent_hws;
    unsigned num_parents;
    unsigned long flags;
    const struct clk_ops *ops;
};
struct clk_hw { const struct clk_init_data *init; };
struct regmap { u32 words[0x5108 / 4]; unsigned cmd, mnd_writes; int fail_reg; };
struct clk_regmap { struct clk_hw hw; struct regmap *regmap; u32 enable_reg, enable_mask; };
struct parent_map { u8 src, cfg; };
struct freq_tbl { unsigned long freq; u8 src, pre_div; u16 m, n; };
struct clk_rcg2 {
    u32 cmd_rcgr; u8 mnd_width, hid_width;
    const struct parent_map *parent_map;
    const struct freq_tbl *freq_tbl;
    struct clk_regmap clkr;
    u8 cfg_off;
    bool hw_clk_ctrl;
};
struct clk_branch { u32 halt_reg; struct clk_regmap clkr; };
struct clk_core {
    const char *name;
    struct clk_hw *hw;
    const struct clk_ops *ops;
    unsigned long flags, rate;
    struct clk_core *parent;
};
static int prepare_lock;
static struct clk_regmap mmpll0_vote, mmpll1_vote;
static const struct clk_ops clk_rcg2_ops;
#define to_clk_rcg2(hw) container_of(container_of(hw, struct clk_regmap, hw), struct clk_rcg2, clkr)
static int clk_hw_get_num_parents(struct clk_hw *hw) { return hw->init->num_parents; }
static const char *clk_hw_get_name(struct clk_hw *hw) { return hw->init->name; }
static bool clk_core_rate_is_protected(struct clk_core *c) { (void)c; return false; }
static void clk_core_forward_rate_req(struct clk_core *c, const struct clk_rate_request *r,
    struct clk_core *p, struct clk_rate_request *o, unsigned long rate) {
    (void)c; *o = *r; o->rate = rate; o->best_parent_hw = p->hw;
}
static int clk_branch2_enable(struct clk_hw *hw) { (void)hw; return 0; }
static void clk_branch2_disable(struct clk_hw *hw) { (void)hw; }
static int clk_is_enabled_regmap(struct clk_hw *hw) { (void)hw; return 1; }
static int regmap_read(struct regmap *m, unsigned off, u32 *value) {
    assert(off % 4 == 0 && off <= 0x5104);
    if ((int)off == m->fail_reg) return -EIO;
    if (off == m->cmd) m->words[off / 4] &= ~BIT(0);
    *value = m->words[off / 4];
    return 0;
}
static int regmap_update_bits(struct regmap *m, unsigned off, u32 mask, u32 value) {
    assert(off % 4 == 0 && off <= 0x5104);
    if ((int)off == m->fail_reg) return -EIO;
    if (off == m->cmd + 8 || off == m->cmd + 12 || off == m->cmd + 16) m->mnd_writes++;
    m->words[off / 4] = (m->words[off / 4] & ~mask) | (value & mask);
    return 0;
}
static int regmap_write(struct regmap *m, unsigned off, u32 value) {
    assert(off % 4 == 0 && off <= 0x5104);
    if ((int)off == m->fail_reg) return -EIO;
    m->words[off / 4] = value;
    return 0;
}
