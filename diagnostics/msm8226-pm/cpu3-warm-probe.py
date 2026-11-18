"""Measure where CPU3 reaches after the test's single warm-start request."""
import errno
from pathlib import Path
import subprocess
import sys
import time

CPUS = Path("/sys/devices/system/cpu")
CPU3 = CPUS / "cpu3/online"
PROBE_STATE = Path("/sys/module/msm8226_pm/parameters/hotplug_probe_state")
BOOT = Path("/proc/sys/kernel/random/boot_id")
COMMAND_LINE = Path("/proc/cmdline")
POWER = Path("/sys/power")
ONLINE = CPUS / "online"

IDLE = 0
ARMED = 1
WARM_ENTRY = 2


def state():
    return int(PROBE_STATE.read_text())


def exercise(guard):
    guard()
    assert ONLINE.read_text().strip() == "0-3" and state() == IDLE
    assert (POWER / "mem_sleep").read_text().split() == ["[s2idle]"]
    fixed = {
        name: (POWER / "suspend_stats" / name).read_text().strip()
        for name in ("success", "fail")
    }
    result = {"CPU": 3, "online_request_count": 0, "offline_request_count": 1,
              "state_before_offline": state(), "online_before": "0-3"}
    try:
        with CPU3.open("wb", buffering=0) as control:
            if control.write(b"0\n") != 2:
                raise OSError(errno.EIO, "short CPU offline write")
    except OSError as error:
        result["offline_errno"] = error.errno
    result["online_after_offline"] = ONLINE.read_text().strip()
    timed = time.monotonic()
    result["state_after_offline"] = state()
    quiet_states = {result["state_after_offline"]}
    while time.monotonic() - timed < 1.0:
        time.sleep(0.05)
        quiet_states.add(state())
    result["quiet_states"] = sorted(quiet_states)
    if result["online_after_offline"] == "0-2" and quiet_states == {ARMED}:
        guard()
        assert ONLINE.read_text().strip() == "0-2" and state() == ARMED
        start = time.monotonic()
        result["online_request_count"] = 1
        request = (
            "import errno\n"
            "from pathlib import Path\n"
            "import sys\n"
            "try:\n"
            "    with Path(sys.argv[1]).open('wb', buffering=0) as control:\n"
            "        if control.write(b'1\\n') != 2:\n"
            "            raise SystemExit(errno.EIO)\n"
            "except OSError as error:\n"
            "    raise SystemExit(error.errno)\n"
        )
        child = subprocess.Popen([sys.executable, "-B", "-c", request, str(CPU3)])
        while time.monotonic() - start < 25:
            if state() == WARM_ENTRY and "warm_vector_elapsed_seconds" not in result:
                result["warm_vector_elapsed_seconds"] = round(time.monotonic() - start, 3)
            if child.poll() is not None and "online_write_status" not in result:
                result["online_write_status"] = child.returncode
                result["online_write_elapsed_seconds"] = round(time.monotonic() - start, 3)
            if {"warm_vector_elapsed_seconds", "online_write_status"} <= result.keys():
                break
            time.sleep(0.05)
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)

    guard()
    result["online_at_end"] = ONLINE.read_text().strip()
    result["terminal_state"] = state()
    result["suspend_counters_unchanged"] = all(
        (POWER / "suspend_stats" / name).read_text().strip() == value
        for name, value in fixed.items()
    )
    result["passed"] = (
        result["online_request_count"] == 1 and result["terminal_state"] == WARM_ENTRY
        and result["online_at_end"] == "0-2" and result["suspend_counters_unchanged"]
        and "warm_vector_elapsed_seconds" in result and result.get("online_write_status") == errno.EIO
    )
    return result
