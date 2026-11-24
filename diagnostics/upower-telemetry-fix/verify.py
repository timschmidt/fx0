#!/usr/bin/env python3
"""Validate the complete configured Linux UPower regression run, without xfails."""
import argparse
import hashlib
import json
from pathlib import Path


def verify(path, family):
    data = path.read_bytes()
    cases = [
        json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()
    ]
    expected = {"current": 131, "backport": 122}[family]
    if len(cases) != expected:
        raise ValueError(f"expected {expected} cases, found {len(cases)}")
    names = [case["name"] for case in cases]
    if len(set(names)) != expected:
        raise ValueError("duplicate case names")
    for case in cases:
        if (
            case["result"] != "OK"
            or case["is_fail"] is not False
            or case["returncode"] != 0
        ):
            raise ValueError(f"case did not pass normally: {case['name']}")
    validity = [
        name for name in names if name.startswith("upower:Tests.test_validity_")
    ]
    if len(validity) != 28:
        raise ValueError("expected all 28 telemetry validity cases")
    required = {
        "upower:self-test",
        "upower:Tests.test_battery_without_charge_information",
        "upower:Tests.test_battery_with_design_information_only",
        "upower:Tests.test_battery_with_measurements_but_no_charge_information",
        "upower:Tests.test_battery_with_zero_remaining_charge",
        "upower:Tests.test_battery_overfull",
        "upower:Tests.test_tool_device_enumeration_failure",
        "upower:Tests.test_wacom_dongle",
    }
    if family == "current":
        required.add("upower:Tests.test_nan_percentage_battery_capacity")
    if not required.issubset(names):
        raise ValueError("missing required existing regression controls")
    return {
        "family": family,
        "all_passed": True,
        "case_count": expected,
        "validity_case_count": len(validity),
        "testlog_sha256": hashlib.sha256(data).hexdigest(),
        "cases": [
            {
                "name": case["name"],
                "result": case["result"],
                "returncode": case["returncode"],
            }
            for case in sorted(cases, key=lambda item: item["name"])
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", required=True, choices=["current", "backport"])
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.log, args.family)
    with args.report.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(
        f"{args.family}: {result['case_count']} normal passes, including 28 validity cases"
    )


if __name__ == "__main__":
    main()
