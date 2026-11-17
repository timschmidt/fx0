// SPDX-License-Identifier: GPL-2.0-only

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
struct regs { unsigned user_ctrl, int_enable, fifo_r_w, int_status; };
struct inv_mpu6050_state { int lock, chip_type; struct regs *reg; struct regmap *map;
 bool dmp_active,dmp_saved_valid,dmp_overflow,dmp_smd_mode;
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
