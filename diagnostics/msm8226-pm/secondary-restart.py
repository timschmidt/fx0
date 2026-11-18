"""Bring secondary CPUs back online in order and run a task on each."""
import errno
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import time

CPUS = Path("/sys/devices/system/cpu")
POWER = Path("/sys/power")
ORDER = (3, 3, 1, 2)
ALL_CPUS = "0-3"
OFFLINE = {1: "0,2-3", 2: "0-1,3", 3: "0-2"}
TASK_DATA = b"fx0-msm8226-hotplug\n" * 65536


def write_once(path, value):
    with path.open("wb", buffering=0) as control:
        if control.write(value) != len(value):
            raise OSError(errno.EIO, "short CPU hotplug write")


def online():
    return (CPUS / "online").read_text().strip()


def counters():
    return {name: (POWER / "suspend_stats" / name).read_text().strip()
            for name in ("success", "fail")}


def cycle(cpu, guard):
    guard()
    assert online() == ALL_CPUS
    path = CPUS / f"cpu{cpu}/online"
    result = {"cpu": cpu, "online_before": ALL_CPUS, "online_requests": 0}
    try:
        write_once(path, b"0\n")
        result["offline_mask"] = online()
        if result["offline_mask"] != OFFLINE[cpu]:
            return result
        time.sleep(0.5)
        guard()
        assert online() == OFFLINE[cpu]
        began = time.monotonic()
        result["online_requests"] = 1
        write_once(path, b"1\n")
        result["online_seconds"] = round(time.monotonic() - began, 4)
        result["online_after"] = online()
        if result["online_after"] != ALL_CPUS:
            return result
        runner = """from hashlib import sha256
from pathlib import Path
import os, sys
cpu = int(sys.argv[1])
os.sched_setaffinity(0, {cpu})
assert os.sched_getaffinity(0) == {cpu}
digest = sha256(sys.stdin.buffer.read()).hexdigest()
assert int(Path("/proc/thread-self/stat").read_text().rsplit(")", 1)[1].split()[36]) == cpu
print(digest)
"""
        process = subprocess.run(
            [sys.executable, "-B", "-c", runner, str(cpu)], input=TASK_DATA,
            capture_output=True, timeout=8, check=True,
        )
        result["pinned_task_passed"] = process.stdout.strip() == sha256(TASK_DATA).hexdigest().encode()
    except (OSError, subprocess.SubprocessError) as error:
        result["error"] = type(error).__name__
        result["errno"] = getattr(error, "errno", None)
        result["online_when_error_observed"] = online()
    return result


def exercise(guard):
    guard()
    assert online() == ALL_CPUS
    assert (POWER / "mem_sleep").read_text().split() == ["[s2idle]", "deep"]
    initial = counters()
    cycles = []
    for cpu in ORDER:
        result = cycle(cpu, guard)
        cycles.append(result)
        if not result.get("pinned_task_passed"):
            break
    guard()
    intact = counters() == initial
    mask = online()
    return {
        "passed": len(cycles) == len(ORDER) and all(c.get("pinned_task_passed") for c in cycles)
                  and intact and mask == ALL_CPUS,
        "cycles": cycles, "online_at_end": mask, "suspend_counters_unchanged": intact,
    }
