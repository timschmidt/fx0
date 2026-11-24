"""Exercise the candidate C decoder against compiled vendor calibration data."""
import ctypes as c
import json
import os
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr'))
HEADER = Path(os.environ.get('FX0_CPR_CALIBRATION_HEADER', KERNEL/'drivers/pmdomain/qcom/cpr-msm8926.h'))
PARAMS = json.loads((ROOT / 'manifests/msm8926-cpr-parameters.json').read_text())['parameters']
WRAPPER = '''
#include "cpr-msm8926.h"
int decode(unsigned long long row22, unsigned long long row138,
           unsigned long long row139, int status, int secure, int matches,
           unsigned int *out) {
 struct cpr_msm8926_fuses f = {row22,row138,row139,status,secure,matches};
 struct cpr_msm8926_calibration r;
 int ret=cpr_msm8926_decode(&f,&r), n=0;
 if(ret)return ret;
#define PUT(x) out[n++]=r.x
 PUT(pvs_bin); PUT(pvs_version); PUT(clock_speed_bin); PUT(cpr_speed_bin);
 for(int i=0;i<3;i++){PUT(floor_uV[i]);PUT(ceiling_uV[i]);PUT(initial_uV[i]);PUT(quotient[i]);PUT(ring_osc[i]);}
 for(int i=0;i<14;i++){PUT(quotient_adjust[i]);}
 PUT(quotient_scaling);PUT(clock_bin_valid);PUT(pvs_redundant);PUT(cpr_redundant);
 PUT(local_scheme);PUT(minimum_override);PUT(uplift);PUT(fuse_allows_loop);
 PUT(mx_ceiling_supported);PUT(interpolation_applied);
 return n;
}
'''


