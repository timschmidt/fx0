# SPDX-License-Identifier: MIT
"""Exercise the bounded Linux PM test on the checked MSM8226 RAM profile."""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import time

POWER = Path("/sys/power")
TRACEFS = Path("/sys/kernel/tracing")
CPUS = Path("/sys/devices/system/cpu/online")
TRACE_GROUP = "fx0_msm8226_platform_test"
CPR_STAGES = {
    "cpr_late_prepare": "qcom_cpr_msm8926_suspend_prepare",
    "cpr_check_rate": "cpr_msm8926_check_cpu_rate",
    "cpr_prepare_rails": "cpr_suspend_prepare",
    "cpr_cover_rails": "cpr_suspend_cover",
}
CALLBACKS = ("dpm_suspend_late", "dpm_suspend_noirq", "dpm_resume_noirq", "dpm_resume_early")
HOTPLUG_ACTIONS = ("CPU_OFF", "CPU_ON")


def read(path):
    return path.read_text().strip()


def write(path, value, append=False):
    # A buffered text file may flush again after the first sysfs failure.
    data = (value + "\n").encode()
    flags = os.O_WRONLY | os.O_CLOEXEC | (os.O_APPEND if append else os.O_TRUNC)
    fd = os.open(path, flags)
    try:
        if os.write(fd, data) != len(data):
            raise OSError("short control write")
    finally:
        os.close(fd)


def selected(path):
    values = re.findall(r"\[([^\[\]\s]+)\]", read(path))
    if len(values) != 1:
        raise ValueError(f"unexpected selected value in {path.name}")
    return values[0]


def statistics():
    stats = POWER / "suspend_stats"
    return {name: int(read(stats / name)) for name in ("success", "fail")}


def trace_summary(text):
    counts = {name: [0, 0] for name in CALLBACKS}
    hotplug = {action: {} for action in HOTPLUG_ACTIONS}
    stages = dict.fromkeys(CPR_STAGES, 0)
    in_late_suspend = False
    machine_suspend = False
    for line in text.splitlines():
        callback = re.search(r": suspend_resume: (\w+)\[(\d+)\] (begin|end)\b", line)
        if callback:
            name, number, edge = callback.groups()
            if name in counts:
                counts[name][int(edge == "end")] += 1
            if name in hotplug:
                hotplug[name].setdefault(number, [0, 0])[int(edge == "end")] += 1
            if name == "dpm_suspend_late":
                in_late_suspend = edge == "begin"
            if name == "machine_suspend":
                machine_suspend = True
        elif in_late_suspend:
            for name in stages:
                if f": {name}:" in line:
                    stages[name] += 1
    return {
        "callback_phases": counts,
        "all_callback_phases_completed_once": all(pair == [1, 1] for pair in counts.values()),
        "secondary_CPU_hotplug": hotplug,
        "all_secondary_CPU_cycles_completed_once": all(
            actions == {"1": [1, 1], "2": [1, 1], "3": [1, 1]} for actions in hotplug.values()
        ),
        "machine_suspend_entered": machine_suspend,
        "CPR_stages_reached": stages,
    }


@contextmanager
def capture(registration_errors):
    instance = TRACEFS / "instances" / TRACE_GROUP
    dynamic = TRACEFS / "kprobe_events"
    instance.mkdir()
    registered = []
    try:
        write(instance / "tracing_on", "0")
        write(instance / "events/power/suspend_resume/enable", "1")
        for event, symbol in CPR_STAGES.items():
            probe = f"{TRACE_GROUP}/{event}"
            try:
                write(dynamic, f"p:{probe} {symbol}", append=True)
            except OSError as error:
                registration_errors[event] = {"operation": "register", "errno": error.errno}
            else:
                registered.append(probe)
                try:
                    write(instance / "events" / probe / "enable", "1")
                except OSError as error:
                    registration_errors[event] = {"operation": "enable", "errno": error.errno}
        write(instance / "tracing_on", "1")
        yield instance
    finally:
        try:
            instance.rmdir()
        finally:
            for probe in reversed(registered):
                write(dynamic, f"-:{probe}", append=True)


def exercise(revalidate, *, test_level="platform"):
    """The caller must pin revalidation to the prepared RAM boot."""
    if test_level not in ("platform", "processors"):
        raise ValueError("expected a bounded PM test level")
    revalidate()
    pm_test, mode = POWER / "pm_test", POWER / "mem_sleep"
    if (selected(pm_test), selected(mode)) != ("none", "s2idle"):
        raise ValueError("power test controls have an unexpected owner")
    if test_level not in read(pm_test).split() or "deep" not in read(mode).split():
        raise ValueError("requested PM test is unavailable")
    if read(CPUS) != "0-3":
        raise ValueError("all CPUs must be online before platform replay")
    initial = statistics()
    result = {"passed": False, "request_attempted": False, "before": initial, "test_level": test_level}
    registration_errors = {}
    result["CPR_trace_registration_errors"] = registration_errors
    with capture(registration_errors) as trace:
        test_write_attempted = False
        mode_write_attempted = False
        try:
            test_write_attempted = True
            write(pm_test, test_level)
            mode_write_attempted = True
            write(mode, "deep")
            if (selected(pm_test), selected(mode)) != (test_level, "deep"):
                raise ValueError("PM test controls changed")
            count = POWER / "wakeup_count"
            write(count, read(count))
            revalidate()
            # Both test levels return before the kernel enters machine suspend.
            if (selected(pm_test), selected(mode)) != (test_level, "deep"):
                raise ValueError("PM test controls changed before the request")
            began = time.monotonic()
            result["request_attempted"] = True
            write(POWER / "state", "mem")
        except Exception as error:
            result.update(error=type(error).__name__, errno=getattr(error, "errno", None))
        finally:
            if mode_write_attempted and selected(mode) == "deep":
                write(mode, "s2idle")
            if test_write_attempted and selected(pm_test) == test_level:
                write(pm_test, "none")
            result["controls_restored"] = (selected(pm_test), selected(mode)) == ("none", "s2idle")
        if result["request_attempted"]:
            result["elapsed_seconds"] = round(time.monotonic() - began, 3)
            write(trace / "tracing_on", "0")
            result.update(trace_summary(read(trace / "trace")), after=statistics(),
                          all_cpus_restored=read(CPUS) == "0-3")
            for event in registration_errors:
                result["CPR_stages_reached"][event] = None
            result["passed"] = (
                "error" not in result and result["controls_restored"]
                and result["all_callback_phases_completed_once"]
                and (test_level == "platform" or result["all_secondary_CPU_cycles_completed_once"])
                and not result["machine_suspend_entered"] and result["all_cpus_restored"]
                and result["after"] == {"success": initial["success"] + 1, "fail": initial["fail"]}
            )
    return result
