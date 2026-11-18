"""Exercise the actual ARM dispatch object with synthetic MPIDR values."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import struct
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("entry_object", type=Path, help="ARM little-endian msm8226-warm-entry.o")
parser.add_argument("output_directory", type=Path)
arguments = parser.parse_args()
ENTRY = arguments.entry_object.resolve(strict=True)
OUT = arguments.output_directory.resolve()
OUT.mkdir(mode=0o700)


def command(*args):
    return subprocess.run(args, check=True, capture_output=True, timeout=20).stdout


object_bytes = bytearray(ENTRY.read_bytes())
assert object_bytes[:6] == b"\x7fELF\x01\x01"
section_offset, = struct.unpack_from("<I", object_bytes, 32)
section_size, count, name_index = struct.unpack_from("<HHH", object_bytes, 46)
assert section_size == 40
sections = [struct.unpack_from("<10I", object_bytes, section_offset + ix * section_size) for ix in range(count)]
names = sections[name_index]
strings = object_bytes[names[4]:names[4] + names[5]]
text, = [row for row in sections if strings[row[0]:].split(b"\0", 1)[0] == b".text"]
assert text[5] == 0x44
for offset, expected, substitute in (
    (0x00, 0xee100fb0, 0xe320f000),  # MPIDR supplied by the harness instead.
    (0x28, 0xf10c01c0, 0xe320f000),  # Userspace cannot mask asynchronous aborts.
    (0x38, 0xe320f003, 0xe12fff1e),  # Inspect the mailbox at the WFI boundary.
):
    target = text[4] + offset
    assert struct.unpack_from("<I", object_bytes, target) == (expected,)
    struct.pack_into("<I", object_bytes, target, substitute)

injected = OUT / "warm-entry-injected.o"
injected.write_bytes(object_bytes)
rows = [
    (0x80000000, 1, 1, 1),
    (0x80000001, 3, 1, 3),
    (0x80000002, 1, 1, 1),
    (0x80000003, 0, 1, 0),
    (0x80000003, 1, 0, 2),
    (0x80000003, 2, 0, 2),
    (0x80000003, 3, 0, 2),
    (0x80000003, 4, 0, 2),
    (0x80000003, 5, 0, 2),
    (0x80000103, 1, 1, 1),
    (0x80010003, 1, 1, 1),
    (0x80000004, 1, 1, 1),
]
controls = OUT / "controls.S"
controls.write_text("""
.syntax unified
.arch armv7-a
.arm
.text
.global _start
_start:
    ldr r4, =cases
    ldr r5, =cases_end
    ldr r10, =msm8226_warm_probe_state
next:
    ldmia r4!, {r0, r6-r8}
    str r6, [r10]
    mov r9, #0
    bl msm8226_warm_probe_entry
    cmp r9, r7
    bne failed
    ldr r2, [r10]
    cmp r2, r8
    bne failed
    cmp r4, r5
    bne next
    mov r0, #0
    b done
failed:
    mov r0, #1
done:
    mov r7, #1
    svc #0

.global cpu_resume_arm
cpu_resume_arm:
    mov r9, #1
    bx lr

.data
.balign 64
.global msm8226_warm_probe_state
msm8226_warm_probe_state:
    .word 0
cases:
""" + "".join(".word " + ", ".join(hex(word) for word in row) + "\n" for row in rows) + "cases_end:\n")
controls_object = OUT / "controls.o"
command("clang-21", "--target=arm-linux-gnueabihf", "-march=armv7-a", "-c", str(controls), "-o", str(controls_object))
bases = [0x200000, 0x600000]
for address in bases:
    binary = OUT / f"controls-{address:#x}"
    command("ld.lld-21", "-static", "-e", "_start", f"-Ttext={address:#x}",
            str(controls_object), str(injected), "-o", str(binary))
    command("/usr/bin/qemu-arm-static", str(binary))

disassembly = command("llvm-objdump-21", "-dr", str(ENTRY)).decode()
assert disassembly.count("R_ARM_JUMP24\tcpu_resume_arm") == 2
assert "R_ARM_REL32\tmsm8226_warm_probe_state" in disassembly
(OUT / "original-object-disassembly.txt").write_text(disassembly)
report = {
    "passed": True, "ARM_controls": len(rows) * len(bases),
    "object_SHA256": sha256(ENTRY.read_bytes()).hexdigest(),
    "simulated_register_and_park_only": True, "hardware_contacted": False,
}
(OUT / "warm-probe-host-controls.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
