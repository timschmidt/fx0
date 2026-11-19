#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare USB controller wake with an RTC fallback on the signed RAM boot."""

from pathlib import Path
import re
import time


USB_WAKE = Path("/sys/bus/platform/devices/ci_hdrc.0/power/wakeup")
USB_STATE = Path("/sys/class/udc/ci_hdrc.0/state")
LEAD_SECONDS = 5
SLOT_SECONDS = 22
PHASES = (
    ("disabled", False),
    ("enabled", False),
    ("disabled", True),
    ("enabled", True),
)


def classify_cycle(result, usb_irq):
    trace = result.get("trace", {})
    if (not result.get("s2idle_transition_observed") or not result["cleared_alarm"] or
            trace.get("complete_s2idle_intervals") != 1 or result["trace_events_lost"] != 0):
        return "unresolved"
    irqs = trace.get("wake_irqs_in_s2idle")
    if irqs == [result["after"]["rtc_irq"]] and result["first_wakeup_source"] == "rtc":
        return "rtc"
    if (irqs == [usb_irq] and result["first_wakeup_source"] == "another_irq" and
            result["RTC_interrupt_increment"] == 0 and
            result["after"]["rtc_seconds"] < result["RTC_target_seconds"]):
        return "usb_controller"
    return "unresolved"


def compare(probe, expected_boot, release, token, notes_hash, epoch):
    read = probe["read"]
    write = probe["write"]
    probe["guard"](expected_boot, release, token, notes_hash)
    original = read(USB_WAKE)
    if original not in {"enabled", "disabled"} or read(USB_STATE) != "configured":
        raise ValueError("the RAM USB gadget must be configured before testing")
    usb_irqs = [int(line.split(":", 1)[0]) for line in Path("/proc/interrupts").read_text().splitlines()
                if "ci_hdrc_msm" in line.split()]
    if len(usb_irqs) != 1 or usb_irqs[0] == probe["rtc_irq"]()[0]:
        raise ValueError("expected one USB-controller interrupt distinct from RTC")
    usb_irq, = usb_irqs
    cycles = []
    report = dict(passed=False, suspend_requested=False, usb_irq=usb_irq, epoch_boottime=epoch,
                  original_usb_wakeup=original, cycles=cycles)
    try:
        for index, (setting, traffic) in enumerate(PHASES):
            starts = epoch + LEAD_SECONDS + index * SLOT_SECONDS
            remaining = starts - time.clock_gettime(time.CLOCK_BOOTTIME)
            if remaining < 0:
                raise ValueError("missed a test slot")
            write(USB_WAKE, setting)
            if read(USB_WAKE) != setting or read(USB_STATE) != "configured":
                raise ValueError("USB wake setting or gadget state could not be verified")
            time.sleep(remaining)
            probe["guard"](expected_boot, release, token, notes_hash)
            with probe["capture_wake_irqs"]() as trace:
                result = probe["measure"](expected_boot, trace)
                counts = re.search(r"entries-in-buffer/entries-written:\s*(\d+)/(\d+)",
                                   read(trace / "trace")) if trace is not None else None
                lost = int(counts[2]) - int(counts[1]) if counts else None
            result.update(usb_wakeup=setting, host_traffic_scheduled=traffic,
                          trace_events_lost=lost)
            result["classified_wake"] = classify_cycle(result, usb_irq)
            cycles.append(result)
            report["suspend_requested"] |= result["suspend_requested"]
            print({"usb_wake_cycle": index + 1, "wake": result["classified_wake"]}, flush=True)
            if result["classified_wake"] == "unresolved":
                break
    finally:
        write(USB_WAKE, original)
        report["USB_wakeup_restored"] = read(USB_WAKE) == original
        report["RTC_alarm_cleared"] = not read(probe["ALARM"])
    report["passed_cycles"] = sum(item["classified_wake"] != "unresolved" for item in cycles)
    report["passed"] = (report["passed_cycles"] == len(PHASES) and report["USB_wakeup_restored"] and
                        report["RTC_alarm_cleared"])
    return report
