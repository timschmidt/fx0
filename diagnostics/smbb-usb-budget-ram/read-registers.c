// SPDX-License-Identifier: GPL-2.0-only
/* Read fixed PM8226 register rows after the caller verifies the SPMI parent and map range. */
#define _POSIX_C_SOURCE 200809L
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

struct register_sample {
	unsigned int address;
	const char *name;
};

static int hex_digit(char value)
{
	if (value >= '0' && value <= '9')
		return value - '0';
	if (value >= 'a' && value <= 'f')
		return value - 'a' + 10;
	return -1;
}

static int read_register(int fd, unsigned int address)
{
	char row[9], prefix[7];
	int high, low;

	if (snprintf(prefix, sizeof(prefix), "%04x: ", address) != 6)
		return -1;
	if (pread(fd, row, sizeof(row), (off_t)address * sizeof(row)) != sizeof(row) ||
	    memcmp(row, prefix, 6) || row[8] != '\n')
		return -1;

	high = hex_digit(row[6]);
	low = hex_digit(row[7]);
	if (high < 0 || low < 0)
		return -1;
	return high * 16 + low;
}

int main(int argc, char **argv)
{
	static const struct register_sample registers[] = {
		{ 0x1049, "charge_control" },
		{ 0x1208, "battery_presence" },
		{ 0x1310, "usb_rt" },
		{ 0x1344, "imax_selector" },
		{ 0x1347, "usb_suspend" },
		{ 0x1348, "usb_otg" },
	};
	int values[sizeof(registers) / sizeof(registers[0])];
	int fd, type, subtype;
	unsigned int i;

	if (argc != 2)
		return 2;
	fd = open(argv[1], O_RDONLY | O_CLOEXEC);
	if (fd < 0) {
		perror("open PM8226 register map");
		return 1;
	}

	type = read_register(fd, 0x1304);
	subtype = read_register(fd, 0x1305);
	if (type != 0x02 || subtype != 0x34) {
		fputs("PM8226 USB peripheral identity mismatch\n", stderr);
		close(fd);
		return 1;
	}
	for (i = 0; i < sizeof(registers) / sizeof(registers[0]); ++i) {
		values[i] = read_register(fd, registers[i].address);
		if (values[i] < 0) {
			fprintf(stderr, "invalid register row at %04x\n", registers[i].address);
			close(fd);
			return 1;
		}
	}
	close(fd);

	for (i = 0; i < sizeof(registers) / sizeof(registers[0]); ++i)
		printf("%s%s=%02x", i ? " " : "", registers[i].name, (unsigned int)values[i]);
	putchar('\n');
	return 0;
}
