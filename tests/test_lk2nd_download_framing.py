"""Execute lk2nd's actual download/read functions with controlled USB completions."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('FX0_LK2ND_SOURCE', ROOT / 'src/lk2nd'))


def function(text, name):
    match = re.search(r'^static [^\n]+\b' + re.escape(name) + r'\([^;]*?\)\n\{', text, re.M)
    if not match:
        raise ValueError('Missing source function: ' + name)
    end = text.index('{', match.start()) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[match.start():end] + '\n'


HARNESS = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "%d: %s\n", __LINE__, #x); exit(1); } } while (0)
#define STACKBUF_DMA_ALIGN(name, size) unsigned char name[size]
#define MAX_RSP_SIZE 64
#define MAX_USBFS_BULK_SIZE (32 * 1024)
#define STATE_COMMAND 1
#define STATE_ERROR 3
#define INFO 0
#define CACHE_LINE 32
#define ROUNDUP(x, y) (((x) + (y) - 1) & ~((y) - 1))
#define PA(x) (x)
typedef uintptr_t addr_t;
struct udc_request {
    void *buf;
    unsigned length;
    void (*complete)(struct udc_request *, unsigned, int);
};
static struct udc_request request, *req = &request;
static unsigned fastboot_state, download_max, download_size;
static void *download_base, *out;
static int txn_status, txn_done;
static unsigned read_calls, okay_calls, failed_calls, short_at, error_at;
static unsigned short_bytes;
static char response[64];
static void event_signal(int *event, int value) { (void)event; (void)value; }
static void event_wait(int *event) { (void)event; }
static void arch_invalidate_cache_range(addr_t buffer, unsigned length) { (void)buffer; (void)length; }
#define dprintf(...) ((void)0)
static int udc_request_queue(void *endpoint, struct udc_request *request) {
    (void)endpoint;
    unsigned actual = request->length;
    read_calls++;
    if (read_calls == short_at) actual = short_bytes;
    request->complete(request, actual, read_calls == error_at ? -1 : 0);
    return 0;
}
static int usb_write(void *buffer, unsigned length) {
    CHECK(length < sizeof(response));
    memcpy(response, buffer, length); response[length] = 0;
    return length;
}
static void fastboot_okay(const char *message) { CHECK(!*message); okay_calls++; }
static void fastboot_fail(const char *message) { CHECK(!strcmp(message, "data too large")); failed_calls++; }
static struct {
    int (*usb_write)(void *, unsigned);
    int (*usb_read)(void *, unsigned);
} usb_if;
'''

MAIN = r'''
int main(int argc, char **argv) {
    CHECK(argc == 2);
    static unsigned char payload[66048];
    fastboot_state = STATE_COMMAND; download_base = payload;
    download_max = sizeof(payload); download_size = 123;
    usb_if.usb_write = usb_write; usb_if.usb_read = hsusb_usb_read;
    if (!strcmp(argv[1], "short_first")) { short_at = 1; short_bytes = 997; }
    else if (!strcmp(argv[1], "short_second")) { short_at = 2; short_bytes = 997; }
    else if (!strcmp(argv[1], "read_error")) error_at = 2;
    else if (!strcmp(argv[1], "oversize")) download_max--;
    else CHECK(!strcmp(argv[1], "full"));
    cmd_download("00010200", NULL, 0);
    if (!strcmp(argv[1], "full")) {
        CHECK(download_size == sizeof(payload) && okay_calls == 1 && read_calls == 3);
        CHECK(fastboot_state == STATE_COMMAND && !failed_calls);
        CHECK(!strcmp(response, "DATA00010200"));
    } else if (!strcmp(argv[1], "oversize")) {
        CHECK(!download_size && !okay_calls && !read_calls && failed_calls == 1);
    } else {
        CHECK(!download_size && !okay_calls && !failed_calls && fastboot_state == STATE_ERROR);
        CHECK(read_calls == (short_at ? short_at : error_at));
    }
    puts("actual lk2nd download framing checked");
    return 0;
}
'''


class Lk2ndDownloadFramingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (SOURCE / 'app/aboot/fastboot.c').read_text()
        cls.directory = tempfile.TemporaryDirectory()
        base = Path(cls.directory.name)
        harness = base / 'download.c'
        harness.write_text(HARNESS + ''.join(function(source, name) for name in [
            'hex2unsigned', 'req_complete', 'hsusb_usb_read', 'cmd_download']) + MAIN)
        cls.binary = base / 'download'
        subprocess.run(['cc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', str(harness), '-o', str(cls.binary)],
                       check=True, capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def check_mode(self, mode):
        result = subprocess.run([str(self.binary), mode], capture_output=True,
                                text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_complete_download_is_acknowledged(self):
        self.check_mode('full')

    def test_short_read_aborts_instead_of_resuming(self):
        for mode in ['short_first', 'short_second']:
            with self.subTest(mode=mode):
                self.check_mode(mode)

    def test_error_or_oversize_cannot_stage_a_payload(self):
        for mode in ['read_error', 'oversize']:
            with self.subTest(mode=mode):
                self.check_mode(mode)


if __name__ == '__main__':
    unittest.main()
