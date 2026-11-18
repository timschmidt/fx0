#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure one RTC-backed s2idle cycle on a WLAN-disabled Fx0 RAM boot."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

POWER = Path("/sys/power")
RTC = Path("/sys/class/rtc/rtc0")
ALARM = RTC / "wakealarm"
BOOT_ID = Path("/proc/sys/kernel/random/boot_id")
TIMER = "fx0-native-return.timer"
RTC_DELAY = 14


def read(path):
    return path.read_text().strip()


def write(path, value):
    with path.open("w") as file:
        file.write(value + "\n")


def rtc_irq():
    interrupts = Path("/proc/interrupts").read_text().splitlines()
    cpu_count = len(interrupts[0].split()) if interrupts else 0
    rows = [line.split(":", 1) for line in interrupts[1:]
            if line.rstrip().endswith("pm8xxx_rtc_alarm")]
    if len(rows) != 1 or not cpu_count:
        raise ValueError("expected exactly one PM8xxx alarm interrupt")
    number, contents = rows[0]
    return int(number), sum(map(int, contents.split()[:cpu_count]))


def snapshot():
    stats = POWER / "suspend_stats"
    irq, irq_count = rtc_irq()
    return {
        "boot_id": read(BOOT_ID),
        "rtc_irq": irq,
        "rtc_irq_count": irq_count,
        "rtc_seconds": int(read(RTC / "since_epoch")),
        "pm_wakeup_irq": int(read(POWER / "pm_wakeup_irq") or 0),
        "suspend_success": int(read(stats / "success")),
        "suspend_fail": int(read(stats / "fail")),
        "boot_seconds": time.clock_gettime(time.CLOCK_BOOTTIME),
        "monotonic_seconds": time.monotonic(),
    }


def classify(before, after, deadline):
    slept = ((after["boot_seconds"] - before["boot_seconds"]) -
             (after["monotonic_seconds"] - before["monotonic_seconds"]))
    transition = (before["boot_id"] == after["boot_id"] and
                  after["suspend_success"] == before["suspend_success"] + 1 and
                  after["suspend_fail"] == before["suspend_fail"] and slept > 0.5)
    irq_change = after["rtc_irq_count"] - before["rtc_irq_count"]
    matching_irq = (after["rtc_irq"] == before["rtc_irq"] == after["pm_wakeup_irq"])
    delivered = irq_change == 1 and after["rtc_seconds"] >= deadline
    source = "unresolved"
    if transition and matching_irq and delivered:
        source = "rtc"
    elif transition and after["pm_wakeup_irq"] not in (0, before["rtc_irq"]) and not delivered:
        source = "another_irq"
    return {"s2idle_transition_observed": transition, "first_wakeup_source": source,
            "RTC_interrupt_increment": irq_change, "inactive_clock_seconds": round(slept, 3)}


def guard(expected_boot, release, token, notes_hash):
    if os.geteuid() != 0 or read(BOOT_ID) != expected_boot or os.uname().release != release:
        raise ValueError("current boot differs from the prepared RAM candidate")
    words = Path("/proc/cmdline").read_text().split()
    if not token.startswith("fx0.native_trial=") or words.count(token) != 1:
        raise ValueError("expected exactly one trial token")
    if hashlib.sha256(Path("/sys/kernel/notes").read_bytes()).hexdigest() != notes_hash:
        raise ValueError("candidate kernel notes differ")
    if words.count("module_blacklist=wcn36xx") != 1 or list(Path("/sys/class/ieee80211").glob("*")):
        raise ValueError("the candidate must run with WLAN disabled")
    if read(Path("/sys/module/module/parameters/sig_enforce")) != "Y":
        raise ValueError("kernel signatures are unenforced")
    if read(Path("/proc/sys/kernel/tainted")) != "0":
        raise ValueError("kernel is tainted")
    early = read(Path("/run/fx0-native-trial/return-armed")).splitlines()
    pids = [line.removeprefix("PID=") for line in early if line.startswith("PID=")]
    if ["DEADLINE=420", f"TOKEN={token}"] != [row for row in early if not row.startswith("PID=")]:
        raise ValueError("early return marker does not match the trial")
    if len(pids) != 1 or not pids[0].isdecimal():
        raise ValueError("early return PID is missing")
    process = Path("/proc") / pids[0] / "exe"
    if process.readlink().name.removesuffix(" (deleted)") != "fx0-native-return":
        raise ValueError("early return executable differs")
    subprocess.run(["systemctl", "is-active", "--quiet", TIMER], check=True, timeout=8)
    if time.clock_gettime(time.CLOCK_BOOTTIME) > 235:
        raise ValueError("the boot is too close to automatic return")
    if "freeze" not in read(POWER / "state").split() or read(RTC / "device/power/wakeup") != "enabled":
        raise ValueError("s2idle or RTC wake is unavailable")


def probe(expected_boot, release, token, notes_hash):
    guard(expected_boot, release, token, notes_hash)
    before = snapshot()
    if read(ALARM):
        raise ValueError("another owner has an armed RTC alarm")
    target = int(read(RTC / "since_epoch")) + RTC_DELAY
    report = {"passed": False, "suspend_requested": False, "cleared_alarm": False, "before": before}
    armed = False
    try:
        armed = True
        write(ALARM, str(target))
        if read(ALARM) != str(target):
            raise ValueError("RTC alarm readback differs")
        report["RTC_target_seconds"] = target
        wake_count = read(POWER / "wakeup_count")
        if int(read(RTC / "since_epoch")) >= target - 8 or read(BOOT_ID) != expected_boot:
            raise ValueError("alarm deadline changed before requesting suspend")
        write(POWER / "wakeup_count", wake_count)
        report["suspend_requested"] = True
        write(POWER / "state", "freeze")
        after = snapshot()
        report.update(classify(before, after, target), after=after)
        report["passed"] = report["first_wakeup_source"] == "rtc"
    except Exception as error:
        report["failure"] = type(error).__name__
        report["failure_reason"] = str(error).splitlines()[0]
    finally:
        current = read(ALARM)
        if armed and current == str(target):
            write(ALARM, "0")
        report["cleared_alarm"] = not read(ALARM)
        if not report["cleared_alarm"]:
            report["passed"] = False
    return report


def interrupted(signum, frame):
    raise InterruptedError("probe interrupted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("boot_id")
    parser.add_argument("release")
    parser.add_argument("token")
    parser.add_argument("notes_sha256")
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    result = probe(args.boot_id, args.release, args.token, args.notes_sha256)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
