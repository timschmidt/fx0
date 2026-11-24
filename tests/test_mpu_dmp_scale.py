"""Execute real IIO tiny-scale formatter code against exact Decimal fractions."""
import os
from decimal import Decimal, localcontext
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr'))
SOURCE = KERNEL/'drivers/iio/industrialio-core.c'
SHIM = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <sys/types.h>
#include <string.h>
typedef uint64_t u64; typedef int64_t s64;
#define BIT_ULL(n) (1ULL<<(n))
static u64 mul_u64_u64_div_u64(u64 a,u64 b,u64 c) { return (unsigned __int128)a*b/c; }
static s64 shift_right(s64 a,int shift) { return a<0 ? -((-a)>>shift) : a>>shift; }
static s64 div_s64_rem(s64 a,int b,int *rem) { *rem=a%b; return a/b; }
static ssize_t sysfs_emit_at(char *buf,size_t offset,const char *fmt,...) {
 va_list args; va_start(args,fmt); int n=vsnprintf(buf+offset,4096-offset,fmt,args); va_end(args); return n;
}
'''


class ScalePrecision(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        code = SOURCE.read_text()
        helper = code[code.index('static ssize_t iio_format_tiny_log2('):code.index('static ssize_t __iio_format_value(')]
        case = code.split('case IIO_VAL_FRACTIONAL_LOG2:', 1)[1].split('case IIO_VAL_INT_MULTIPLE:', 1)[0]
        cls.directory = tempfile.TemporaryDirectory(prefix='fx0-scale-')
        cls.exe = Path(cls.directory.name) / 'scale'
        source = Path(cls.directory.name) / 'scale.c'
        source.write_text(SHIM + helper + '\nstatic ssize_t format(char *buf,size_t offset,int *vals) { int tmp0,tmp1; s64 tmp2;\n' + case + '\n}\n' + r'''
int main(int argc,char **argv) {
 char buf[4096]={0}; int vals[2],offset=0;
 if(argc<3)return 1;
 vals[0]=strtol(argv[1],0,10); vals[1]=atoi(argv[2]);
 if(argc>3)offset=atoi(argv[3]);
 memset(buf,'x',offset); format(buf,offset,vals); puts(buf); return 0;
}
''')
        subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(cls.exe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def formatted(self, value, shift, offset=0):
        return subprocess.check_output([str(self.exe), str(value), str(shift), str(offset)], text=True).strip()

    def test_exact_nonzero_subnanounit_scales(self):
        with localcontext() as ctx:
            ctx.prec = 110
            for shift in range(30, 64):
                for numerator in (1, -1, 3, -3, 2147483647, -2147483648):
                    expected = Decimal(numerator) / (1 << shift)
                    if abs(expected) >= Decimal('0.000000001'):
                        continue
                    with self.subTest(shift=shift, numerator=numerator):
                        actual = Decimal(self.formatted(numerator, shift))
                        self.assertEqual(actual, expected)
                        self.assertNotEqual(actual, 0)

    def test_existing_non_tiny_formatting_unchanged(self):
        for numerator, shift, expected in [(0, 30, '0.000000000'), (123, 10, '0.120117187'), (-123, 10, '-0.120117187'), (1234567, 10, '1205.631835937')]:
            self.assertEqual(self.formatted(numerator, shift), expected)

    def test_offset_is_preserved(self):
        self.assertEqual(self.formatted(-1, 30, 4), 'xxxx-0.000000000931322574615478515625')


if __name__ == '__main__':
    unittest.main()
