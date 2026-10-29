/* SPDX-License-Identifier: MIT */
/*
 * RAM-only calibration reader for the verified Fx0 stock 3.4 kernel.
 *
 * Build as a freestanding ARM32 Linux executable; no libc is needed in the
 * stock-kernel diagnostic initramfs. ABI reference: the pinned vendor tree's
 * include/media/msm_cam_sensor.h and sensor/eeprom/msm_eeprom.c.
 *
 * Only GET_INFO, GET_CAL_DATA and READ_CAL_DATA are issued. READ_CAL_DATA
 * consumes the driver's cached copy: obtain independent captures across two
 * stock-kernel boots. No EEPROM programming or calibration operation is used.
 * Raw calibration goes to stdout and must remain in private backup storage.
 */

typedef unsigned char u8;
typedef unsigned int u32;

struct eeprom_config {
	u32 operation;
	u8 supported;
	union {
		char name[32];
		u32 size;
		struct {
			u8 *buffer;
			u32 size;
		} read;
		u32 padding[8];
	} data;
};

_Static_assert(sizeof(void *) == 4, "requires ARM32 ABI");
_Static_assert(sizeof(struct eeprom_config) == 40, "stock ioctl size");
_Static_assert(__builtin_offsetof(struct eeprom_config, data) == 8,
	       "stock ioctl union offset");

#define EEPROM_IOCTL ((3UL << 30) | (40UL << 16) | ('V' << 8) | 200)
_Static_assert(EEPROM_IOCTL == 0xc02856c8UL, "stock ioctl command");

static struct eeprom_config config;
#ifndef FX0_EEPROM_BYTES
#define FX0_EEPROM_BYTES 0x900
#endif
_Static_assert(FX0_EEPROM_BYTES == 0x900 || FX0_EEPROM_BYTES == 0xa00,
	       "use the original or expanded diagnostic calibration range");
static u8 calibration[FX0_EEPROM_BYTES];

static long syscall3(long number, long a, long b, long c)
{
	register long r0 __asm__("r0") = a;
	register long r1 __asm__("r1") = b;
	register long r2 __asm__("r2") = c;
	register long r7 __asm__("r7") = number;

	__asm__ volatile("svc 0" : "+r"(r0) : "r"(r1), "r"(r2), "r"(r7)
			 : "memory", "cc");
	return r0;
}

static unsigned int length(const char *text)
{
	unsigned int n = 0;

	while (text[n])
		n++;
	return n;
}

static int equal(const char *left, const char *right)
{
	while (*left && *left == *right) {
		left++;
		right++;
	}
	return *left == *right;
}

static int write_all(long fd, const void *buffer, unsigned int size)
{
	const u8 *bytes = buffer;
	long done;

	while (size) {
		done = syscall3(4, fd, (long)bytes, size);
		if (done == -4) /* EINTR */
			continue;
		if (done <= 0)
			return -1;
		bytes += done;
		size -= done;
	}
	return 0;
}

__attribute__((noreturn))
static void fail(long status, const char *message)
{
	write_all(2, message, length(message));
	syscall3(1, status, 0, 0);
	__builtin_unreachable();
}

static void read_text(const char *path, char *buffer, unsigned int size)
{
	long fd, count;

	fd = syscall3(5, (long)path, 0, 0); /* O_RDONLY */
	if (fd < 0)
		fail(65, "Cannot read kernel or subdevice identity\n");
	count = syscall3(3, fd, (long)buffer, size - 1);
	syscall3(6, fd, 0, 0);
	if (count < 0 || (unsigned long)count == size - 1)
		fail(65, "Invalid kernel or subdevice identity\n");
	buffer[count] = 0;
}

__attribute__((noreturn, used))
void reader_entry(unsigned long *initial_stack)
{
	char release[64], node_name[64], sysfs_path[128];
	const char *path, *suffix;
	const char prefix[] = "/dev/v4l-subdev";
	const char sysfs_prefix[] = "/sys/class/video4linux/";
	unsigned int i = 0, j, digits = 0;
	long fd;

	if (initial_stack[0] != 2)
		fail(64, "Usage: stock-camera-eeprom-reader /dev/v4l-subdevN\n");
	path = (const char *)initial_stack[2];
	while (prefix[i] && path[i] == prefix[i])
		i++;
	if (prefix[i])
		fail(64, "Expected a V4L2 subdevice path\n");
	for (j = i; path[j]; j++) {
		if (path[j] < '0' || path[j] > '9' || ++digits > 10)
			fail(64, "Invalid V4L2 subdevice number\n");
	}
	if (!digits)
		fail(64, "Missing V4L2 subdevice number\n");
	read_text("/proc/sys/kernel/osrelease", release, sizeof(release));
	if (!equal(release, "3.4.0-gf0d2a47\n"))
		fail(78, "Requires the verified Fx0 stock 3.4.0-gf0d2a47 kernel\n");

	i = 0;
	while (sysfs_prefix[i]) {
		sysfs_path[i] = sysfs_prefix[i];
		i++;
	}
	for (j = 5; path[j]; j++)
		sysfs_path[i++] = path[j];
	suffix = "/name";
	while (*suffix)
		sysfs_path[i++] = *suffix++;
	sysfs_path[i] = 0;
	read_text(sysfs_path, node_name, sizeof(node_name));
	if (!equal(node_name, "msm_eeprom\n"))
		fail(65, "Selected node is not the stock EEPROM subdevice\n");

	fd = syscall3(5, (long)path, 0, 0); /* O_RDONLY */
	if (fd < 0)
		fail(66, "Cannot open EEPROM subdevice\n");
	config.operation = 0; /* CFG_EEPROM_GET_INFO */
	if (syscall3(54, fd, EEPROM_IOCTL, (long)&config))
		fail(74, "EEPROM identity ioctl failed\n");
	config.data.name[31] = 0;
	if (!(config.supported & 1) || !equal(config.data.name, "imx179_eeprom"))
		fail(65, "Unexpected EEPROM identity\n");
	config.operation = 1; /* CFG_EEPROM_GET_CAL_DATA */
	if (syscall3(54, fd, EEPROM_IOCTL, (long)&config))
		fail(74, "EEPROM size ioctl failed\n");
	if (config.data.size != sizeof(calibration))
		fail(65, "Unexpected cached range; wrong image or cache already consumed\n");
	config.operation = 2; /* CFG_EEPROM_READ_CAL_DATA */
	config.data.read.buffer = calibration;
	config.data.read.size = sizeof(calibration);
	if (syscall3(54, fd, EEPROM_IOCTL, (long)&config))
		fail(74, "EEPROM cache read failed\n");
	syscall3(6, fd, 0, 0);
	if (write_all(1, calibration, sizeof(calibration)))
		fail(74, "Writing the calibration capture failed\n");
	syscall3(1, 0, 0, 0);
	__builtin_unreachable();
}

__asm__(".text\n.global _start\n.type _start,%function\n"
	"_start:\nmov r0, sp\nb reader_entry\n");
