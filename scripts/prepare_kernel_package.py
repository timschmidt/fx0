#!/usr/bin/env python3
"""Export a checked kernel manifest as a standalone pmaports package directory.

Local files only; does not build, publish, install or access a device. The
caller supplies the pinned source archive's independently recorded SHA-512.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from prepare_kernel_integration import ROOT, digest, relative_path


def export(manifest_path, profile, config, template, archive, archive_sha512,
           output, pkgrel, root=ROOT):
    root, output = Path(root).resolve(), Path(output)
    if output.exists():
        raise ValueError('Output already exists')
    if pkgrel < 0:
        raise ValueError('Package revision must be nonnegative')
    if not re.fullmatch(r'[0-9a-f]{128}', archive_sha512):
        raise ValueError('Expected archive SHA-512 must be 128 lowercase hex digits')
    with Path(archive).open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha512').hexdigest()
    if actual != archive_sha512:
        raise ValueError('Source archive checksum mismatch')
    manifest = json.loads(Path(manifest_path).read_text())
    if manifest.get('schema') != 1:
        raise ValueError('Unsupported manifest schema')
    if manifest['base'].get('repository') != 'https://github.com/timschmidt/fx0-linux.git':
        raise ValueError('Unsupported source repository')
    commit = manifest['base']['commit']
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Invalid pinned base commit')
    patches = manifest['profiles'][profile]['patches']
    names, contents = [], {}
    for name in patches:
        path = root / relative_path(name)
        if digest(path) != manifest['sha256'][name]:
            raise ValueError('Patch checksum mismatch: ' + name)
        target = path.stem + '.patch'
        if target in contents:
            raise ValueError('Duplicate package patch name: ' + target)
        names.append(target)
        contents[target] = path.read_bytes()
    if not names:
        raise ValueError('Empty patch series')
    recipe = Path(template).read_text()
    # Restrict this exporter to the established shared SoC recipe structure.
    required = ['pkgname=linux-$_flavor', 'pkgver=6.18.59',
                'builddir="$srcdir/fx0-linux-$_commit"',
                'pmb:cross-native', 'pmb:kconfigcheck-community']
    if any(text not in recipe for text in required):
        raise ValueError('Unexpected package template')
    substitutions = [(r'^pkgrel=\d+$', 'pkgrel=' + str(pkgrel)),
                     (r'^_commit="[0-9a-f]{40}"$', '_commit="' + commit + '"')]
    for pattern, value in substitutions:
        recipe, count = re.subn(pattern, lambda match: value, recipe, flags=re.M)
        if count != 1:
            raise ValueError('Ambiguous package template field: ' + pattern)
    source = ('source="\n\tlinux-fx0-$_commit.tar.gz::'
              'https://github.com/timschmidt/fx0-linux/archive/$_commit.tar.gz\n'
              '\t$_config\n' + ''.join('\t' + n + '\n' for n in names) + '"')
    recipe, count = re.subn(r'^source="[^\"]*"', lambda match: source,
                            recipe, flags=re.M)
    if count != 1:
        raise ValueError('Ambiguous package source block')
    if recipe.count('LLVM=1') != 2 or 'LOCALVERSION=' in recipe:
        raise ValueError('Unexpected build/install make commands')
    recipe = recipe.replace('LLVM=1', 'LLVM=1 LOCALVERSION=""')
    config_copy = '\tcp "$srcdir/config-$_flavor.$arch" .config'
    if recipe.count(config_copy) != 1:
        raise ValueError('Unexpected prepare configuration copy')
    recipe = recipe.replace(config_copy, config_copy +
                            '\n\tmake ARCH="$_carch" LLVM=1 LOCALVERSION="" olddefconfig')
    config_name = 'config-postmarketos-qcom-msm8226.armv7'
    contents[config_name] = Path(config).read_bytes()
    checksums = [(archive_sha512, 'linux-fx0-' + commit + '.tar.gz')]
    checksums += [(hashlib.sha512(contents[n]).hexdigest(), n)
                  for n in [config_name, *names]]
    block = 'sha512sums="\n' + ''.join(h + '  ' + n + '\n' for h, n in checksums) + '"'
    recipe, count = re.subn(r'^sha512sums="[^\"]*"', lambda match: block,
                            recipe, flags=re.M)
    if count != 1:
        raise ValueError('Ambiguous package checksum block')
    contents['APKBUILD'] = recipe.encode()
    report = {'manifest_sha256': digest(Path(manifest_path)),
              'profile': profile, 'base_commit': commit,
              'configuration_sha256': digest(Path(config)),
              'template_sha256': digest(Path(template)),
              'source_archive_sha512': archive_sha512,
              'pkgrel': pkgrel, 'patch_order': names,
              'exported_sha256': {n: hashlib.sha256(b).hexdigest()
                                  for n, b in contents.items()},
              'status': 'exported only; source build and hardware acceptance separate'}
    output.mkdir(parents=True, mode=0o700)
    for name, data in contents.items():
        (output/name).write_bytes(data)
    (output/'source-provenance.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--profile', choices=['r50', 'cpr', 'nfc'], required=True)
    for name in ['config', 'template', 'archive', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--archive-sha512', required=True)
    parser.add_argument('--pkgrel', type=int, required=True)
    a = parser.parse_args()
    report = export(a.manifest, a.profile, a.config, a.template, a.archive,
                    a.archive_sha512, a.output, a.pkgrel)
    print(f"Exported {len(report['patch_order'])} ordered patches at r{a.pkgrel}")


if __name__ == '__main__':
    main()
