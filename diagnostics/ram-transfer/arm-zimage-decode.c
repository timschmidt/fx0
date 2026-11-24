// SPDX-License-Identifier: MIT
/* Freestanding Linux ARM user-mode harness for a verified zImage payload. */
#ifndef IMAGE_BYTES
#error Define IMAGE_BYTES from the verified runtime Image.
#endif

extern int do_decompress(unsigned char *, int, unsigned char *, void (*)(char *));
unsigned long free_mem_ptr;
unsigned long free_mem_end_ptr;
static unsigned char scratch[65536] __attribute__((aligned(8)));
static unsigned char packed[8 * 1024 * 1024] __attribute__((aligned(8)));
static struct {
    unsigned char image[IMAGE_BYTES];
    unsigned char tail[64];
} output __attribute__((aligned(8)));

static long syscall3(long number, long fd, void *buf, unsigned long size)
{
    register long r0 asm("r0") = fd;
    register void *r1 asm("r1") = buf;
    register unsigned long r2 asm("r2") = size;
    register long r7 asm("r7") = number;
    asm volatile("svc 0" : "+r"(r0) : "r"(r1), "r"(r2), "r"(r7) : "memory", "cc");
    return r0;
}

static __attribute__((noreturn)) void finish(int status)
{
    syscall3(1, status, (void *)0, 0);
    __builtin_unreachable();
}

void __aeabi_unwind_cpp_pr0(void)
{
    finish(2);
}

static void decoder_error(char *message)
{
    (void)message;
    finish(3);
}

void _start(void)
{
    unsigned long length = 0;
    unsigned long written = 0;
    long count;

    while (length < sizeof(packed)) {
        count = syscall3(3, 0, packed + length, sizeof(packed) - length);
        if (count == -4)
            continue;
        if (count < 0)
            finish(4);
        if (!count)
            break;
        length += count;
    }
    if (length < 4 || length == sizeof(packed))
        finish(4);
    unsigned long size = 0;
    for (unsigned i = 0; i < 4; i++)
        size |= (unsigned long)packed[length - 4 + i] << (8 * i);
    if (size != IMAGE_BYTES)
        finish(4);

    free_mem_ptr = (unsigned long)scratch;
    free_mem_end_ptr = free_mem_ptr + sizeof(scratch);
    for (unsigned i = 0; i < sizeof(output.tail); i++)
        output.tail[i] = 0xa5;
    if (do_decompress(packed, (int)length, output.image, decoder_error))
        finish(3);
    for (unsigned i = 0; i < sizeof(output.tail); i++) {
        if (output.tail[i] != 0xa5)
            finish(5);
    }
    while (written < IMAGE_BYTES) {
        count = syscall3(4, 1, output.image + written, IMAGE_BYTES - written);
        if (count == -4)
            continue;
        if (count <= 0)
            finish(6);
        written += count;
    }
    finish(0);
}