def reference(row22, primary, backup, matches):
    """Vendor sequence using the compiled property arrays, rather than C constants."""
    p = PARAMS
    def field(row, offset, width):
        return (row >> offset) & ((1 << width) - 1)
    selector = field(row22, 24, 3)
    pvs_redundant = selector == p['qcom,pvs-fuse-redun-sel'][3]
    desc = p['qcom,pvs-fuse-redun' if pvs_redundant else 'qcom,pvs-fuse']
    pvs = field(row22, desc[1], desc[2])
    speed = field(row22, 0, 3)
    version = field(row22, 4, 2)
    redundant = field(primary, 57, 1) == 1
    row = backup if redundant else primary
    prefix = 'qcom,cpr-fuse-redun-' if redundant else 'qcom,cpr-fuse-'
    quot = [field(row, offset, 12) for offset in p[prefix + 'target-quot']]
    ro = [field(row, offset, 3) for offset in p[prefix + 'ro-sel']]
    quot = [a + b for a, b in zip(quot, p['qcom,cpr-quotient-adjustment'])]
    minimum = not matches
    uplift = not minimum and speed == p['qcom,cpr-uplift-speed-bin'][0] and field(row22, 53, 1) == 0
    floor = p['qcom,cpr-voltage-floor'].copy()
    ceiling = p['qcom,cpr-voltage-ceiling'].copy()
    if minimum:
        for i in range(3):
            floor[i] = max(floor[i], p['qcom,cpr-cond-min-voltage'][0])
            ceiling[i] = max(ceiling[i], p['qcom,cpr-cond-min-voltage'][0])
    initial = p['qcom,pvs-voltage-table'][pvs * 3:pvs * 3 + 3]
    if uplift:
        initial[2] = min(initial[2] + p['qcom,cpr-uplift-voltage'][0], p['qcom,cpr-uplift-max-volt'][0])
        quot = [a + b for a, b in zip(quot, p['qcom,cpr-uplift-quotient'])]
    ceiling[2] = max(ceiling[2], initial[2])
    for i in range(2):
        if initial[i] > ceiling[i]:
            initial[i] = ceiling[i]
        elif initial[i] < floor[i]:
            initial[i] = floor[i]
    allowed = all(q <= 4095 for q in quot) and bool(row) and not field(primary, 36, 1) and quot[2] > quot[1] > quot[0] and quot[2] - quot[1] > 50
    table = p['qcom,cpr-speed-bin-max-corners']
    entry = next((table[i:i+5] for i in range(0, len(table), 5) if table[i:i+2] == [speed, version]), None)
    scaling = 0
    adjustments = [0] * 14
    interpolate = bool(entry and allowed)
    if interpolate:
        freq = dict(zip(p['qcom,cpr-corner-frequency-map'][::2], p['qcom,cpr-corner-frequency-map'][1::2]))
        normal, turbo = entry[3:5]
        scaling = min(1000 * (quot[2] - quot[1]) // (freq[turbo] // 1000000 - freq[normal] // 1000000), p['qcom,cpr-quot-adjust-scaling-factor-max'][0])
        for corner in range(normal+1, turbo+1):
            adjustments[corner-1] = scaling * (freq[turbo] // 1000000 - freq[corner] // 1000000) // 1000
    clock_valid = bool(row22 & 8)
    clock_speed = (field(row22, 27, 3) if selector == 1 else speed) if clock_valid else 0
    out = [pvs, version, clock_speed, speed]
    for i in range(3):
        out += [floor[i], ceiling[i], initial[i], quot[i], ro[i]]
    out += adjustments + [scaling, clock_valid, pvs_redundant, redundant, bool(field(primary, 37, 1)), minimum, uplift, allowed, ceiling[2] <= p['qcom,vdd-mx-vmax'][0], interpolate]
    return out


@unittest.skipUnless(HEADER.exists(), 'Candidate calibration header required')
class CalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        base = Path(cls.temporary.name)
        (base / 'linux').mkdir()
        (base / 'linux/types.h').write_text('#include <stdint.h>\n#include <stdbool.h>\ntypedef uint64_t u64;typedef uint32_t u32;\n')
        (base / 'linux/errno.h').write_text('#define EINVAL 22\n#define EIO 5\n')
        (base / 'linux/minmax.h').write_text('#define min(a,b) ((a)<(b)?(a):(b))\n#define max(a,b) ((a)>(b)?(a):(b))\n#define clamp(x,l,h) min(max(x,l),h)\n')
        (base / 'cpr-msm8926.h').write_bytes(HEADER.read_bytes())
        (base / 'wrapper.c').write_text(WRAPPER)
        result = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC', '-I', str(base), str(base/'wrapper.c'), '-o', str(base/'decoder.so')], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
        cls.lib = c.CDLL(str(base/'decoder.so'))
        cls.lib.decode.argtypes = [c.c_ulonglong]*3 + [c.c_int]*3 + [c.POINTER(c.c_uint)]
        cls.lib.decode.restype = c.c_int

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def check_decode(self, row22, primary, backup, matches):
        output = (c.c_uint * 43)()
        count = self.lib.decode(row22, primary, backup, 0, 0, matches, output)
        self.assertEqual(count, 43)
        self.assertEqual(list(output), reference(row22, primary, backup, matches))

    def test_all_pvs_bins_and_independent_selectors(self):
        primary = 700 << 24 | 900 << 12 | 1200 | 5 << 54 | 3 << 38 | 6 << 41
        backup = 650 << 24 | 850 << 12 | 1300 | 7 << 46 | 2 << 36 | 4 << 39
        for selector in range(8):
            for pvs in range(32):
                for redundant in range(2):
                    for matches in range(2):
                        row22 = 8 | 16 | pvs << 6 | selector << 24 | ((31-pvs) << 27)
                        self.check_decode(row22, primary | redundant << 57, backup, matches)

    def test_speed_version_uplift_disable_and_scheme(self):
        for speed in range(8):
            for version in range(4):
                for valid in range(2):
                    for upper in range(2):
                        for flags in range(4):
                            for matches in range(2):
                                row22 = speed | valid << 3 | version << 4 | 10 << 6 | upper << 53
                                primary = 700 << 24 | 900 << 12 | 1200 | (flags & 1) << 36 | (flags >> 1) << 37
                                self.check_decode(row22, primary, 0, matches)

    def test_invalid_zero_and_boundary_quotients(self):
        for svs, normal, turbo in [(0,0,0), (900,800,1200), (700,900,950), (700,900,951), (4095,4095,4095), (0,1,4095)]:
            for redundant in range(2):
                row = svs << 24 | normal << 12 | turbo
                self.check_decode(24, row | redundant << 57, row, 1)

    def test_random_rows(self):
        rng = random.Random(8926)
        for _ in range(2000):
            self.check_decode(rng.getrandbits(64), rng.getrandbits(64), rng.getrandbits(64), rng.randrange(2))

    def test_failed_reads_and_invalid_selector_leave_output_unchanged(self):
        for status, secure, matches, expected in [(-5,0,1,-5), (1,0,1,-5), (0,-517,1,-517), (0,4,1,-5), (0,0,-1,-22), (0,0,2,-22)]:
            output = (c.c_uint * 43)(*([0xdeadbeef]*43))
            self.assertEqual(self.lib.decode(24,0,0,status,secure,matches,output), expected)
            self.assertEqual(list(output), [0xdeadbeef]*43)


if __name__ == '__main__':
    unittest.main()
