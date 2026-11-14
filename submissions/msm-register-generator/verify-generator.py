#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare actual register generators across Python hash seeds."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ARRAY = re.compile(r"template<> constexpr inline uint16_t (\w+)_REGS<([^>]+)>\[\] = \{\n(.*?)\n\};", re.S)

def semantics(data):
    text = data.decode("utf-8")
    rows = ARRAY.findall(text)
    arrays = {(usage, variant): body for usage, variant, body in rows}
    if len(arrays) != len(rows) or len(arrays) < 2:
        raise RuntimeError("expected distinct usage arrays for multiple variants")
    return arrays, ARRAY.sub("", text)

def generate(script, registers, seed):
    command = [sys.executable, "-B", str(script), "--no-validate", "--rnn",
               str(registers), "--xml", str(registers / "adreno/a6xx.xml"), "c-defines"]
    env = dict(os.environ, PYTHONHASHSEED=str(seed))
    return subprocess.run(command, env=env, check=True, capture_output=True).stdout

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    parser.add_argument("--registers", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = []
    reference = None
    for seed in [0, 1, 2, 17, 107]:
        row = {"seed": seed}
        for name, script in [("before", args.before), ("after", args.after)]:
            data = generate(script.resolve(), args.registers.resolve(), seed)
            current = semantics(data)
            if reference is None:
                reference = current
            if current != reference:
                raise RuntimeError("usage array values or other declarations changed")
            row[name + "_SHA256"] = hashlib.sha256(data).hexdigest()
        records.append(row)
    before = {row["before_SHA256"] for row in records}
    after = {row["after_SHA256"] for row in records}
    if len(before) <= 1:
        raise RuntimeError("baseline did not reproduce the hash-seed dependence")
    if len(after) != 1:
        raise RuntimeError("fixed generator is still dependent on the hash seed")
    result = {"recorded_UTC": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "actual_generator_processes": len(records) * 2,
              "distinct_baseline_outputs": len(before), "distinct_fixed_outputs": len(after),
              "usage_array_count": len(reference[0]),
              "every_usage_array_key_and_value_preserved": True,
              "every_non_usage_declaration_preserved": True,
              "before_source_SHA256": hashlib.sha256(args.before.read_bytes()).hexdigest(),
              "after_source_SHA256": hashlib.sha256(args.after.read_bytes()).hexdigest(),
              "records": records, "passed": True}
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result))

if __name__ == "__main__":
    main()
