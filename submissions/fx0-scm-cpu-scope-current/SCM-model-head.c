// SPDX-License-Identifier: GPL-2.0-only
/* Host services: no SMC, DMA mapping, fuse read or device access is executed. */
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <endian.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef uint64_t u64;
typedef uint32_t __le32;
typedef uintptr_t dma_addr_t;
#define EPROBE_DEFER 517
#define cpu_to_le32(v) htole32((uint32_t)(v))
#define le32_to_cpu(v) le32toh((uint32_t)(v))
#define PAGE_ALIGN(v) (((v)+4095)&~4095UL)
#define GFP_KERNEL 0
#define DMA_TO_DEVICE 1
#define DMA_FROM_DEVICE 2
#define DEFINE_MUTEX(v) int v
static unsigned cases, checks, failures;
#define CHECK(c) do { checks++; if (!(c)) { failures++; if (failures < 10) printf("FAIL %d %s\n", __LINE__, #c); } } while (0)
static int model_lock, allocations, frees, maps, unmaps, syncs, smc_calls;
static int availability_checks, convention_checks, arm_calls, slept;
static int allocation_fail, map_fail, smc_error, interruptions, poll_delay;
static void *model_allocation;
static size_t model_allocation_size, mapped_size;
static unsigned expected_address;
static uint32_t model_words[3];
struct device { int unused; };
struct qcom_scm { struct device *dev; };
static struct device model_device;
static struct qcom_scm model_scm = {.dev=&model_device};
static struct qcom_scm *__scm = &model_scm;
static void *kzalloc(size_t n, int flag) {
 (void)flag; allocations++; if (allocation_fail) return NULL;
 CHECK(!model_allocation && n == 4096);
 model_allocation = calloc(1,n); if (!model_allocation) exit(99);
 model_allocation_size=n; return model_allocation;
}
static void kfree(void *p) {
 CHECK(p && p == model_allocation && !model_lock); frees++;
 free(p); model_allocation=NULL; model_allocation_size=0;
}
static dma_addr_t dma_map_single(struct device *d, void *p, size_t n, int direction) {
 CHECK(d==&model_device && p==model_allocation && n<=model_allocation_size && direction==DMA_TO_DEVICE);
 maps++; mapped_size=n; return map_fail ? 0 : (uintptr_t)p;
}
static bool dma_mapping_error(struct device *d, dma_addr_t address) { CHECK(d==&model_device); return !address; }
static void dma_unmap_single(struct device *d, dma_addr_t address, size_t n, int direction) {
 CHECK(d==&model_device && address==(uintptr_t)model_allocation && n==mapped_size && direction==DMA_TO_DEVICE && !model_lock);
 unmaps++;
}
static void mutex_lock(int *p) { (void)p; CHECK(!model_lock); model_lock=1; }
static void mutex_unlock(int *p) { (void)p; CHECK(model_lock==1); model_lock=0; }
static void might_sleep(void) { slept++; }
#define pr_err(...) ((void)0)
#define smp_load_acquire(p) (availability_checks++, *(p))
struct arm_smccc_res { unsigned long a0, a1, a2, a3; };
static void dma_sync_single_for_cpu(struct device *, dma_addr_t, size_t, int);
static void arm_smccc_smc(unsigned long, unsigned long, unsigned long, unsigned long,
                         unsigned long, unsigned long, unsigned long, unsigned long,
                         struct arm_smccc_res *);
