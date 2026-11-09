#!/usr/bin/env python3
"""Verify the disabled modem description against a private stock DTB, on host only."""
import argparse
import ctypes as c
import ctypes.util
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess


class Fdt:
    def __init__(self, path):
        raw = path.read_bytes()
        self.buffer = c.create_string_buffer(raw)
        self.lib = c.CDLL(ctypes.util.find_library('fdt'))
        self.lib.fdt_check_full.argtypes = [c.c_void_p, c.c_size_t]
        assert self.lib.fdt_check_full(self.buffer, len(raw)) == 0
        self.lib.fdt_path_offset.argtypes = [c.c_void_p, c.c_char_p]
        self.lib.fdt_node_offset_by_phandle.argtypes = [c.c_void_p, c.c_uint32]
        self.lib.fdt_get_path.argtypes = [c.c_void_p, c.c_int, c.c_void_p, c.c_int]
        self.lib.fdt_getprop.argtypes = [c.c_void_p, c.c_int, c.c_char_p, c.POINTER(c.c_int)]
        self.lib.fdt_getprop.restype = c.c_void_p

    def offset(self, path):
        offset = self.lib.fdt_path_offset(self.buffer, path.encode())
        assert offset >= 0, path
        return offset

    def prop(self, path, name):
        length = c.c_int()
        pointer = self.lib.fdt_getprop(self.buffer, self.offset(path), name.encode(), c.byref(length))
        return c.string_at(pointer, length.value) if pointer and length.value >= 0 else None

    def cells(self, path, name):
        raw = self.prop(path, name)
        assert raw is not None and len(raw) % 4 == 0, (path, name)
        return list(struct.unpack('>' + str(len(raw) // 4) + 'I', raw))

    def strings(self, path, name):
        raw = self.prop(path, name)
        assert raw is not None, (path, name)
        return raw.rstrip(b'\0').decode().split('\0')

    def resolve(self, handle):
        offset = self.lib.fdt_node_offset_by_phandle(self.buffer, handle)
        assert offset >= 0, handle
        path = c.create_string_buffer(4096)
        assert self.lib.fdt_get_path(self.buffer, offset, path, len(path)) == 0
        return path.value.decode()

    def supply(self, node, name):
        handles = self.cells(node, name)
        assert len(handles) == 1
        return self.resolve(handles[0])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stock_mapping(path):
    tree = Fdt(path)
    assert tree.cells('/', 'qcom,board-id') == [150, 0]
    node = '/soc/qcom,mss@fc880000'
    assert tree.strings(node, 'compatible') == ['qcom,pil-q6v5-mss']
    result = {}
    for role, supply, expected, minimum, maximum in [
        ('mx', 'vdd_mx-supply', '8226_l3', 750000, 1337500),
        ('pll', 'vdd_pll-supply', '8226_l8', 1800000, 1800000),
        ('mss', 'vdd_mss-supply', '8226_s5', 1150000, 1150000),
    ]:
        provider = tree.supply(node, supply)
        assert tree.strings(provider, 'regulator-name') == [expected]
        assert tree.cells(provider, 'regulator-min-microvolt') == [minimum]
        assert tree.cells(provider, 'regulator-max-microvolt') == [maximum]
        result[role] = {'stock_regulator': expected, 'minimum_uV': minimum, 'maximum_uV': maximum}
    # Only selected wiring/constraints escape this function; no complete stock dump.
    return result


def candidate_mapping(path, stock):
    tree = Fdt(path)
    node = '/soc/remoteproc@fc880000'
    assert tree.strings(node, 'compatible') == ['qcom,msm8926-mss-pil']
    assert tree.strings(node, 'status') == ['disabled']
    assert tree.prop(node, 'qcom,ext-bhs-reg') is None
    result = {}
    for role, name in [('mx', 'l3'), ('pll', 'l8'), ('mss', 's5')]:
        provider = tree.supply(node, role + '-supply')
        assert provider.rsplit('/', 1)[1] == name, (role, provider)
        for prop, key in [('regulator-min-microvolt', 'minimum_uV'), ('regulator-max-microvolt', 'maximum_uV')]:
            assert tree.cells(provider, prop) == [stock[role][key]], (role, prop)
        if role == 'mss':
            assert tree.strings(provider, 'status') == ['disabled']
        result[role] = provider
    memory = [tree.resolve(value) for value in tree.cells(node, 'memory-region')]
    assert [tree.cells(path, 'reg') for path in memory] == [[0x0d100000, 0x100000], [0x08000000, 0x05100000]]
    assert all(tree.prop(path, 'no-map') == b'' for path in memory)
    return {'supply_paths': result, 'memory_paths': memory, 'modem_status': 'disabled', 'S5_status': 'disabled'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--stock-dtb', required=True, type=Path)
    parser.add_argument('--patch', required=True, type=Path)
    parser.add_argument('--schema-tools', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    output.mkdir(mode=0o700, exist_ok=False)
    env = os.environ | {'PYTHONDONTWRITEBYTECODE': '1', 'XDG_CACHE_HOME': str(output / 'cache')}
    stock = stock_mapping(args.stock_dtb)
    board = 'arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai.dts'
    scratch = output / 'source'
    (scratch / board).parent.mkdir(parents=True)
    shutil.copy2(source / board, scratch / board)
    subprocess.run(['patch', '--batch', '--fuzz=0', '--dry-run', '-p1', '-i', str(args.patch.resolve())], cwd=scratch, env=env, check=True, capture_output=True)
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(args.patch.resolve())], cwd=scratch, env=env, check=True, capture_output=True)
    dtbs = {}
    for name, path in [('baseline', source / board), ('candidate', scratch / board)]:
        preprocessed, dtb = output / (name + '.dts'), output / (name + '.dtb')
        with preprocessed.open('wb') as out:
            subprocess.run(['cpp', '-nostdinc', '-undef', '-D__DTS__', '-x', 'assembler-with-cpp',
                            '-I' + str(source / 'include'), '-I' + str(source / 'arch/arm/boot/dts'),
                            '-I' + str(source / 'arch/arm/boot/dts/qcom'), str(path)], env=env, check=True, stdout=out)
        with (output / (name + '-dtc.log')).open('w') as log:
            subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb', '-o', str(dtb), str(preprocessed)], env=env, check=True, stderr=log)
        dtbs[name] = dtb
    candidate = candidate_mapping(dtbs['candidate'], stock)
    def warnings(name):
        return [row.split(': Warning ', 1)[1] for row in
                (output / (name + '-dtc.log')).read_text().splitlines() if ': Warning ' in row]
    assert warnings('baseline') == warnings('candidate')
    # The wrong variant and a same-type but wrong rail must fail the stock-derived check.
    controls = []
    for mode in ['baseline-wrong-description', 'wrong-MSS-supply', 'S5-unexpectedly-enabled']:
        path = output / (mode + '.dtb')
        shutil.copy2(dtbs['baseline' if mode == 'baseline-wrong-description' else 'candidate'], path)
        if mode == 'wrong-MSS-supply':
            tree = Fdt(path)
            wrong = tree.cells(candidate['supply_paths']['pll'], 'phandle')[0]
            subprocess.run(['fdtput', '-t', 'x', str(path), '/soc/remoteproc@fc880000', 'mss-supply', hex(wrong)], check=True, env=env)
        if mode == 'S5-unexpectedly-enabled':
            subprocess.run(['fdtput', '-t', 's', str(path), candidate['supply_paths']['mss'], 'status', 'okay'], check=True, env=env)
        try:
            candidate_mapping(path, stock)
        except AssertionError:
            controls.append({'mode': mode, 'rejected': True})
        else:
            raise AssertionError('Control accepted: ' + mode)
    schema = output / 'processed-schema.json'
    with (output / 'schema-generation.log').open('w') as log:
        subprocess.run([str(args.schema_tools / 'dt-mk-schema'), '-j', '-o', str(schema),
                        str(source / 'Documentation/devicetree/bindings')], env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
    # Disabled nodes relax required-property checks. Validate separate enabled
    # copies, including the new S5, to prove that the descriptions are complete.
    schema_logs = {}
    validation_dtbs = {}
    for name, path in dtbs.items():
        enabled = output / (name + '-schema-enabled.dtb')
        shutil.copy2(path, enabled)
        subprocess.run(['fdtput', '-t', 's', str(enabled), '/soc/remoteproc@fc880000',
                        'status', 'okay'], check=True, env=env)
        if name == 'candidate':
            subprocess.run(['fdtput', '-t', 's', str(enabled), candidate['supply_paths']['mss'],
                            'status', 'okay'], check=True, env=env)
        validation_dtbs[name] = enabled
        result = subprocess.run([str(args.schema_tools / 'dt-validate'), '-s', str(schema),
                                 '-l', 'qcom,msm8916-mss-pil:qcom,smd-rpm-regulator', str(enabled)],
                                env=env, capture_output=True, text=True, check=True)
        schema_logs[name] = result.stdout + result.stderr
        (output / (name + '-schema.log')).write_text(schema_logs[name])
    assert schema_logs['candidate'] == '', schema_logs['candidate']
    assert 'mx-supply' in schema_logs['baseline'] and 'pll-supply' in schema_logs['baseline']
    stale_bhs = output / 'candidate-with-stale-BHS.dtb'
    shutil.copy2(validation_dtbs['candidate'], stale_bhs)
    old = Fdt(dtbs['baseline']).cells('/soc/remoteproc@fc880000', 'qcom,ext-bhs-reg')
    subprocess.run(['fdtput', '-t', 'x', str(stale_bhs), '/soc/remoteproc@fc880000',
                    'qcom,ext-bhs-reg', *[hex(value) for value in old]], check=True, env=env)
    invalid = subprocess.run([str(args.schema_tools / 'dt-validate'), '-s', str(schema),
                              '-l', 'qcom,msm8916-mss-pil', str(stale_bhs)],
                             env=env, capture_output=True, text=True, check=True)
    diagnostic = invalid.stdout + invalid.stderr
    (output / 'stale-BHS-schema-control.log').write_text(diagnostic)
    assert diagnostic and 'False schema' in diagnostic
    candidate_mapping(dtbs['candidate'], stock)  # Enabled validation copies never replace it.
    result = {'verified_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'stock_selected_supply_mapping': stock, 'candidate': candidate, 'controls': controls,
              'patch_applies_without_fuzz': True, 'baseline_and_candidate_DTC': 'pass',
              'candidate_MSS_and_RPM_regulator_schema_diagnostics': 0,
              'schema_validates_separate_enabled_host_copies': True,
              'baseline_missing_supplies_detected_by_actual_schema': True,
              'stale_MSM8226_BHS_property_detected_by_actual_schema': True,
              'new_DTC_warnings': 0, 'inherited_DTC_warnings': len(warnings('baseline')),
              'patch_sha256': sha(args.patch), 'baseline_board_sha256': sha(source / board),
              'candidate_board_sha256': sha(scratch / board),
              'baseline_DTB_sha256': sha(dtbs['baseline']), 'candidate_DTB_sha256': sha(dtbs['candidate']),
              'no_device_access': True, 'candidate_booted_or_packaged': False,
              'scope': 'Stock-derived wiring and disabled DT description only; no voltage, modem startup, radio or GNSS qualification'}
    (output / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
