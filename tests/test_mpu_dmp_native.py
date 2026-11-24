"""Compile actual native transport against a fault-injected banked regmap model."""
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
KERNEL = pathlib.Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr'))
SOURCE = KERNEL/'drivers/iio/imu/inv_mpu6050/inv_mpu_dmp.c'

SHIM = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8;
#define __aligned(n) __attribute__((aligned(n)))
#define INV_MPU6515 2
#define INV_MPU6050_BIT_DMP_EN 0x80
#define INV_MPU6050_BIT_FIFO_EN 0x40
#define lockdep_assert_held(x) ((void)(x))
#define min_t(t,a,b) ((t)(a) < (t)(b) ? (t)(a) : (t)(b))
struct regmap { u8 ram[3072], regs[256]; unsigned bank, cursor; int calls, fail, corrupt; u8 fifo[1024]; size_t fifo_len; };
struct regs { unsigned user_ctrl, int_enable, fifo_r_w; };
struct inv_mpu6050_state { int lock, chip_type; struct regs *reg; struct regmap *map;
 bool dmp_active,dmp_saved_valid,dmp_overflow;
 u8 dmp_saved[12],dmp_tail[16],dmp_fifo[1040]; size_t dmp_tail_len;
 int64_t dmp_last_timestamp; struct { unsigned user_ctrl; bool wom_en; } chip_config;
 };
