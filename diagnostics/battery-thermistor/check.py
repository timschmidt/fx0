#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Check Fx0 units/table and execute the actual generic ADC interpolation."""
import argparse
from fractions import Fraction
from pathlib import Path
import re
import subprocess
import tempfile


def definition(text, start):
    begin = text.index(start)
    brace = text.index("{", begin)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[begin:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("linux", type=Path)
    parser.add_argument("vendor", type=Path)
    args = parser.parse_args()
    dtsi = (args.linux / "arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai-battery.dtsi").read_text()
    lookup = dtsi.split("temperature-lookup-table = <", 1)[1].split(">;", 1)[0]
    numbers = [int(n) for n in re.findall(r"-?\d+", lookup)]
    rows = list(zip(numbers[::2], numbers[1::2]))
    vendor = (args.vendor / "drivers/hwmon/qpnp-adc-common.c").read_text()
    table = vendor.split("static const struct qpnp_vadc_map_pt adcmap_btm_threshold[] = {", 1)[1].split("};", 1)[0]
    original = [(int(t), int(v)) for t, v in re.findall(r"\{\s*(-?\d+),\s*(\d+)\s*\}", table)]
    assert rows == [(t * 100, v) for t, v in original], "Table/units differ from LG reference"
    assert len(rows) == 83 and all(a[0] < b[0] and a[1] > b[1] for a, b in zip(rows, rows[1:]))
    driver = (args.linux / "drivers/thermal/thermal-generic-adc.c").read_text()
    struct = definition(driver, "struct gadc_thermal_info {") + ";\n"
    function = definition(driver, "static int gadc_thermal_adc_to_temp(")
    math = (args.linux / "include/linux/math.h").read_text()
    macro_lines = math[math.index("#define mult_frac("):].splitlines()
    macro = []
    for line in macro_lines:
        macro.append(line)
        if not line.endswith("\\"):
            break
    tests = list(range(1801)) + [-2147483648, 2147483647]

    def expected(value):
        if value >= rows[0][1]:
            return rows[0][0]
        for (hi_t, hi_v), (lo_t, lo_v) in zip(rows, rows[1:]):
            if value >= lo_v:
                return hi_t + int(Fraction((lo_t - hi_t) * (value - hi_v), lo_v - hi_v))
        return rows[-1][0]

    prelude = "#include <stdint.h>\n#include <stdio.h>\ntypedef int32_t s32;\n"
    source = prelude + "\n".join(macro) + "\n" + struct + function
    source += "\nstatic s32 table[] = {" + ",".join(map(str, numbers)) + "};\n"
    source += "int main(void) { struct gadc_thermal_info g = {.lookup_table=table,.nlookup_table=83};\n"
    source += "int values[] = {" + ",".join(map(str, tests)) + "};\n"
    source += 'for (unsigned i=0;i<sizeof(values)/sizeof(values[0]);i++) printf("%d\\n",gadc_thermal_adc_to_temp(&g,values[i]));\n'
    source += "g.lookup_table=0; if (gadc_thermal_adc_to_temp(&g,-12345)!=-12345) return 1; return 0; }\n"
    with tempfile.TemporaryDirectory(prefix="fx0-thermistor-") as temporary:
        path = Path(temporary)
        (path / "check.c").write_text(source)
        subprocess.run(["clang", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined", "-fno-sanitize-recover=all", str(path / "check.c"), "-o", str(path / "check")], check=True)
        actual = list(map(int, subprocess.check_output([str(path / "check")], text=True).splitlines()))
    assert actual == [expected(value) for value in tests], "Interpolation mismatch"
    assert expected(737) == 25000 and expected(664) == 31000
    print(f"PASS: {len(rows)} LG table points; {len(tests)} actual interpolation cases and passthrough under ASan/UBSan")


if __name__ == "__main__":
    main()
