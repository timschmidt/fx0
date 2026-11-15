# SPDX-License-Identifier: GPL-2.0-only
"""Check actual compiled CAMSS example and resource-name/schema agreement."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import re
import dtschema
import yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', required=True, type=Path)
parser.add_argument('--build', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
assert not args.output.exists()
binding = args.source / 'Documentation/devicetree/bindings/media/qcom,msm8226-camss.yaml'
schema = args.build / 'Documentation/devicetree/bindings/processed-schema.json'
example = args.build / 'Documentation/devicetree/bindings/media/qcom,msm8226-camss.example.dtb'
validator = dtschema.DTValidator([str(schema)])
tree = validator.decode_dtb(example.read_bytes())[0]
node = tree['example-0']['camss@fda0ac00']

def errors(value):
    value = copy.deepcopy(value)
    value['$nodename'] = ['camss@fda0ac00']
    return list(validator.iter_errors(value, filter=['media/qcom,msm8226-camss.yaml']))

assert not errors(node)
controls = []
for prop in ['clocks', 'clock-names', 'interrupts', 'interrupt-names', 'reg', 'reg-names']:
    broken = copy.deepcopy(node)
    broken[prop] = broken[prop][:-1]
    assert errors(broken), ('truncated property accepted', prop)
    controls.append('truncated ' + prop)
for prop in ['iommus', 'vdda-supply', 'power-domains']:
    broken = copy.deepcopy(node)
    del broken[prop]
    assert errors(broken), ('required property omission accepted', prop)
    controls.append('missing ' + prop)
broken = copy.deepcopy(node)
broken['clock-names'][0] = 'unrelated_ahb'
assert errors(broken)
controls.append('incorrect clock name')

document = yaml.safe_load(binding.read_text())
source = (args.source / 'drivers/media/platform/qcom/camss/camss.c').read_text()
start = source.index('/* MSM8226:')
end = source.index('static const struct camss_subdev_resources csiphy_res_8x39', start)
resources = source[start:end]
observed = {}
for field, prop in [('clock', 'clock-names'), ('reg', 'reg-names'), ('interrupt', 'interrupt-names')]:
    names = set()
    for match in re.finditer(r'\.' + field + r'\s*=\s*\{([^}]+)\}', resources):
        names.update(re.findall(r'"([^"\n]+)"', match[1]))
    expected = {item['const'] for item in document['properties'][prop]['items']}
    assert names == expected, (field, sorted(names), sorted(expected))
    observed[prop] = sorted(names)
assert len(observed['clock-names']) == 18 and len(observed['reg-names']) == 9
assert len(observed['interrupt-names']) == 6
assert resources.count('.supply = "vdda"') == 2
assert resources.count('{ 266670000 }') == 1
record = dict(passed=True, example_SHA256=hashlib.sha256(example.read_bytes()).hexdigest(),
              binding_SHA256=hashlib.sha256(binding.read_bytes()).hexdigest(),
              source_SHA256=hashlib.sha256(source.encode()).hexdigest(),
              ordinary_example_schema_passed=True, negative_controls=controls,
              resource_names_agree_with_binding=observed,
              scope='Compiled example and declarative resource contract only; no board or hardware acceptance',
              phone_access=False)
args.output.write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record))
