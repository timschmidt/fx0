"""Check that a rejected CPU online write does not resend the wake request."""
import errno
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

import pytest

WORKER = Path(__file__).resolve().parents[1] / "diagnostics/msm8226-pm/cpu3-warm-probe.py"


def test_rejected_cpu_online_write_is_unbuffered(monkeypatch, tmp_path):
    exercise = runpy.run_path(str(WORKER))["exercise"]
    scope = exercise.__globals__
    cpu3 = tmp_path / "cpu3-online"
    online = tmp_path / "online"
    power = tmp_path / "power"
    power.mkdir()
    (power / "mem_sleep").write_text("[s2idle]\n")
    (power / "suspend_stats").mkdir()
    for name in ("success", "fail"):
        (power / "suspend_stats" / name).write_text("0\n")
    online.write_text("0-3\n")
    vector = 0
    clock = 0.0
    writes = []
    real_open = Path.open

    class CPUControl:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def write(self, data):
            nonlocal vector
            writes.append(data)
            if data == b"0\n":
                online.write_text("0-2\n")
                vector = 1
                return len(data)
            raise OSError(errno.EIO, "simulated online failure")

    def open_control(path, mode="r", buffering=-1, *args, **kwargs):
        if path == cpu3:
            assert mode == "wb" and buffering == 0
            return CPUControl()
        return real_open(path, mode, buffering, *args, **kwargs)

    def sleep(seconds):
        nonlocal clock
        clock += seconds

    def run_child(argv):
        assert argv[1:3] == ["-B", "-c"]
        with monkeypatch.context() as child:
            child.setattr(sys, "argv", ["-c", argv[4]])
            with pytest.raises(SystemExit) as exited:
                exec(compile(argv[3], "<online-request>", "exec"), {})
        status = exited.value.code
        return SimpleNamespace(poll=lambda: status, returncode=status)

    monkeypatch.setattr(Path, "open", open_control)
    scope.update(CPU3=cpu3, ONLINE=online, POWER=power, state=lambda: vector,
                 subprocess=SimpleNamespace(Popen=run_child),
                 time=SimpleNamespace(monotonic=lambda: clock, sleep=sleep))
    result = exercise(lambda: None)
    assert result["online_write_status"] == errno.EIO
    assert result["online_request_count"] == 1
    assert writes == [b"0\n", b"1\n"]
    assert result["suspend_counters_unchanged"]
