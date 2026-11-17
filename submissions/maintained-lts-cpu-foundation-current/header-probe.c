// SPDX-License-Identifier: GPL-2.0-only
/* Compile and instantiate calibration helpers against actual LTS kernel APIs. */
#include <linux/module.h>
#include "cpr-msm8926-fuses.h"
#include "cpr-msm8926-corner.h"
int fx0_header_probe(struct device *dev, struct regulator *apc, struct regulator *mx,
                     unsigned long rate, struct cpr_msm8926_corner *corner);
int fx0_header_probe(struct device *dev, struct regulator *apc, struct regulator *mx,
                     unsigned long rate, struct cpr_msm8926_corner *corner)
{
        struct cpr_msm8926_calibration calibration;
        struct cpr_msm8926_voltage_plan plan;
        u32 mask;
        int ret;

        ret = cpr_msm8926_read_calibration(dev, &calibration);
        if (ret)
                return ret;
        ret = cpr_msm8926_plan_voltages(&calibration, apc, mx, 1150000, 1337500, &plan);
        if (ret)
                return ret;
        ret = cpr_msm8926_supported_hw(&calibration, &plan, &mask);
        if (ret)
                return ret;
        return cpr_msm8926_map_corner(&calibration, &plan, rate, corner);
}
MODULE_LICENSE("GPL");
