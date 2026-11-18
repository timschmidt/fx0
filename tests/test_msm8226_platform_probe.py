# SPDX-License-Identifier: MIT
from contextlib import nullcontext
import errno
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "platform_test",
    Path(__file__).resolve().parents[1] / "diagnostics/msm8226-pm/platform-test.py",
)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
rtc_spec = importlib.util.spec_from_file_location(
    "rtc_probe",
    Path(__file__).resolve().parents[1] / "diagnostics/rtc-s2idle/probe.py",
)
rtc_probe = importlib.util.module_from_spec(rtc_spec)
rtc_spec.loader.exec_module(rtc_probe)


class PlatformTest(unittest.TestCase):
    def test_control_store_is_attempted_once_and_keeps_the_first_errno(self):
        timeout = OSError(errno.ETIMEDOUT, "fixture")
        for module, state in ((probe, "mem"), (rtc_probe, "freeze")):
            with self.subTest(state=state):
                with patch.object(module.os, "open", return_value=7), \
                     patch.object(module.os, "write", side_effect=timeout) as write, \
                     patch.object(module.os, "close") as close:
                    with self.assertRaises(OSError) as raised:
                        module.write(module.POWER / "state", state)
                self.assertEqual(raised.exception.errno, errno.ETIMEDOUT)
                write.assert_called_once_with(7, (state + "\n").encode())
                close.assert_called_once_with(7)

    def test_trace_counts_cpr_only_during_late_suspend(self):
        log = "\n".join((
            "test: cpr_late_prepare: (outside)",
            "test: suspend_resume: dpm_suspend_late[2] begin",
            "test: cpr_late_prepare: (inside)",
            "test: suspend_resume: dpm_suspend_late[2] end",
            "test: cpr_check_rate: (outside)",
        ))
        result = probe.trace_summary(log)
        self.assertEqual(result["CPR_stages_reached"]["cpr_late_prepare"], 1)
        self.assertEqual(result["CPR_stages_reached"]["cpr_check_rate"], 0)
        self.assertFalse(result["machine_suspend_entered"])
        self.assertTrue(probe.trace_summary(log + "\ntest: suspend_resume: machine_suspend[3] begin")
                        ["machine_suspend_entered"])

    def test_failed_store_preserves_trace_and_restores_both_controls(self):
        pm_test = probe.POWER / "pm_test"
        mode = probe.POWER / "mem_sleep"
        trace = Path("/fixture/trace")
        values = {
            pm_test: "[none] platform",
            mode: "[s2idle] deep",
            probe.POWER / "wakeup_count": "3",
            probe.CPUS: "0-3",
            trace / "trace": "\n".join((
                "test: suspend_resume: dpm_suspend_late[2] begin",
                "test: cpr_late_prepare: (inside)",
                "test: suspend_resume: dpm_suspend_late[2] end",
            )),
        }
        stores = []

        def write(path, value):
            stores.append((path, value))
            if path == pm_test:
                values[path] = "[platform] none" if value == "platform" else "[none] platform"
            elif path == mode:
                values[path] = "[deep] s2idle" if value == "deep" else "[s2idle] deep"
            elif path == probe.POWER / "state":
                raise OSError(errno.ETIMEDOUT, "fixture")

        with patch.object(probe, "capture", return_value=nullcontext(trace)), \
             patch.object(probe, "read", side_effect=values.__getitem__), \
             patch.object(probe, "statistics", side_effect=(
                 {"success": 0, "fail": 0}, {"success": 0, "fail": 1},
             )), patch.object(probe, "write", side_effect=write):
            result = probe.exercise(lambda: None)

        self.assertFalse(result["passed"])
        self.assertTrue(result["controls_restored"])
        self.assertEqual(result["errno"], errno.ETIMEDOUT)
        self.assertEqual(result["after"], {"success": 0, "fail": 1})
        self.assertEqual(result["CPR_stages_reached"]["cpr_late_prepare"], 1)
        self.assertEqual(stores.count((probe.POWER / "state", "mem")), 1)

    def test_processor_cycles_require_each_secondary_and_no_cpu_zero(self):
        events = [
            f"test: suspend_resume: {action}[{cpu}] {edge}"
            for action in ("CPU_OFF", "CPU_ON")
            for cpu in (1, 2, 3)
            for edge in ("begin", "end")
        ]
        self.assertTrue(probe.trace_summary("\n".join(events))["all_secondary_CPU_cycles_completed_once"])
        self.assertFalse(probe.trace_summary("\n".join(events[:-1]))["all_secondary_CPU_cycles_completed_once"])
        events.append("test: suspend_resume: CPU_OFF[0] begin")
        self.assertFalse(probe.trace_summary("\n".join(events))["all_secondary_CPU_cycles_completed_once"])

    def test_machine_suspend_levels_are_refused(self):
        with self.assertRaisesRegex(ValueError, "bounded PM test level"):
            probe.exercise(lambda: self.fail("unexpected revalidation"), test_level="none")

    def test_core_level_requires_syscore_suspend_and_resume(self):
        pm_test, mode = probe.POWER / "pm_test", probe.POWER / "mem_sleep"
        trace = Path("/fixture/trace")
        actions = dict.fromkeys(probe.CALLBACKS, (2,))
        actions.update(dict.fromkeys(probe.HOTPLUG_ACTIONS, (1, 2, 3)))
        actions.update(dict.fromkeys(probe.SYSCORE_ACTIONS, (0,)))
        events = [
            f"test: suspend_resume: {action}[{value}] {edge}"
            for action, identifiers in actions.items()
            for value in identifiers
            for edge in ("begin", "end")
        ]
        for label, observed, accepted in (
            ("complete", events, True),
            ("missing resume", events[:-1], False),
            ("machine entry", events + ["test: suspend_resume: machine_suspend[3] begin"], False),
        ):
            with self.subTest(label=label):
                values = {pm_test: "[none] core", mode: "[s2idle] deep",
                          probe.POWER / "wakeup_count": "3", probe.CPUS: "0-3",
                          trace / "trace": "\n".join(observed)}

                def write(path, value):
                    if path == pm_test:
                        other = "none" if value == "core" else "core"
                        values[path] = f"[{value}] {other}"
                    if path == mode:
                        other = "s2idle" if value == "deep" else "deep"
                        values[path] = f"[{value}] {other}"

                with patch.object(probe, "capture", return_value=nullcontext(trace)), \
                     patch.object(probe, "read", side_effect=values.__getitem__), \
                     patch.object(probe, "statistics", side_effect=(
                         {"success": 0, "fail": 0}, {"success": 1, "fail": 0},
                     )), patch.object(probe, "write", side_effect=write):
                    result = probe.exercise(lambda: None, test_level="core")
                self.assertEqual(result["passed"], accepted)
                self.assertTrue(result["controls_restored"])

    def test_unavailable_cpr_probe_preserves_the_power_trace(self):
        events = []
        errors = {}

        def write(path, value, append=False):
            events.append((path.name, value, append))
            if value.startswith("p:") and "cpr_check_rate " in value:
                raise OSError(errno.EINVAL, "fixture")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "instances").mkdir()
            with patch.object(probe, "TRACEFS", root), patch.object(probe, "write", side_effect=write):
                with probe.capture(errors) as trace:
                    self.assertTrue(trace.is_dir())
                    self.assertIn(("enable", "1", False), events)
                    self.assertEqual(errors, {"cpr_check_rate": {"operation": "register", "errno": errno.EINVAL}})
                self.assertFalse(trace.exists())

        deleted = {value for name, value, append in events if append and value.startswith("-:")}
        self.assertEqual(deleted, {f"-:{probe.TRACE_GROUP}/{event}" for event in probe.CPR_STAGES
                                  if event != "cpr_check_rate"})


if __name__ == "__main__":
    unittest.main()
