# SPDX-License-Identifier: GPL-2.0-only
"""Require the QMI service-fault model to reject five independent regressions."""
from pathlib import Path
import argparse
import importlib.util
import json

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('qmi_fixture', B / 'check-qmi.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
assert not a.output.exists()
a.output.mkdir()
path = 'drivers/slimbus/qcom-ngd-ctrl.c'
text = (a.source / path).read_text()
body = fixture.function(text, 'qcom_slim_qmi_send_power_request')
guard = '\tif (rc < 0)\n\t\treturn rc;'
# The send helper also checks wait/send errors; mutate only the init guard.
assert body.count(guard) == 1
controls = [
    ('missing-init-guard', '', 'invalid_sends == 0'),
    ('reject-positive-transaction-ID', '\tif (rc != 0)\n\t\treturn rc;', 'ret == expected'),
    ('reject-ID-zero', '\tif (rc <= 0)\n\t\treturn rc;', 'send_calls == (unsigned)(alloc_result >= 0)'),
    ('cancel-unallocated-transaction', '\tif (rc < 0) {\n\t\tqmi_txn_cancel(&txn);\n\t\treturn rc;\n\t}', 'remove_calls == (unsigned)(alloc_result >= 0)'),
    ('replace-allocation-errno', '\tif (rc < 0)\n\t\treturn -ENOMEM;', 'ret == expected'),
]
results = []
for name, replacement, assertion in controls:
    root = a.output / name
    source = root / 'source'
    for relative in [path, 'drivers/soc/qcom/qmi_interface.c', 'include/linux/soc/qcom/qmi.h']:
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        value = text.replace(body, body.replace(guard, replacement)) if relative == path else (a.source / relative).read_text()
        target.write_text(value)
    report = fixture.run(source, root / 'run', baseline=True)
    stderr = (root / 'run/run.stderr').read_text()
    assert assertion in stderr, (name, assertion, stderr)
    results.append(dict(name=name, rejected=True, failures=report['failures'], named_assertion=assertion))
result = dict(passed=True, controls=results, all_services_synthetic=True,
              normal_LSan_and_failfast_ASan_UBSan=True, no_real_network_or_device_execution=True)
(a.output / 'qualification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
