# SPDX-License-Identifier: GPL-2.0-only
"""Exercise actual CMS verification and kernel sign-file attachment offline."""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import subprocess

inputs = Path('/inputs')
fixtures = Path('/tests/fixtures')
output = Path('/results')
spec = importlib.util.spec_from_file_location('issued_signature_attachment', inputs / 'attach-signature.py')
attachment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(attachment)
catalog = json.loads((inputs / 'module-signatures.json').read_text())
fixture = json.loads((fixtures / 'fixture.json').read_text())
payload_hash = fixture['payload_SHA256']
payload = (fixtures / 'sample.ko').read_bytes()
sha = lambda b: hashlib.sha256(b).hexdigest()
assert sha(payload) == payload_hash
assert sha((fixtures / 'sign-file').read_bytes()) == fixture['kernel_sign_file_SHA256']
assert not any(Path(p).exists() for p in ['/home', '/root', '/run', '/sys', '/dev/bus/usb'])
interfaces = [l.split(':', 1)[0].strip() for l in Path('/proc/net/dev').read_text().splitlines()[2:]]
assert interfaces == ['lo']
records = []

def setup(name):
    root = output / name
    root.mkdir()
    local_inputs = root / 'inputs'
    local_inputs.mkdir()
    (local_inputs / 'module-signatures').mkdir()
    for filename in ['module-verification.pem', 'module-verification.der']:
        shutil.copyfile(inputs / filename, local_inputs / filename)
    data = json.loads(json.dumps(catalog))
    signature = data['payloads'][payload_hash]['signature']
    shutil.copyfile(inputs / signature, local_inputs / signature)
    manifest = local_inputs / 'module-signatures.json'
    manifest.write_text(json.dumps(data))
    module = root / 'sample.ko'
    module.write_bytes(payload)
    return module, manifest, data

def rejected(name, mutate, expected, format_check=False):
    module, manifest, data = setup(name)
    mutate(module, manifest.parent, data)
    manifest.write_text(json.dumps(data))
    if format_check:
        signature = manifest.parent / data['payloads'][payload_hash]['signature']
        result = subprocess.run(['openssl', 'cms', '-cmsout', '-inform', 'DER',
            '-in', str(signature), '-out', '/dev/null'], capture_output=True)
        assert result.returncode == 0, result.stderr
    before = module.read_bytes()
    try:
        attachment.attach(module, manifest, fixtures / 'sign-file')
    except ValueError as error:
        assert expected in str(error), (name, str(error))
    else:
        raise AssertionError(name + ': invalid input accepted')
    assert module.read_bytes() == before, name + ': rejected input changed module'
    records.append(dict(name=name, passed=True, rejected_without_module_write=True,
                        CMS_DER_format_validated=format_check))

module, manifest, data = setup('actual-kernel-attachment')
digest = attachment.attach(module, manifest, fixtures / 'sign-file')
assert digest == data['payloads'][payload_hash]['signed_module_SHA256']
assert module.read_bytes().endswith(attachment.MAGIC)
records.append(dict(name='actual-kernel-attachment', passed=True,
                    actual_kernel_sign_file_s=True, signed_module_SHA256=digest))
before = module.read_bytes()
try:
    attachment.attach(module, manifest, fixtures / 'sign-file')
except ValueError as error:
    assert 'second module signature' in str(error)
else:
    raise AssertionError('Double attachment accepted')
assert module.read_bytes() == before
records.append(dict(name='double-attachment', passed=True, rejected_without_module_write=True))

def corrupt_payload(module, directory, data):
    altered = bytearray(module.read_bytes()); altered[len(altered)//2] ^= 1
    module.write_bytes(altered)

rejected('changed-payload-catalog', corrupt_payload, 'No issued signature')

def corrupt_payload_with_entry(module, directory, data):
    corrupt_payload(module, directory, data)
    data['payloads'][sha(module.read_bytes())] = data['payloads'][payload_hash]

rejected('changed-payload-CMS', corrupt_payload_with_entry, 'CMS signature does not verify')

def corrupt_signature(module, directory, data):
    path = directory / data['payloads'][payload_hash]['signature']
    altered = bytearray(path.read_bytes()); altered[-1] ^= 1; path.write_bytes(altered)

rejected('changed-signature-checksum', corrupt_signature, 'signature checksum mismatch')

def corrupt_signature_with_checksum(module, directory, data):
    corrupt_signature(module, directory, data)
    entry = data['payloads'][payload_hash]
    entry['signature_SHA256'] = sha((directory / entry['signature']).read_bytes())

rejected('valid-format-changed-CMS', corrupt_signature_with_checksum,
         'CMS signature does not verify', format_check=True)

def unknown_entry(module, directory, data):
    del data['payloads'][payload_hash]

rejected('unissued-payload', unknown_entry, 'No issued signature')

def wrong_signed_digest(module, directory, data):
    data['payloads'][payload_hash]['signed_module_SHA256'] = '0' * 64

rejected('wrong-final-digest', wrong_signed_digest, 'Expected signed module checksum mismatch')

def bad_signature_path(module, directory, data):
    data['payloads'][payload_hash]['signature'] = '../outside.p7s'

rejected('invalid-signature-path', bad_signature_path, 'Invalid signature path')

def changed_certificate(module, directory, data):
    path = directory / 'module-verification.pem'
    path.write_bytes(path.read_bytes() + b'\n')

rejected('changed-certificate', changed_certificate, 'Certificate PEM checksum mismatch')

report = dict(passed=True, cases=len(records), records=records,
    actual_kernel_sign_file_source_head=fixture['compiled_kernel_source_head'],
    input_manifest_SHA256=sha((inputs / 'manifest.json').read_bytes()),
    private_key_not_mounted_or_used=True, no_new_signing_operation=True,
    network_interfaces=interfaces, phone_access=False)
(output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(passed=True, cases=len(records), actual_kernel_sign_file=True)))
