// SPDX-License-Identifier: GPL-2.0-only

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
static uint32_t int_sqrt64(uint64_t x) {
 uint64_t low=0,high=1ULL<<32;
 while(low+1<high) { uint64_t mid=(low+high)/2; if(mid<=x/mid)low=mid; else high=mid; }
 return low;
}
