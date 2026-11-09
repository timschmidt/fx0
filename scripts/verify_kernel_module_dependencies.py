#!/usr/bin/env python3
"""Check packaged modules.dep against dependencies inside every module.

Run signature/ABI verification separately. Reads local files and modinfo only;
never loads a module or accesses a device. Rejects empty/stale depmod output.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess


def validate_graph(declared, recorded):
    if set(declared) != set(recorded):
        raise ValueError('modules.dep does not describe exactly the packaged modules')
    memo, active = {}, set()

    def closure(name):
        if name in active:
            raise ValueError('Cyclic module dependency: ' + name)
        if name in memo:
            return memo[name]
        active.add(name)
        result = set()
        for child in declared[name]:
            if child not in declared:
                raise ValueError('Missing declared dependency: ' + child)
            result.add(child)
            result.update(closure(child))
        active.remove(name)
        memo[name] = result
        return result

    for name, dependencies in recorded.items():
        wanted = closure(name)
        if len(dependencies) != len(set(dependencies)) or set(dependencies) != wanted:
            raise ValueError('modules.dep differs from signed module dependencies: ' + name)
    return memo


def verify(modules, expected_count):
    modules = Path(modules).resolve()
    files = sorted(p for p in modules.rglob('*') if p.is_file()
                   and (p.name.endswith('.ko') or p.name.endswith('.ko.zst')))
    if expected_count <= 0 or len(files) != expected_count:
        raise ValueError(f'Expected {expected_count} modules, found {len(files)}')
    names, dependencies = {}, {}

    def info(path, field):
        return subprocess.check_output(['modinfo', '-F', field, str(path)], text=True).strip()

    for path in files:
        if not path.resolve().is_relative_to(modules):
            raise ValueError('Module path escapes package directory')
        name = info(path, 'name').replace('-', '_')
        if not name or name in names:
            raise ValueError('Missing or duplicate module name: ' + name)
        relative = path.relative_to(modules).as_posix()
        names[name] = relative
        dependencies[relative] = [n.replace('-', '_') for n in info(path, 'depends').split(',') if n]
    declared = {}
    for path, values in dependencies.items():
        try:
            declared[path] = [names[name] for name in values]
        except KeyError as error:
            raise ValueError('Missing packaged dependency: ' + str(error)) from error
    recorded = {}
    depfile = modules / 'modules.dep'
    for line in depfile.read_text().splitlines():
        if not line.strip():
            continue
        name, separator, rest = line.partition(':')
        if not separator or name in recorded:
            raise ValueError('Malformed or duplicate modules.dep entry')
        values = rest.split()
        for value in [name, *values]:
            path = PurePosixPath(value)
            if path.is_absolute() or '..' in path.parts or str(path) != value:
                raise ValueError('Unsafe dependency path: ' + value)
        recorded[name] = values
    closure = validate_graph(declared, recorded)
    return {'verified_modules': len(files), 'declared_dependency_edges': sum(map(len, declared.values())),
            'transitive_dependency_edges': sum(map(len, closure.values())),
            'all_modules_dep_entries_match_module_metadata': True,
            'modules_dep_sha256': hashlib.sha256(depfile.read_bytes()).hexdigest(),
            'scope': 'Dependency metadata only; signatures, ABI, runtime loading and install hooks separate'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modules', type=Path, required=True)
    parser.add_argument('--expected-count', type=int, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report already exists')
    report = verify(args.modules, args.expected_count)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(f"Verified dependency metadata for {report['verified_modules']} packaged modules")


if __name__ == '__main__':
    main()
