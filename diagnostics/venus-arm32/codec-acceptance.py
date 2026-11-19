#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Generate and verify a small H.264 workload for the Venus RAM candidate."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import time

WIDTH, HEIGHT, FRAMES, FPS = 320, 240, 12, 15
LUMA = WIDTH * HEIGHT
FRAME_SIZE = LUMA * 3 // 2
RELEASE = "6.18.64-fx0-venus-ram-alpine"
TOKEN = "fx0.native_trial=venus-6.18.64-02"
VIDIOC_QUERYCAP = 0x80685600
CAPABILITY = struct.Struct("=16s32s32s6I")
M2M_MPLANE = 0x4000
STREAMING = 0x04000000
DEVICE_CAPS = 0x80000000


def sha(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def levels(index):
    return [214 if cell == index else 41 + 11 * (cell % 6) for cell in range(FRAMES)]


def raw_video():
    video = bytearray()
    for index in range(FRAMES):
        values = levels(index)
        for row in range(3):
            line = b"".join(bytes([value]) * 80 for value in values[row * 4:row * 4 + 4])
            video += line * 80
        video += bytes([95, 159]) * (LUMA // 4)
    return video


def check_frames(path, *, count=FRAMES):
    decoded = path.read_bytes()
    if not 1 <= count <= FRAMES or len(decoded) != FRAME_SIZE * count:
        raise ValueError("unexpected decoded size or frame count")
    maximum = 0
    for frame in range(count):
        start = frame * FRAME_SIZE
        for cell, expected in enumerate(levels(frame)):
            left, top = cell % 4 * 80 + 24, cell // 4 * 80 + 24
            total = sum(sum(decoded[start + y * WIDTH + left:start + y * WIDTH + left + 32])
                        for y in range(top, top + 32))
            error = abs(round(total / 1024) - expected)
            if error > 18:
                raise ValueError(f"incorrect luma in frame {frame}, cell {cell}")
            maximum = max(maximum, error)
        for plane, expected in enumerate((95, 159)):
            offset = start + LUMA + plane * (LUMA // 4)
            mean = sum(decoded[offset:offset + LUMA // 4]) / (LUMA // 4)
            if abs(mean - expected) > 18:
                raise ValueError(f"incorrect chroma in frame {frame}, plane {plane}")
    return {"frames": count, "luma_cells": count * FRAMES,
            "max_luma_mean_error": maximum, "chroma_planes": count * 2}


def run_command(executable, args, directory, label):
    result = subprocess.run(
        [str(executable), "-nostdin", "-hide_banner", "-loglevel", "info", *args],
        cwd=directory, capture_output=True, timeout=38,
    )
    (directory / f"{label}.log").write_bytes(result.stderr)
    if result.returncode:
        raise ValueError(f"{label} exited with status {result.returncode}")
    return result.stderr.decode(errors="replace")


def generate(directory, ffmpeg):
    directory.mkdir(mode=0o700)
    (directory / "reference.nv12").write_bytes(raw_video())
    run_command(ffmpeg, [
        "-f", "rawvideo", "-pixel_format", "nv12", "-video_size", f"{WIDTH}x{HEIGHT}",
        "-framerate", str(FPS), "-i", "reference.nv12", "-an", "-c:v", "libx264",
        "-threads", "1", "-preset", "ultrafast", "-tune", "zerolatency",
        "-pix_fmt", "yuv420p", "-profile:v", "baseline", "-g", str(FRAMES),
        "-bf", "0", "-frames:v", str(FRAMES), "-f", "h264", "reference.h264",
    ], directory, "reference-encode")


def identify_nodes():
    roles = {"Qualcomm Venus video encoder": "encoder", "Qualcomm Venus video decoder": "decoder"}
    result = {}
    for node in sorted(Path("/dev").glob("video[0-9]*")):
        try:
            with node.open("rb", buffering=0) as handle:
                raw = bytearray(CAPABILITY.size)
                fcntl.ioctl(handle.fileno(), VIDIOC_QUERYCAP, raw)
        except OSError:
            continue
        driver, card, bus, _, caps, device, *_ = CAPABILITY.unpack(raw)
        driver, card, bus = (field.split(b"\0", 1)[0].decode(errors="replace")
                             for field in (driver, card, bus))
        active_caps = device if caps & DEVICE_CAPS else caps
        required = M2M_MPLANE | STREAMING
        role = roles.get(card)
        if driver == "qcom-venus" and bus == "platform:qcom-venus" and role and active_caps & required == required:
            if role in result:
                raise ValueError("ambiguous Venus role")
            result[role] = str(node)
    if set(result) != {"encoder", "decoder"}:
        raise ValueError("both Venus mem-to-mem roles must be present")
    return result


def only_expected_node(log, node):
    matches = re.findall(r"Using device (/dev/video\d+)\b", log)
    if matches != [node]:
        raise ValueError("FFmpeg did not use the verified Venus node")


def target_gate(*, token=TOKEN, firmware_target="/run/fx0-venus-firmware"):
    words = Path("/proc/cmdline").read_text().split()
    mandatory = (token, "module.sig_enforce=1", "module_blacklist=wcn36xx",
                 "firmware_class.path=/run/fx0-venus-firmware")
    if (not token.startswith("fx0.native_trial=venus-") or os.uname().release != RELEASE
            or any(words.count(word) != 1 for word in mandatory)):
        raise ValueError("current boot does not match the Venus RAM candidate")
    if Path("/sys/module/module/parameters/sig_enforce").read_text().strip() != "Y":
        raise ValueError("kernel module signatures are unenforced")
    allowed_targets = {
        "/run/fx0-venus-firmware",
        "/run/msm-firmware-loader/target",
        "/run/fx0-venus-combined-firmware",
    }
    if (firmware_target not in allowed_targets
            or Path("/sys/module/firmware_class/parameters/path").read_text().strip() != firmware_target):
        raise ValueError("firmware search path does not match the Venus RAM candidate")
    if Path("/proc/sys/kernel/tainted").read_text().strip() != "0":
        raise ValueError("kernel taint prevents acceptance")
    if Path("/sys/class/ieee80211").exists() and any(Path("/sys/class/ieee80211").iterdir()):
        raise ValueError("WLAN device present in the candidate")
    if not any(row.split()[4] == "/run" and row.split(" - ", 1)[1].startswith("tmpfs ")
               for row in Path("/proc/self/mountinfo").read_text().splitlines()):
        raise ValueError("candidate workspace must be on /run tmpfs")
    armed = Path("/run/fx0-native-trial/return-armed").read_text().splitlines()
    if "DEADLINE=420" not in armed or f"TOKEN={token}" not in armed:
        raise ValueError("early return helper is not recorded")
    pids = [line.removeprefix("PID=") for line in armed if line.startswith("PID=")]
    if len(pids) != 1 or not pids[0].isdecimal():
        raise ValueError("early return helper PID is absent")
    process = Path("/proc") / pids[0]
    if (process / "exe").readlink().name.removesuffix(" (deleted)") != "fx0-native-return":
        raise ValueError("early return helper process differs from the recorded process")
    subprocess.run(["systemctl", "is-active", "--quiet", "fx0-native-return.timer"],
                   check=True, timeout=8)
    if time.clock_gettime(time.CLOCK_BOOTTIME) > 205:
        raise ValueError("insufficient time before automatic return")
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


def prepare_trial(binary, binary_hash, fixture, reference_hash, token, firmware_target):
    os.umask(0o077)
    binary, fixture = binary.resolve(strict=True), fixture.resolve(strict=True)
    boot = target_gate(token=token, firmware_target=firmware_target)
    if sha(binary) != binary_hash or sha(fixture) != reference_hash:
        raise ValueError("test input hash differs from the pinned fixture")
    nodes = identify_nodes()
    directory = Path(tempfile.mkdtemp(prefix="fx0-venus-", dir="/run"))
    (directory / "reference.h264").write_bytes(fixture.read_bytes())
    return binary, boot, nodes, directory


RAW_OUTPUT = ("-an", "-fps_mode", "passthrough", "-pix_fmt", "yuv420p", "-c:v", "rawvideo",
              "-f", "rawvideo")


def decode_reference(binary, decoder, directory):
    log = run_command(binary, ["-f", "h264", "-c:v", "h264_v4l2m2m", "-i", "reference.h264",
                               *RAW_OUTPUT, "decoded.yuv"], directory, "hardware-decode")
    only_expected_node(log, decoder)
    return directory / "decoded.yuv"


def encode_reference(binary, encoder, directory):
    (directory / "reference.nv12").write_bytes(raw_video())
    encode = run_command(binary, [
        "-f", "rawvideo", "-pixel_format", "nv12", "-video_size", f"{WIDTH}x{HEIGHT}",
        "-framerate", str(FPS), "-i", "reference.nv12", "-an", "-pix_fmt", "nv12",
        "-c:v", "h264_v4l2m2m", "-b:v", "800k", "-g", str(FRAMES), "-bf", "0",
        "-frames:v", str(FRAMES), "-f", "h264", "hardware.h264",
    ], directory, "hardware-encode")
    only_expected_node(encode, encoder)
    run_command(binary, ["-f", "h264", "-c:v", "h264", "-i", "hardware.h264",
                         *RAW_OUTPUT, "encoded-check.yuv"], directory, "software-verify-encoding")
    return directory / "encoded-check.yuv"


def run_trial(binary, binary_hash, fixture, reference_hash, *, token=TOKEN,
              firmware_target="/run/fx0-venus-firmware"):
    binary, boot, nodes, directory = prepare_trial(binary, binary_hash, fixture, reference_hash,
                                                    token, firmware_target)
    encoded = encode_reference(binary, nodes["encoder"], directory)
    decoded = decode_reference(binary, nodes["decoder"], directory)
    report = {"boot": boot, "nodes": nodes,
              "encode_checked_in_software": check_frames(encoded),
              "hardware_decode_of_reference": check_frames(decoded)}
    if Path("/proc/sys/kernel/random/boot_id").read_text().strip() != boot:
        raise ValueError("boot changed during codec acceptance")
    (directory / "acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


def run_encoder_trial(binary, binary_hash, fixture, reference_hash, *, token=TOKEN,
                      firmware_target="/run/fx0-venus-firmware"):
    binary, boot, nodes, directory = prepare_trial(binary, binary_hash, fixture, reference_hash,
                                                    token, firmware_target)
    encoded = check_frames(encode_reference(binary, nodes["encoder"], directory))
    if Path("/proc/sys/kernel/random/boot_id").read_text().strip() != boot:
        raise ValueError("boot changed during encoder acceptance")
    report = {"boot": boot, "encoder_node": nodes["encoder"], "encode_checked_in_software": encoded}
    (directory / "encoder-acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


def run_decoder_trial(binary, binary_hash, fixture, reference_hash, *, token=TOKEN,
                      firmware_target="/run/fx0-venus-firmware"):
    binary, boot, nodes, directory = prepare_trial(binary, binary_hash, fixture, reference_hash,
                                                    token, firmware_target)
    decoded = check_frames(decode_reference(binary, nodes["decoder"], directory))
    if Path("/proc/sys/kernel/random/boot_id").read_text().strip() != boot:
        raise ValueError("boot changed during decoder acceptance")
    report = {"boot": boot, "decoder_node": nodes["decoder"], "hardware_decode_of_reference": decoded}
    (directory / "decoder-acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("generate")
    make.add_argument("directory", type=Path)
    make.add_argument("--ffmpeg", type=Path, default=Path("/usr/bin/ffmpeg"))
    verify = commands.add_parser("check-frames")
    verify.add_argument("raw_yuv420p", type=Path)
    trial = commands.add_parser("run")
    trial.add_argument("ffmpeg", type=Path)
    trial.add_argument("ffmpeg_sha256")
    trial.add_argument("reference", type=Path)
    trial.add_argument("reference_sha256")
    args = parser.parse_args()
    if args.command == "generate":
        generate(args.directory, args.ffmpeg.resolve(strict=True))
    elif args.command == "check-frames":
        print(json.dumps(check_frames(args.raw_yuv420p), indent=2))
    else:
        run_trial(args.ffmpeg, args.ffmpeg_sha256, args.reference, args.reference_sha256)


if __name__ == "__main__":
    main()
