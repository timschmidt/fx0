// SPDX-License-Identifier: GPL-2.0-only

 typedef uint16_t u16; typedef int16_t s16; typedef int32_t s32;
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
enum inv_mpu6515_dmp_packet_type { INV_MPU6515_DMP_ACCEL, INV_MPU6515_DMP_QUATERNION };
struct inv_mpu6515_dmp_packet { enum inv_mpu6515_dmp_packet_type type; s32 xyz[3]; u8 step_flags; };
static u16 get_unaligned_be16(const u8 *p) { return (p[0]<<8)|p[1]; }
static uint32_t get_unaligned_be32(const u8 *p) { return ((uint32_t)get_unaligned_be16(p)<<16)|get_unaligned_be16(p+2); }
