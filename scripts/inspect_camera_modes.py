#!/usr/bin/env python3
"""Inspect camera register-setting geometry without executing vendor libraries.

The ELF reader recognizes the stock Qualcomm ARM32 register-setting ABI. The C
reader recognizes numeric register tables in the recovered Tegra GPL drivers.
Neither reader proves that a setting is reachable or works on a physical sensor.
"""

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path


def geometry(registers):
    values = {address: value for address, value, _ in registers}
    required = (0x0340, 0x0342, 0x034C, 0x034E)
    if not all(address + byte in values for address in required for byte in (0, 1)):
        return None

    def pair(address):
        return values[address] * 256 + values[address + 1]

    result = {
        "register_count": len(registers),
        "width": pair(0x034C),
        "height": pair(0x034E),
        "frame_lines": pair(0x0340),
        "line_length_pixels": pair(0x0342),
    }
    for name, address in (
        ("coarse_exposure_lines", 0x0202),
        ("crop_x_start", 0x0344),
        ("crop_y_start", 0x0346),
        ("crop_x_end", 0x0348),
        ("crop_y_end", 0x034A),
    ):
        if address in values and address + 1 in values:
            result[name] = pair(address)
    return result


def elf_settings(data):
    if len(data) < 52 or data[:7] != b"\x7fELF\x01\x01\x01":
        raise ValueError("expected a little-endian ELF32 file")
    elf_type, machine = struct.unpack_from("<HH", data, 16)
    if elf_type != 3 or machine != 40:
        raise ValueError("expected an ARM shared object")
    phoff, shoff = struct.unpack_from("<II", data, 28)
    phsize, phnum, shsize, shnum = struct.unpack_from("<4H", data, 42)
    if phsize != 32 or shsize != 40:
        raise ValueError("unexpected ELF header sizes")
    if phoff + phnum * phsize > len(data) or shoff + shnum * shsize > len(data):
        raise ValueError("truncated ELF header table")
    segments = [struct.unpack_from("<8I", data, phoff + i * phsize) for i in range(phnum)]

    def file_offset(address, size):
        for kind, offset, base, _, filesz, _, _, _ in segments:
            if kind == 1 and base <= address and address + size <= base + filesz:
                result = offset + address - base
                if result + size <= len(data):
                    return result
        raise ValueError("address outside file-backed load segments")

    seen = set()
    result = []
    for i in range(shnum):
        section = struct.unpack_from("<10I", data, shoff + i * shsize)
        _, kind, _, _, offset, size, _, _, _, entry_size = section
        if kind != 9:  # SHT_REL
            continue
        if entry_size != 8 or size % entry_size or offset + size > len(data):
            raise ValueError("invalid ELF relocation table")
        for at in range(offset, offset + size, entry_size):
            location, info = struct.unpack_from("<II", data, at)
            if info & 255 != 23:  # R_ARM_RELATIVE
                continue
            try:
                setting = file_offset(location, 20)
                pointer, count, address_type, data_type, delay = struct.unpack_from(
                    "<IH2xIIH", data, setting
                )
                if address_type != 2 or data_type != 1:
                    continue  # 16-bit register address, 8-bit register data
                if not 1 <= count <= 1000 or delay > 1000 or pointer in seen:
                    continue
                start = file_offset(pointer, count * 8)
            except ValueError:
                continue
            registers = [struct.unpack_from("<HHI", data, start + j * 8) for j in range(count)]
            if any(value > 255 or wait > 1000 for _, value, wait in registers):
                continue
            seen.add(pointer)
            setting_geometry = geometry(registers)
            if setting_geometry:
                setting_geometry["setting_delay_ms"] = delay
                result.append(setting_geometry)
    return result


def c_settings(data):
    text = data.decode("utf-8")
    arrays = re.finditer(
        r"static\s+(?:const\s+)?struct\s+\w+\s+(\w+)\[\]\s*=\s*\{(.*?)^\};",
        text,
        re.DOTALL | re.MULTILINE,
    )
    number = r"(?:0[xX][0-9a-fA-F]+|[0-9]+)"
    result = []
    for match in arrays:
        registers = [
            (int(address, 0), int(value, 0), 0)
            for address, value in re.findall(
                r"\{\s*(" + number + r")\s*,\s*(" + number + r")\s*\}", match[2]
            )
        ]
        setting_geometry = geometry(registers)
        if not setting_geometry:
            continue
        setting_geometry["array_name"] = match[1]
        label = re.fullmatch(r"mode_([0-9]+)[xX]([0-9]+)", match[1])
        if label:
            setting_geometry["array_label_matches_register_geometry"] = (
                int(label[1]) == setting_geometry["width"]
                and int(label[2]) == setting_geometry["height"]
            )
        result.append(setting_geometry)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, action="append", default=[])
    parser.add_argument("--c-source", type=Path, action="append", default=[])
    args = parser.parse_args()
    if not args.elf and not args.c_source:
        parser.error("provide --elf or --c-source")
    reports = []
    for kind, paths, inspect in (
        ("ARM32 register-setting descriptors", args.elf, elf_settings),
        ("numeric C register arrays", args.c_source, c_settings),
    ):
        for path in paths:
            try:
                data = path.read_bytes()
                settings = inspect(data)
                if not settings:
                    raise ValueError("no recognized register setting contains geometry")
            except (OSError, ValueError, struct.error) as error:
                parser.error(f"{path}: {error}")
            reports.append({
                "input": path.name,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "method": kind,
                "register_settings_with_geometry": settings,
            })
    print(json.dumps({
        "scope": "Static register values only; no execution, hardware access or capture qualification",
        "inputs": reports,
    }, indent=2))


if __name__ == "__main__":
    main()
