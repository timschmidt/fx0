"""Exercise the real CPR boot-clock lookup, including the native 800 MHz report."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT / 'worktrees/linux-fx0-cpr')) / 'drivers/pmdomain/qcom/cpr.c'

HARNESS = r'''
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#define EINVAL 22
#define dev_err(...) ((void)0)
#define dev_dbg(...) ((void)0)
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "line %d: %s\n", __LINE__, #x); exit(1); } } while (0)
struct corner { unsigned long freq; };
struct cpr_drv {
 void *cpu_clk, *dev, *msm8926;
 struct corner *corners, *corner;
 unsigned int num_corners;
};
static unsigned long boot_rate;
static unsigned long clk_get_rate(void *clk) { (void)clk; return boot_rate; }
'''
MAIN = r'''
int main(void) {
 struct corner corners[] = {{300000000}, {384000000}, {600000000},
                            {787200000}, {998400000}, {1094400000}, {1190400000}};
 struct cpr_drv drv = {.cpu_clk = (void *)1, .msm8926 = (void *)1,
                      .corners = corners, .num_corners = 7};
 unsigned long rejected[] = {0, 299999999, 400000000, 800000000, 1190400001};
 for (unsigned int i = 0; i < 7; i++) {
  boot_rate = corners[i].freq; drv.corner = NULL;
  CHECK(!cpr_find_initial_corner(&drv)); CHECK(drv.corner == &corners[i]);
 }
 for (unsigned int i = 0; i < sizeof(rejected) / sizeof(rejected[0]); i++) {
  boot_rate = rejected[i]; drv.corner = NULL;
  CHECK(cpr_find_initial_corner(&drv) == -EINVAL);
 }
 drv.msm8926 = NULL; drv.corner = NULL; boot_rate = 800000000;
 CHECK(!cpr_find_initial_corner(&drv)); CHECK(drv.corner == &corners[3]);
 drv.cpu_clk = NULL;
 CHECK(cpr_find_initial_corner(&drv) == -EINVAL);
 puts("7 exact MSM rates accepted; 5 unlisted rates rejected, including 800 MHz; legacy floor preserved");
 return 0;
}
'''


class InitialCornerTests(unittest.TestCase):
    def test_actual_boot_clock_lookup(self):
        source = SOURCE.read_text()
        start = source.index('static int cpr_find_initial_corner(')
        end = source.index('\n}', start) + 2
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'test.c').write_text(HARNESS + source[start:end] + MAIN)
            result = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                     str(base / 'test.c'), '-o', str(base / 'test')],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(base / 'test')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('including 800 MHz', result.stdout)


if __name__ == '__main__':
    unittest.main()
