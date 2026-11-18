// SPDX-License-Identifier: GPL-2.0-only
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <linux/elf.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
typedef uint32_t phys_addr_t;
#define PHYS_ADDR_MAX UINT32_MAX
#define GFP_KERNEL 0
#define SZ_4K 4096U
#define ALIGN(x, a) (((x) + (a) - 1) & ~((a) - 1))
#define QCOM_MDT_TYPE_MASK (7U << 24)
#define QCOM_MDT_TYPE_HASH (2U << 24)
#define QCOM_MDT_RELOCATABLE (1U << 27)
#define ERR_PTR(x) ((void *)(intptr_t)(x))
#define PTR_ERR(x) ((intptr_t)(x))
#define IS_ERR(x) ((uintptr_t)(x) >= (uintptr_t)-4095L)
#define kmalloc(n, flags) malloc(n)
#define kfree(ptr) free(ptr)
#define kstrdup(s, flags) strdup(s)
#define __free(name) __attribute__((cleanup(free_string)))
#define dev_err(...) ((void)0)
#define IS_ENABLED(option) 1
#define EPROBE_DEFER 517
struct firmware { size_t size; const unsigned char *data; };
struct device { void *of_node; };
struct qcom_scm_pas_metadata { int unused; };
struct venus_resources {
	const char *fwname;
	uint32_t cp_start, cp_size, cp_nonpixel_start, cp_nonpixel_size;
};
struct venus_core {
	struct device *dev;
	struct venus_resources *res;
	bool use_tz;
	struct { phys_addr_t mem_phys; size_t mem_size; } fw;
};
static const unsigned char *original;
static size_t original_size;
static unsigned int state;
static int metadata_error, relocation_error;
static int firmware_status, auth_status, protect_status, auth_calls, shutdown_calls;
static bool scm_available = true;
static const char *firmware_root;
static int missing_segment, short_segment, requests;
static void free_string(char **ptr) { free(*ptr); }
static size_t size_add(size_t a, size_t b)
{
	size_t n;
	return __builtin_add_overflow(a, b, &n) ? SIZE_MAX : n;
}
static size_t size_mul(size_t a, size_t b)
{
	size_t n;
	return __builtin_mul_overflow(a, b, &n) ? SIZE_MAX : n;
}
static FILE *open_split(const char *name)
{
	char path[PATH_MAX];
	int length = snprintf(path, sizeof(path), "%s/%s", firmware_root, name);

	assert(length > 0 && length < sizeof(path));
	return fopen(path, "rb");
}
static int request_firmware_into_buf(const struct firmware **fw, const char *name,
				     struct device *dev, void *buffer, size_t limit)
{
	char expected[32];
	struct firmware *result;
	int segment = 2 + requests++;
	FILE *file;
	size_t size;

	snprintf(expected, sizeof(expected), "qcom/msm8226/venus.b%02d", segment);
	assert(segment <= 4 && !strcmp(expected, name) && state == 2);
	if (!firmware_root || segment == missing_segment)
		return -ENOENT;
	file = open_split(name);
	if (!file)
		return -errno;
	size = fread(buffer, 1, limit - (segment == short_segment), file);
	assert(!ferror(file) && (segment == short_segment || fgetc(file) == EOF));
	fclose(file);
	result = malloc(sizeof(*result));
	assert(result);
	*result = (struct firmware) { size, buffer };
	*fw = result;
	return 0;
}
static void release_firmware(const struct firmware *fw)
{
	free((void *)fw);
}
static int qcom_scm_pas_init_image(int id, void *metadata, size_t length,
				   struct qcom_scm_pas_metadata *ctx)
{
	assert(!state && id == 9 && length == original_size);
	assert(!memcmp(original, metadata, length));
	state = 1;
	return metadata_error;
}
static int qcom_scm_pas_mem_setup(int id, phys_addr_t address, size_t length)
{
	assert(state == 1 && id == 9 && address == 0x0f500000 && length == 0x500000);
	state = 2;
	return relocation_error;
}
static bool qcom_scm_is_available(void) { return scm_available; }
static int of_property_read_string_index(void *node, const char *name, int index, const char **str)
{
	assert(!strcmp(name, "firmware-name") && index == 0);
	return -EINVAL;
}
static int venus_load_fw(struct venus_core *core, const char *name,
			 phys_addr_t *address, size_t *size)
{
	assert(!strcmp(name, "qcom/msm8226/venus.mdt"));
	*address = 0x0f500000;
	*size = 0x500000;
	return firmware_status;
}
static int qcom_scm_pas_auth_and_reset(int id)
{
	assert(id == 9);
	auth_calls++;
	return auth_status;
}
static int venus_boot_no_tz(struct venus_core *core, phys_addr_t address, size_t size)
{
	return -EOPNOTSUPP;
}
static int qcom_scm_mem_protect_video_var(uint32_t start, uint32_t size, uint32_t start2,
					 uint32_t size2)
{
	return protect_status;
}
static int qcom_scm_pas_shutdown(int id)
{
	assert(id == 9);
	shutdown_calls++;
	return 0;
}
static int dev_err_probe(struct device *dev, int error, const char *fmt, ...) { return error; }

/* EXTRACTED KERNEL SOURCE */

