"""Fault injection against C functions extracted from the local Fx0 kernel.

Requires the development kernel checkout under src/fx0-linux and a host C compiler.
These tests exercise control flow with mocks, not bus timing or hardware.
"""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
KERNEL = ROOT / "src/fx0-linux"


def function(path, signature):
    source = (KERNEL / path).read_text()
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


class SlimbusErrorPaths(unittest.TestCase):
    def setUp(self):
        if not KERNEL.exists():
            self.skipTest("local Fx0 kernel checkout required")

    def run_c(self, source):
        compiler = "/usr/bin/gcc"
        if not pathlib.Path(compiler).exists() or not KERNEL.exists():
            self.skipTest("local kernel checkout and GCC required")
        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp) / "test.c"
            exe = pathlib.Path(tmp) / "test"
            src.write_text(source)
            subprocess.run([compiler, "-std=gnu11", "-Wall", "-Wextra",
                            "-Werror", "-Wno-unused-parameter", str(src),
                            "-o", str(exe)], check=True, capture_output=True)
            subprocess.run([str(exe)], check=True, capture_output=True)

    def test_codec_trigger_faults(self):
        trigger = function("sound/soc/codecs/wcd9306.c",
                           "static int wcd9306_trigger(")
        self.run_c(r"""
#include <assert.h>
#include <errno.h>
#define SNDRV_PCM_TRIGGER_START 1
#define SNDRV_PCM_TRIGGER_RESUME 2
#define SNDRV_PCM_TRIGGER_PAUSE_RELEASE 3
#define SNDRV_PCM_TRIGGER_STOP 4
#define SNDRV_PCM_TRIGGER_SUSPEND 5
#define SNDRV_PCM_TRIGGER_PAUSE_PUSH 6
struct snd_pcm_substream { int unused; };
struct slim_stream_runtime { int unused; };
struct slim_stream_config { int unused; };
struct wcd9306_codec {
 struct slim_stream_runtime *sruntime[1];
 struct slim_stream_config sconfig[1];
};
struct snd_soc_dai { struct wcd9306_codec *component; int id; };
static struct wcd9306_codec *snd_soc_component_get_drvdata(void *p) { return p; }
static int results[4], calls[4];
static int slim_stream_prepare(struct slim_stream_runtime *s,
                              struct slim_stream_config *c) {
 calls[0]++; return results[0];
}
static int slim_stream_enable(struct slim_stream_runtime *s) {
 calls[1]++; return results[1];
}
static int slim_stream_disable(struct slim_stream_runtime *s) {
 calls[2]++; return results[2];
}
static int slim_stream_unprepare(struct slim_stream_runtime *s) {
 calls[3]++; return results[3];
}
""" + trigger + r"""
static void reset(void) {
 for (int i = 0; i < 4; i++) results[i] = calls[i] = 0;
}
int main(void) {
 struct slim_stream_runtime stream = {0};
 struct wcd9306_codec codec = { .sruntime = { &stream } };
 struct snd_soc_dai dai = { &codec, 0 };
 struct snd_pcm_substream substream = {0};
 for (int cmd = 1; cmd <= 3; cmd++) {
  reset();
  assert(wcd9306_trigger(&substream, cmd, &dai) == 0);
  assert(calls[0] == 1 && calls[1] == 1 && !calls[2] && !calls[3]);
  reset(); results[0] = -ENOMEM;
  assert(wcd9306_trigger(&substream, cmd, &dai) == -ENOMEM);
  assert(calls[0] == 1 && !calls[1] && !calls[2] && !calls[3]);
  reset(); results[1] = -EIO;
  assert(wcd9306_trigger(&substream, cmd, &dai) == -EIO);
  assert(calls[0] == 1 && calls[1] == 1 && calls[2] == 1 && calls[3] == 1);
  reset(); results[1] = -ETIMEDOUT; results[2] = -EIO; results[3] = -EINVAL;
  assert(wcd9306_trigger(&substream, cmd, &dai) == -ETIMEDOUT);
  assert(calls[2] == 1 && calls[3] == 1);
 }
 for (int cmd = 4; cmd <= 6; cmd++) {
  reset();
  assert(wcd9306_trigger(&substream, cmd, &dai) == 0);
  assert(!calls[0] && !calls[1] && calls[2] == 1 && calls[3] == 1);
  reset(); results[2] = -EIO; results[3] = -EINVAL;
  assert(wcd9306_trigger(&substream, cmd, &dai) == -EIO);
  assert(calls[3] == 1);
  reset(); results[3] = -ETIMEDOUT;
  assert(wcd9306_trigger(&substream, cmd, &dai) == -ETIMEDOUT);
 }
 reset();
 assert(wcd9306_trigger(&substream, 999, &dai) == -EINVAL);
 for (int i = 0; i < 4; i++) assert(calls[i] == 0);
 return 0;
}
""")

    def test_prepare_rollback_and_disconnect_errors(self):
        prepare = function("drivers/slimbus/stream.c", "int slim_stream_prepare(")
        unprepare = function("drivers/slimbus/stream.c", "int slim_stream_unprepare(")
        self.run_c(r"""
#include <assert.h>
#include <errno.h>
#include <stdlib.h>
#define GFP_KERNEL 0
#define SLIM_DEVICE_MAX_PORTS 8
#define SNDRV_PCM_STREAM_PLAYBACK 0
#define SLIM_PROTO_PUSH 1
#define SLIM_PROTO_PULL 2
#define SLIM_PROTO_ISO 3
#define SLIM_PORT_DISCONNECTED 0
#define SLIM_CH_STATE_ALLOCATED 1
#define SLIM_CH_DATA_FMT_NOT_DEFINED 0
#define SLIM_CH_AUX_FMT_NOT_APPLICABLE 0
#define SLIM_PORT_SINK 0
#define SLIM_PORT_SOURCE 1
#define dev_err(...) ((void)0)
#define hweight32(x) __builtin_popcount(x)
#define for_each_set_bit(i, mask, max) \
 for ((i) = 0; (i) < (max); (i)++) if (*(mask) & (1UL << (i)))
#define kfree free
struct slim_framer { int superfreq; };
struct slim_controller { struct slim_framer *a_framer; };
struct slim_device { struct slim_controller *ctrl; int dev; };
struct slim_port {
 int state, id, direction;
 struct { int prrate, id, data_fmt, aux_fmt, state; } ch;
};
struct slim_stream_runtime {
 struct slim_device *dev;
 struct slim_port *ports;
 int num_ports, rate, bps, direction, prot, ratem;
};
struct slim_stream_config {
 unsigned long port_mask;
 int rate, bps, direction;
 unsigned int *chs;
};
static int alloc_fail, connect_fail, disconnected, connected;
static int disconnect_fail;
static void *kcalloc(int n, size_t size, int flags) {
 return alloc_fail ? NULL : calloc(n, size);
}
static int slim_get_prate_code(int rate) { return rate == 48000 ? 0x83 : -EINVAL; }
static int slim_connect_port_channel(struct slim_stream_runtime *rt,
                                     struct slim_port *port) {
 connected++;
 return port->id == connect_fail ? -EIO : 0;
}
static int slim_disconnect_port(struct slim_stream_runtime *rt,
                               struct slim_port *port) {
 disconnected++;
 return port->id == disconnect_fail ? -ETIMEDOUT : 0;
}
""" + prepare + unprepare + r"""
int main(void) {
 struct slim_framer framer = {4000};
 struct slim_controller ctrl = {&framer};
 struct slim_device dev = { .ctrl = &ctrl };
 struct slim_stream_runtime rt = { .dev = &dev };
 unsigned int channels[] = {144, 145};
 struct slim_stream_config cfg = {3, 48000, 24, 0, channels};
 connect_fail = disconnect_fail = -1;
 alloc_fail = 1;
 assert(slim_stream_prepare(&rt, &cfg) == -ENOMEM);
 assert(!rt.ports && !connected);
 alloc_fail = 0;
 cfg.rate = 123;
 assert(slim_stream_prepare(&rt, &cfg) == -EINVAL);
 assert(!rt.ports && !rt.num_ports && !connected);
 cfg.rate = 48000;
 for (int failure = 0; failure < 2; failure++) {
  connected = disconnected = 0; connect_fail = failure;
  assert(slim_stream_prepare(&rt, &cfg) == -EIO);
  assert(!rt.ports && !rt.num_ports);
  assert(connected == failure + 1 && disconnected == failure);
  /* Retrying after failure must allocate/connect a fresh stream. */
  connect_fail = -1;
  assert(slim_stream_prepare(&rt, &cfg) == 0);
  assert(rt.ports && rt.num_ports == 2);
  assert(slim_stream_prepare(&rt, &cfg) == -EINVAL);
  disconnected = 0; disconnect_fail = 0;
  assert(slim_stream_unprepare(&rt) == -ETIMEDOUT);
  assert(disconnected == 2 && !rt.ports && !rt.num_ports);
  assert(slim_stream_unprepare(&rt) == -EINVAL);
 }
 connect_fail = disconnect_fail = -1;
 assert(slim_stream_prepare(&rt, &cfg) == 0);
 assert(slim_stream_unprepare(&rt) == 0);
 return 0;
}
""")

    def test_ngd_response_ownership(self):
        ack = function("drivers/slimbus/qcom-ngd-ctrl.c",
                       "static int qcom_slim_ngd_check_ack(")
        sync = function("drivers/slimbus/qcom-ngd-ctrl.c",
                        "static int qcom_slim_ngd_xfer_msg_sync(")
        self.run_c(r"""
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#define HZ 100
#define SLIM_USR_MC_ADDR_QUERY 0x0d
#define SLIM_USR_ACK_SUCCESS (1U << 5)
#define dev_err(...) ((void)0)
#define DECLARE_COMPLETION_ONSTACK(name) int name = 0
struct slim_controller { void *dev; };
struct slim_val_inf { uint8_t *rbuf; };
struct slim_msg_txn {
 uint8_t mc, mt;
 struct slim_val_inf *msg;
 int *comp;
};
static int pm_refs, tid_refs, pm_error, send_error, timeout, reply;
static struct slim_msg_txn *current;
static int pm_runtime_get_sync(void *dev) { pm_refs++; return pm_error; }
static void pm_runtime_put(void *dev) { assert(pm_refs == 1); pm_refs--; }
static void slim_free_txn_tid(struct slim_controller *c, struct slim_msg_txn *t) {
 assert(tid_refs == 1); tid_refs--;
}
static int qcom_slim_ngd_xfer_msg(struct slim_controller *c,
                                 struct slim_msg_txn *t) {
 current = t;
 /* A new transaction must never retain the preceding ACK's success. */
 assert(t->msg->rbuf[0] == 0);
 return send_error;
}
static unsigned long wait_for_completion_timeout(int *done, int ticks) {
 if (timeout) return 0;
 /* Model the receive callback: copy reply, release TID and PM vote. */
 if (reply >= 0) current->msg->rbuf[0] = reply;
 assert(tid_refs == 1 && pm_refs == 1);
 tid_refs--; pm_refs--;
 *done = 1;
 return 1;
}
""" + ack + sync + r"""
static void reset(void) {
 pm_refs = 0; tid_refs = 1;
 pm_error = send_error = timeout = 0;
 reply = 0x20;
}
int main(void) {
 struct slim_controller ctrl = {0};
 uint8_t status = 0x20;
 struct slim_val_inf msg = {&status};
 struct slim_msg_txn txn = {.mc = 0x21, .msg = &msg};
 /* All possible ACK values, including nonzero successful 0x2b. */
 for (int value = 0; value < 256; value++) {
  reset(); reply = value;
  assert(qcom_slim_ngd_xfer_msg_sync(&ctrl, &txn) ==
         ((value & 0x20) ? 0 : -EIO));
  assert(!pm_refs && !tid_refs);
 }
 reset(); reply = -1; status = 0x20;
 assert(qcom_slim_ngd_xfer_msg_sync(&ctrl, &txn) == -EIO);
 assert(!pm_refs && !tid_refs);
 reset(); pm_error = -EHOSTDOWN;
 assert(qcom_slim_ngd_xfer_msg_sync(&ctrl, &txn) == -EHOSTDOWN);
 assert(!pm_refs && !tid_refs);
 reset(); send_error = -EIO;
 assert(qcom_slim_ngd_xfer_msg_sync(&ctrl, &txn) == -EIO);
 assert(!pm_refs && !tid_refs);
 reset(); timeout = 1;
 assert(qcom_slim_ngd_xfer_msg_sync(&ctrl, &txn) == -ETIMEDOUT);
 assert(!pm_refs && !tid_refs);
 txn.mc = SLIM_USR_MC_ADDR_QUERY;
 reset(); reply = 0;
 assert(qcom_slim_ngd_xfer_msg_sync(&ctrl, &txn) == 0);
 assert(!pm_refs && !tid_refs);
 return 0;
}
""")


if __name__ == "__main__":
    unittest.main()