static int tick(struct regmap *m) { return ++m->calls == m->fail ? -EREMOTEIO : 0; }
static int regmap_read(struct regmap *m, unsigned r, unsigned *v) {
 int e=tick(m); if(e) return e; if(r==0x72) *v=m->fifo_len>>8;
 else if(r==0x73) *v=m->fifo_len&255;
 else { *v=m->regs[r]; }
 return 0;
}
static int regmap_write(struct regmap *m, unsigned r, unsigned v) {
 int e=tick(m); if(e) return e;
 m->regs[r]=v;
 if(r==0x6a && (v&4)) m->fifo_len=0;
 if(r==0x6d) { assert(v<12); m->bank=v; } else if(r==0x6e) m->cursor=v;
 return 0;
}
static int transfer(struct regmap *m, unsigned r, void *data, size_t n, bool write) {
 int e=tick(m); if(e) return e;
 if(r==0x74) {
  assert(!write && n<=m->fifo_len);
  memcpy(data,m->fifo,n); memmove(m->fifo,m->fifo+n,m->fifo_len-n);
  m->fifo_len-=n; return 0;
 }
 assert(r==0x6f && n<=16 && m->cursor+n<=256);
 assert(m->bank*256+m->cursor>=32);
 if(write) memcpy(m->ram+m->bank*256+m->cursor,data,n);
 else { memcpy(data,m->ram+m->bank*256+m->cursor,n); if(m->corrupt) ((u8*)data)[0]^=1; }
 /* Deliberately lose cursor between transactions. */
 m->cursor=0;
 return 0;
}
static int regmap_noinc_write(struct regmap *m,unsigned r,const void *p,size_t n) { return transfer(m,r,(void*)p,n,true); }
static int regmap_noinc_read(struct regmap *m,unsigned r,void *p,size_t n) { return transfer(m,r,p,n,false); }
'''
MAIN = r'''
int main(void) {
 struct regmap m={0}; struct regs r={.user_ctrl=0x6a,.int_enable=0x38,.fifo_r_w=0x74};
 struct inv_mpu6050_state st={.chip_type=INV_MPU6515,.reg=&r,.map=&m};
 u8 input[2943], output[2943]; int n, calls;
 for(n=0;n<2943;n++) input[n]=(n*37+11)&255;
 memset(m.ram,0x5a,sizeof(m.ram));
 assert(inv_mpu6515_dmp_mem_write(&st,32,input,sizeof(input))==0);
 calls=m.calls;
 assert(!memcmp(m.ram+32,input,sizeof(input)));
 for(n=0;n<32;n++) assert(m.ram[n]==0x5a);
 for(n=2975;n<3072;n++) assert(m.ram[n]==0x5a);
 assert(inv_mpu6515_dmp_mem_read(&st,32,output,sizeof(output))==0);
 assert(!memcmp(input,output,sizeof(input)));
 /* Fail each operation of an entire successful write/readback sequence. */
 for(n=1;n<=calls;n++) {
  memset(&m,0,sizeof(m)); m.fail=n;
  assert(inv_mpu6515_dmp_mem_write(&st,32,input,sizeof(input))==-EREMOTEIO);
  assert(m.calls==n && !(m.regs[0x6a]&0xc0));
 }
 memset(&m,0,sizeof(m)); m.corrupt=1;
 assert(inv_mpu6515_dmp_mem_write(&st,255,input,20)==-EIO);
 memset(&m,0,sizeof(m));
 assert(inv_mpu6515_dmp_mem_write(&st,31,input,1)==-EINVAL);
 assert(inv_mpu6515_dmp_mem_write(&st,3071,input,2)==-EINVAL);
 assert(inv_mpu6515_dmp_mem_write(&st,32,input,0)==-EINVAL);
 assert(inv_mpu6515_dmp_mem_write(&st,~0u,input,1)==-EINVAL);
 assert(m.calls==0);
 m.regs[0x6a]=0x80;
 assert(inv_mpu6515_dmp_mem_write(&st,32,input,1)==-EBUSY);
 m.regs[0x6a]=0x40;
 assert(inv_mpu6515_dmp_mem_read(&st,32,output,1)==-EBUSY);
 st.chip_type=0; m.calls=0;
 assert(inv_mpu6515_dmp_mem_write(&st,32,input,1)==-EOPNOTSUPP);
 assert(m.calls==0);
 printf("Passed bounds, bank splits, cursor loss, corrupt readback and %d injected operation failures\n",calls);
 return 0;
}
'''

PACKET_SHIM = r'''
 typedef uint16_t u16; typedef int16_t s16; typedef int32_t s32;
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
enum inv_mpu6515_dmp_packet_type { INV_MPU6515_DMP_ACCEL, INV_MPU6515_DMP_QUATERNION };
struct inv_mpu6515_dmp_packet { enum inv_mpu6515_dmp_packet_type type; s32 xyz[3]; u8 step_flags; };
static u16 get_unaligned_be16(const u8 *p) { return (p[0]<<8)|p[1]; }
static uint32_t get_unaligned_be32(const u8 *p) { return ((uint32_t)get_unaligned_be16(p)<<16)|get_unaligned_be16(p+2); }
'''
PACKET_MAIN = r'''
int main(void) {
 struct regmap m={0}; struct regs r={.user_ctrl=0x6a,.int_enable=0x38,.fifo_r_w=0x74};
 struct inv_mpu6050_state st={.chip_type=INV_MPU6515,.reg=&r,.map=&m};
 struct inv_mpu6515_dmp_packet packet, before;
 u8 accel[]={0x40,0x0b,0x80,0,0x7f,0xff,0xff,0xff};
 u8 quat[]={0x04,0x03,0,0,0x80,0,0,0,0x7f,0xff,0xff,0xff,0xff,0xff,0xff,0xff};
 int i,calls;
 assert(inv_mpu6515_dmp_configure(&st)==0); calls=m.calls;
 assert(m.ram[1127]==0x4c && m.ram[1770]==0xa3 && m.ram[1701]==0xa3);
 assert(m.ram[744]==0 && m.ram[745]==7 && m.ram[731]==7);
 for(i=1;i<=calls;i++) {
  memset(&m,0,sizeof(m)); m.fail=i;
  assert(inv_mpu6515_dmp_configure(&st)==-EREMOTEIO && m.calls==i);
 }
 memset(&packet,0x5a,sizeof(packet)); before=packet;
 for(i=0;i<8;i++) {
  assert(inv_mpu6515_dmp_decode(accel,i,&packet)==-EAGAIN);
  assert(!memcmp(&packet,&before,sizeof(packet)));
 }
 assert(inv_mpu6515_dmp_decode(accel,8,&packet)==8);
 assert(packet.type==INV_MPU6515_DMP_ACCEL && packet.step_flags==11);
 assert(packet.xyz[0]==-32768 && packet.xyz[1]==32767 && packet.xyz[2]==-1);
 before=packet;
 for(i=0;i<16;i++) {
  assert(inv_mpu6515_dmp_decode(quat,i,&packet)==-EAGAIN);
  assert(!memcmp(&packet,&before,sizeof(packet)));
 }
 assert(inv_mpu6515_dmp_decode(quat,16,&packet)==16);
 assert(packet.type==INV_MPU6515_DMP_QUATERNION && packet.step_flags==3);
 assert(packet.xyz[0]==INT32_MIN && packet.xyz[1]==INT32_MAX && packet.xyz[2]==-1);
 before=packet; quat[0]=0x7f;
 assert(inv_mpu6515_dmp_decode(quat,16,&packet)==-EPROTO);
 assert(!memcmp(&packet,&before,sizeof(packet)));
 printf("Passed native packet fragments, signed extremes, no stale output and %d configuration-operation failures\n",calls);
 return 0;
}
'''

# Stream lifecycle tests compile only stream/recovery entry points. SMD PM
# entry points are covered by test_mpu_dmp_smd with their own PM/IRQ model.
STREAM_SHIM = SHIM.replace('unsigned user_ctrl, int_enable, fifo_r_w;',
                           'unsigned user_ctrl, int_enable, fifo_r_w, int_status;')
STREAM_SHIM = STREAM_SHIM.replace('bool dmp_active,dmp_saved_valid,dmp_overflow;',
                                 'bool dmp_active,dmp_saved_valid,dmp_overflow,dmp_smd_mode;')

LIFECYCLE_SHIM = r'''
typedef uint64_t u64; typedef int64_t s64;
#define BIT_ULL(n) (1ULL<<(n))
#define INV_MPU6050_BIT_DMP_RST 8
#define INV_MPU6050_BIT_FIFO_RST 4
#define INV_MPU6050_BIT_DMP_INT_EN 2
#define INV_MPU6050_BIT_FIFO_OVERFLOW_INT 16
#define dev_err(...) ((void)0)
#define dev_warn_ratelimited(...) ((void)0)
#define msleep(n) ((void)(n))
#define usleep_range(a,b) ((void)(a),(void)(b))
struct reg_sequence { unsigned reg,def; };
static int regmap_multi_reg_write(struct regmap *m,const struct reg_sequence *r,size_t n) {
 size_t i; int e; for(i=0;i<n;i++) { e=regmap_write(m,r[i].reg,r[i].def); if(e)return e; } return 0;
}
static int inv_mpu6515_dmp_load(struct inv_mpu6050_state *st) { (void)st; return 0; }
struct iio_dev { struct inv_mpu6050_state *st; int samples; int32_t q[4]; s64 timestamp; };
#define iio_priv(d) ((d)->st)
static int iio_push_to_buffers_with_ts(struct iio_dev *d,void *p,size_t n,s64 t) {
 /* IIO aligns total scan size to its largest element: 16 + 8 rounds to 32. */
 size_t scan_bytes=((16+8+15)/16)*16;
 unsigned char *bytes=p; size_t i;
 assert(n>=scan_bytes);
 for(i=16;i<24;i++) assert(bytes[i]==0);
 memcpy(bytes+scan_bytes-8,&t,8);
 memcpy(d->q,p,16); memcpy(&d->timestamp,bytes+24,8); d->samples++;
 return 0;
}
static uint32_t int_sqrt64(uint64_t x) {
 uint64_t low=0,high=1ULL<<32;
 while(low+1<high) { uint64_t mid=(low+high)/2; if(mid<=x/mid)low=mid; else high=mid; }
 return low;
}
'''
LIFECYCLE_MAIN = r'''
int main(void) {
 struct regmap m={0}; struct regs r={.user_ctrl=0x6a,.int_enable=0x38,.fifo_r_w=0x74};
 struct inv_mpu6050_state st={.chip_type=INV_MPU6515,.reg=&r,.map=&m};
 struct iio_dev d={.st=&st}; int i,calls,stop_calls;
 u8 packet[16]={4,0};
 assert(inv_mpu6515_dmp_start(&st)==0 && st.dmp_active);
 calls=m.calls;
 assert(m.regs[0x6a]==0xc0 && m.regs[0x38]==0x12);
 assert(inv_mpu6515_dmp_stop(&st)==0 && !st.dmp_saved_valid && !st.dmp_active);
 stop_calls=m.calls-calls;
 assert(m.regs[0x19]==0 && m.regs[0x38]==0 && m.regs[0x6a]==0);
 for(i=1;i<=calls;i++) {
  memset(&m,0,sizeof(m)); st.dmp_saved_valid=false; st.dmp_active=false; m.fail=i;
  assert(inv_mpu6515_dmp_start(&st)==-EREMOTEIO);
  assert(!st.dmp_active && !(m.regs[0x6a]&0xc0));
 }
 for(i=1;i<=stop_calls;i++) {
  memset(&m,0,sizeof(m)); st.dmp_saved_valid=false; st.dmp_active=false;
  assert(inv_mpu6515_dmp_start(&st)==0);
  m.fail=m.calls+i;
  assert(inv_mpu6515_dmp_stop(&st)==-EREMOTEIO && st.dmp_saved_valid);
  assert(inv_mpu6515_dmp_stop(&st)==0 && !st.dmp_saved_valid);
 }
 memset(&m,0,sizeof(m)); st.dmp_saved_valid=false;
 assert(inv_mpu6515_dmp_start(&st)==0);
 m.fail=m.calls+1;
 assert(inv_mpu6515_dmp_stop(&st)==-EREMOTEIO && st.dmp_saved_valid);
 assert(inv_mpu6515_dmp_stop(&st)==0 && !st.dmp_saved_valid);
 assert(inv_mpu6515_dmp_start(&st)==0);
 memcpy(m.fifo,packet,7); m.fifo_len=7;
 assert(inv_mpu6515_dmp_read_fifo(&d,1000000000)==0 && d.samples==0 && st.dmp_tail_len==7);
 memcpy(m.fifo,packet+7,9); m.fifo_len=9;
 assert(inv_mpu6515_dmp_read_fifo(&d,1040000000)==0 && d.samples==1 && st.dmp_tail_len==0);
 assert(d.q[0]==(1<<30) && d.q[1]==0 && d.timestamp==1040000000);
 memcpy(m.fifo,packet,16); m.fifo[0]=0x7f; m.fifo_len=16;
 assert(inv_mpu6515_dmp_read_fifo(&d,1080000000)==-EPROTO && d.samples==1);
 assert(st.dmp_tail_len==0 && m.fifo_len==0);
 st.dmp_overflow=true;
 assert(inv_mpu6515_dmp_read_fifo(&d,1080000000)==-EOVERFLOW && !st.dmp_overflow);
 memcpy(m.fifo,packet,16); m.fifo[4]=0x7f; m.fifo_len=16;
 assert(inv_mpu6515_dmp_read_fifo(&d,1080000000)==-ERANGE && d.samples==1);
 memcpy(m.fifo,packet,16); memcpy(m.fifo+16,packet,16); m.fifo_len=32;
 assert(inv_mpu6515_dmp_read_fifo(&d,1200000000)==0 && d.samples==3);
 assert(d.timestamp==1200000000);
 /* A semantically invalid second packet invalidates the whole batch. */
 memcpy(m.fifo,packet,16); memcpy(m.fifo+16,packet,16); m.fifo[20]=0x7f; m.fifo_len=32;
 assert(inv_mpu6515_dmp_read_fifo(&d,1280000000)==-ERANGE && d.samples==3);
 m.fifo_len=992;
 assert(inv_mpu6515_dmp_read_fifo(&d,1320000000)==-EOVERFLOW && d.samples==3);
 printf("Passed native lifecycle (%d startup + %d stop failures), cleanup retry, FIFO fragments, quaternion, corruption and overflow controls\n",calls,stop_calls);
 return 0;
}
'''

LOADER_SHIM = r'''
struct device { int unused; };
struct firmware { const u8 *data; size_t size; };
static struct firmware fixture;
static int missing,requests,releases;
#define regmap_get_device(m) ((void)(m),(struct device *)0)
#define MODULE_FIRMWARE(n)
static int request_firmware(const struct firmware **fw,const char *name,struct device *dev) {
 (void)name; (void)dev; requests++; if(missing)return -ENOENT; *fw=&fixture; return 0;
}
static void release_firmware(const struct firmware *fw) { (void)fw; releases++; }
static uint32_t crc32_le(uint32_t crc,const u8 *data,size_t n) {
 size_t i; int bit; for(i=0;i<n;i++) { crc^=data[i]; for(bit=0;bit<8;bit++)crc=(crc>>1)^((crc&1)?0xedb88320:0); } return crc;
}
static int regmap_bulk_write(struct regmap *m,unsigned r,const void *data,size_t n) {
 const u8 *p=data; size_t i; int e; for(i=0;i<n;i++) { e=regmap_write(m,r+i,p[i]); if(e)return e; } return 0;
}
'''
LOADER_MAIN = r'''
int main(int argc,char **argv) {
 struct regmap m={0}; struct regs r={.user_ctrl=0x6a,.int_enable=0x38,.fifo_r_w=0x74};
 struct inv_mpu6050_state st={.chip_type=INV_MPU6515,.reg=&r,.map=&m};
 u8 image[2943]; FILE *f; int calls,i;
 assert(argc==2); f=fopen(argv[1],"rb"); assert(f);
 assert(fread(image,1,sizeof(image),f)==sizeof(image)); fclose(f);
 fixture.data=image; fixture.size=sizeof(image);
 assert(inv_mpu6515_dmp_load(&st)==0); calls=m.calls;
 assert(requests==1 && releases==1 && m.regs[0x70]==4 && m.regs[0x71]==0);
 assert(!memcmp(m.ram+32,image,sizeof(image)) && m.regs[0x6a]==0);
 for(i=1;i<=calls;i++) {
  memset(&m,0,sizeof(m)); m.fail=i; requests=0; releases=0;
  assert(inv_mpu6515_dmp_load(&st)==-EREMOTEIO);
  assert(requests==releases && m.regs[0x6a]==0);
 }
 memset(&m,0,sizeof(m)); requests=0; releases=0; missing=1;
 assert(inv_mpu6515_dmp_load(&st)==-ENOENT && requests==1 && releases==0 && m.calls==2);
 missing=0; fixture.size--;
 assert(inv_mpu6515_dmp_load(&st)==-EINVAL && m.calls==4);
 fixture.size++; image[0]^=1;
 assert(inv_mpu6515_dmp_load(&st)==-EINVAL && m.calls==6);
 image[0]^=1; m.corrupt=1;
 assert(inv_mpu6515_dmp_load(&st)==-EIO);
 printf("Passed real loader image/CRC, missing/invalid firmware, corruption and %d operation failures\n",calls);
 return 0;
}
'''

class NativeTransportTest(unittest.TestCase):
    def test_real_c_transport_with_regmap_faults(self):
        self.assertTrue(SOURCE.is_file(), 'Native DMP worktree is required')
        # No implementation substitution: strip includes and compile transport verbatim.
        code = SOURCE.read_text().split('#define INV_MPU6515_DMP_FIRMWARE')[0]
        code = '\n'.join(line for line in code.splitlines()
                         if not line.startswith('#include'))
        with tempfile.TemporaryDirectory(prefix='fx0-native-dmp-') as directory:
            src = pathlib.Path(directory) / 'transport.c'
            exe = pathlib.Path(directory) / 'transport'
            src.write_text(SHIM + code + MAIN)
            subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                            str(src), '-o', str(exe)], check=True)
            result = subprocess.run([str(exe)], check=True, text=True, capture_output=True)
            self.assertIn('injected operation failures', result.stdout)
            print(result.stdout.strip())

    def test_real_c_configuration_and_decoder(self):
        code = SOURCE.read_text()
        prefix = code.split('#define INV_MPU6515_DMP_FIRMWARE')[0]
        suffix = code[code.index('int inv_mpu6515_dmp_configure('):].split('/* Manufacturer SMD defaults;')[0]
        code = '\n'.join(line for line in (prefix + suffix).splitlines()
                         if not line.startswith('#include'))
        with tempfile.TemporaryDirectory(prefix='fx0-native-packet-') as directory:
            src = pathlib.Path(directory) / 'packet.c'
            exe = pathlib.Path(directory) / 'packet'
            src.write_text(SHIM + PACKET_SHIM + code + PACKET_MAIN)
            subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                            str(src), '-o', str(exe)], check=True)
            result = subprocess.run([str(exe)], check=True, text=True, capture_output=True)
            print(result.stdout.strip())

    def test_real_c_lifecycle_and_fifo(self):
        source = SOURCE.read_text()
        prefix = source.split('#define INV_MPU6515_DMP_FIRMWARE')[0]
        suffix = source[source.index('int inv_mpu6515_dmp_configure('):].split('\nint inv_mpu6515_dmp_smd_set(')[0]
        code = '\n'.join(line for line in (prefix + suffix).splitlines()
                         if not line.startswith('#include'))
        with tempfile.TemporaryDirectory(prefix='fx0-native-fifo-') as directory:
            src = pathlib.Path(directory) / 'fifo.c'
            exe = pathlib.Path(directory) / 'fifo'
            src.write_text(STREAM_SHIM + PACKET_SHIM + LIFECYCLE_SHIM + code + LIFECYCLE_MAIN)
            subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                            str(src), '-o', str(exe)], check=True)
            result = subprocess.run([str(exe)], check=True, text=True, capture_output=True)
            print(result.stdout.strip())

    def test_real_c_loader_with_private_reference_image(self):
        image = ROOT / 'local/firmware/mpu6515-reference/mpu6515-dmp.bin'
        if not image.exists():
            self.skipTest('private pinned reference image is not extracted')
        source = SOURCE.read_text()
        code = source[:source.index('int inv_mpu6515_dmp_configure(')]
        code = '\n'.join(line for line in code.splitlines()
                         if not line.startswith('#include'))
        with tempfile.TemporaryDirectory(prefix='fx0-native-loader-') as directory:
            src = pathlib.Path(directory) / 'loader.c'
            exe = pathlib.Path(directory) / 'loader'
            src.write_text(SHIM + LOADER_SHIM + code + LOADER_MAIN)
            subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                            str(src), '-o', str(exe)], check=True)
            result = subprocess.run([str(exe), str(image)], check=True, text=True, capture_output=True)
            print(result.stdout.strip())

if __name__ == '__main__':
    unittest.main()