static void check_venus_boot(struct device *dev, const char *name)
{
	struct venus_resources resources = { .fwname = name };
	struct venus_core core = { .dev = dev, .res = &resources, .use_tz = true };

	firmware_status = -ENOENT;
	assert(venus_boot(&core) == -ENOENT);
	firmware_status = -EPROBE_DEFER;
	assert(venus_boot(&core) == -EPROBE_DEFER);
	firmware_status = 9;
	assert(venus_boot(&core) == -EIO && !auth_calls && !core.fw.mem_size);
	firmware_status = 0;
	scm_available = false;
	assert(venus_boot(&core) == -EPROBE_DEFER && !auth_calls);
	scm_available = true;
	auth_status = -ETIMEDOUT;
	assert(venus_boot(&core) == -ETIMEDOUT && auth_calls == 1);
	auth_status = 3;
	assert(venus_boot(&core) == -EIO && auth_calls == 2);
	auth_status = 0;
	assert(!venus_boot(&core) && auth_calls == 3 && core.fw.mem_size == 0x500000);
	resources.cp_size = 1;
	protect_status = 4;
	assert(venus_boot(&core) == -EIO && auth_calls == 4 && shutdown_calls == 1);
}

static void expect_fill(const unsigned char *start, size_t length, unsigned char value)
{
	for (size_t i = 0; i < length; i++)
		assert(start[i] == value);
}

static void check_split_load(struct device *dev, const struct firmware *fw, const char *name)
{
	const phys_addr_t start = 0x0f500000;
	const size_t span = 0x500000;
	const struct elf32_hdr *header = (const struct elf32_hdr *)fw->data;
	const struct elf32_phdr *phdrs = (const struct elf32_phdr *)(fw->data + header->e_phoff);
	unsigned char *buffer = malloc(span + 2 * SZ_4K);
	unsigned char *image;
	phys_addr_t relocation_base;
	size_t cursor = 0;

	assert(buffer && header->e_phnum == 5);
	image = buffer + SZ_4K;
	memset(buffer, 0xa5, span + 2 * SZ_4K);
	state = 0;
	relocation_error = 0;
	assert(!qcom_mdt_load(dev, fw, name, 9, image, start, span, &relocation_base));
	assert(state == 2 && requests == 3 && relocation_base == start);
	for (int index = 2; index < header->e_phnum; index++) {
		const struct elf32_phdr *segment = &phdrs[index];
		size_t offset = segment->p_paddr - start;
		char filename[32];
		FILE *expected;

		assert(offset >= cursor && offset + segment->p_memsz <= span);
		expect_fill(image + cursor, offset - cursor, 0xa5);
		snprintf(filename, sizeof(filename), "qcom/msm8226/venus.b%02d", index);
		expected = open_split(filename);
		assert(expected);
		for (size_t byte = 0; byte < segment->p_filesz; byte++)
			assert(fgetc(expected) == image[offset + byte]);
		assert(fgetc(expected) == EOF && !ferror(expected));
		fclose(expected);
		expect_fill(image + offset + segment->p_filesz,
			    segment->p_memsz - segment->p_filesz, 0);
		cursor = offset + segment->p_memsz;
	}
	expect_fill(image + cursor, span - cursor, 0xa5);
	expect_fill(buffer, SZ_4K, 0xa5);
	expect_fill(image + span, SZ_4K, 0xa5);

	for (int segment = 2; segment <= 4; segment++) {
		state = requests = 0;
		missing_segment = segment;
		assert(qcom_mdt_load(dev, fw, name, 9, image, start, span, NULL) == -ENOENT);
		assert(requests == segment - 1);
	}
	missing_segment = 0;
	for (int segment = 2; segment <= 4; segment++) {
		state = requests = 0;
		short_segment = segment;
		assert(qcom_mdt_load(dev, fw, name, 9, image, start, span, NULL) == -EINVAL);
		assert(requests == segment - 1);
	}
	free(buffer);
}

int main(int argc, char **argv)
{
	unsigned char data[1024] __attribute__((aligned(4)));
	const char *name = "qcom/msm8226/venus.mdt";
	size_t length = fread(data, 1, sizeof(data), stdin);
	struct firmware fw = { length, data };
	struct device dev = {};
	void *metadata;

	assert(length == 412 && feof(stdin));
	assert(qcom_mdt_get_size(&fw) == 0x500000 && qcom_mdt_bins_are_split(&fw));
	metadata = qcom_mdt_read_metadata(&fw, &length, name, &dev);
	assert(!IS_ERR(metadata) && length == fw.size && !memcmp(data, metadata, length));
	free(metadata);
	original = data;
	original_size = length;
	assert(qcom_mdt_pas_init(&dev, &fw, name, 9, 0x0f500000, NULL) == 0 && state == 2);
	state = 0;
	metadata_error = -EIO;
	assert(qcom_mdt_pas_init(&dev, &fw, name, 9, 0x0f500000, NULL) == -EIO && state == 1);
	state = 0;
	metadata_error = 0;
	relocation_error = -ETIMEDOUT;
	assert(qcom_mdt_pas_init(&dev, &fw, name, 9, 0x0f500000, NULL) == -ETIMEDOUT && state == 2);
	check_venus_boot(&dev, name);
	assert(argc == 1 || argc == 2);
	if (argc == 2) {
		firmware_root = argv[1];
		check_split_load(&dev, &fw, name);
		puts("split files, loaded bytes, zero-fill, guard bytes and six file errors passed");
	} else {
		puts("native layout, metadata copy and both SCM error checks passed");
	}
	return 0;
}
