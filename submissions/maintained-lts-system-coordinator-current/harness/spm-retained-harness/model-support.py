# SPDX-License-Identifier: GPL-2.0-only
import hashlib
import json
import os
import re
import subprocess

def block(text, pattern):
    match = re.search(pattern, text, re.M)
    assert match, pattern
    end = text.index('{', match.start()) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    if text[end:end+1] == ';':
        end += 1
    return text[match.start():end] + '\n'

def function(text, name):
    return block(text, r'^(?:static\s+(?:inline\s+)?)?(?:__cpuidle\s+)?(?:struct\s+\w+|int|void|u32)[ \t*]*\n?' + re.escape(name) + r'\([^;{}]*\)\n\{')


def run_code(code, output):
    assert not output.exists()
    output.mkdir()
    (output / 'compiler-temporary').mkdir()
    (output / 'model.c').write_text(code)
    env = os.environ | {'TMPDIR':str(output.resolve() / 'compiler-temporary'),
        'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1', 'UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
    env.pop('LSAN_OPTIONS', None)
    r = subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror',
        '-Wno-unused-parameter','-Wno-unused-function','-Wno-sign-compare','-fsanitize=address,undefined',
        '-fno-sanitize-recover=all','-fno-omit-frame-pointer',str(output / 'model.c'),'-o',str(output / 'model')],
        env=env,capture_output=True,text=True,timeout=60)
    (output / 'build.log').write_text(r.stdout+r.stderr)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([str(output / 'model')],env=env,capture_output=True,text=True,timeout=120)
    (output / 'run.stdout').write_text(r.stdout)
    (output / 'run.stderr').write_text(r.stderr)
    assert r.returncode == 0, r.stderr
    assert not any(s in r.stderr for s in ['AddressSanitizer','LeakSanitizer','runtime error:'])
    return json.loads(r.stdout)
