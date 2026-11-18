"""Compile and exercise the restart state transitions from the ARM source."""
import os
from pathlib import Path
import re
import subprocess

import pytest

HERE = Path(__file__).resolve().parent


def function(source, name):
    return re.search(rf"(?m)^\w[^\n]*\b{name}\([^\n]*\)\n\{{\n[\s\S]+?^\}}", source)[0]


def test_msm8226_secondary_restart(tmp_path):
    worktree = Path(os.environ.get("FX0_KERNEL_SOURCE", "/nonexistent"))
    platform = worktree / "arch/arm/mach-qcom/platsmp.c"
    arm = worktree / "arch/arm/kernel/smp.c"
    if not platform.is_file() or "MSM8226_RESTART_ACCEPTED" not in (source := platform.read_text()):
        pytest.skip("MSM8226 secondary restart candidate source required")

    state = re.search(r"enum msm8226_restart_state \{[^}]+\};", source)[0]
    functions = ("msm8226_cpu_disable", "msm8226_cancel_secondary_boot",
                 "msm8226_cpu_die", "msm8226_restart_secondary")
    (tmp_path / "msm8226-restart-source.h").write_text(
        "#define MSM8226_WAKE_SGI 1\n" + state
        + "\nstatic DEFINE_PER_CPU(atomic_t, msm8226_restart);\n"
        + "\n\n".join(function(source, name) for name in functions) + "\n"
    )
    (tmp_path / "arm-secondary-boot-source.h").write_text(function(arm.read_text(), "__cpu_up") + "\n")
    binary = tmp_path / "restart"
    subprocess.run(
        [os.environ.get("CC", "cc"), "-std=gnu11", "-Wall", "-Wextra", "-Werror",
         "-I", str(tmp_path), str(HERE / "msm8226-secondary-restart-harness.c"), "-o", str(binary)],
        check=True, timeout=30,
    )
    subprocess.run([binary], check=True, timeout=5)
