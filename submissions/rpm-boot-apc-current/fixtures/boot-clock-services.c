/* SPDX-License-Identifier: GPL-2.0-only */
#define BIT(n) (1U << (n))
#define GENMASK(h,l) (((UINT32_MAX >> (31 - (h))) & (UINT32_MAX << (l))))
struct boot_plan { int bootstrap_mx_uV; };
struct cpr_msm8926_data { struct boot_plan plan; bool apc_enabled; void *apcs; };
struct boot_corner { unsigned long freq; int uV; };
struct cpr_drv {
    struct cpr_msm8926_data *msm8926;
    unsigned num_corners;
    struct boot_corner *corners;
    void *cpu_clk;
    struct cpr_voltage rails;
};
static unsigned long boot_cpu_rate;
static unsigned boot_clock_calls;
static int cpr_msm8926_check_cpu_rate(struct cpr_drv *drv, unsigned long limit) { return 0; }
static unsigned long clk_get_rate(void *clock) { return boot_cpu_rate; }
static int clk_set_rate(void *clock, unsigned long rate)
{
    ++boot_clock_calls;
    EXPECT(fw[0].enabled && fw[0].uV >= apc_voltage);
    boot_cpu_rate = rate; return 0;
}
static int regmap_read(void *map, u32 offset, u32 *value)
{
    CHECK(offset == 0x50 || offset == 0x54);
    *value = offset == 0x50 ? 0 : (4 << 8 | 3);
    return 0;
}
/* ACTUAL_BOOTSTRAP_CLOCK */
static int boot_cpu_attach(struct regulator_dev *ao, int covering, struct cpr_voltage *rails)
{
    static struct regulator mx, apc;
    mx = (struct regulator){.rdev = ao}; apc = (struct regulator){.apc = true};
    ao->consumer_list = &mx;
    struct boot_corner corner = {.freq = 300000000, .uV = 900000};
    struct cpr_msm8926_data data = {.plan.bootstrap_mx_uV = covering};
    struct cpr_drv drv = {.msm8926 = &data, .corners = &corner, .num_corners = 1,
        .rails = {.mx = &mx, .apc = &apc, .mx_max_uV = 1337500}};
    boot_cpu_rate = 800000000; boot_clock_calls = 0;
    int ret = cpr_msm8926_bootstrap_clock(&drv);
    if (!ret) {
        EXPECT(data.apc_enabled && boot_clock_calls == 1 && apc_enable_calls == 1);
        EXPECT(boot_cpu_rate == 300000000);
    } else {
        EXPECT(!boot_clock_calls && !apc_enable_calls);
    }
    *rails = drv.rails;
    return ret;
}
