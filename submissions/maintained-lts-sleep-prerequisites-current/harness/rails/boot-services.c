/* SPDX-License-Identifier: GPL-2.0-only */
#define EPROBE_DEFER 517
#define ENOTRECOVERABLE 131
#define REGULATOR_CHANGE_VOLTAGE 1
#define rdev_info(...) ((void)0)
#define rdev_dbg(...) ((void)0)
static bool machine_registration;
static struct regulation_constraints machine_constraints[8];
static int regulator_ops_is_valid(struct regulator_dev *rdev, int mask) { return true; }
static int regulator_get_voltage_rdev(struct regulator_dev *rdev) { return rpm_reg_get_voltage(rdev); }
static int _regulator_do_set_voltage(struct regulator_dev *rdev, int low, int high)
{
    return rpm_reg_set_voltage(rdev, low, high, NULL);
}
/* ACTUAL_MACHINE_CONSTRAINTS */
