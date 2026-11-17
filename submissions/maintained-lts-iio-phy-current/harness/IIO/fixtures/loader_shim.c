// SPDX-License-Identifier: GPL-2.0-only

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
