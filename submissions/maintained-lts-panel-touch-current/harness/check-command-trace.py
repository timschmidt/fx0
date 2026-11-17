#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Execute extracted panel/DRM helpers against a recording DSI transport.

Compare payload families, bytes and waits with the vendor production tables.
Packet types, host timing, GPIOs and physical display effects are not modeled.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function(source, name):
    match = re.search(r'^(?:static\s+)?(?:inline\s+)?(?:int|void)\s+' + re.escape(name) + r'\([^;{}]*\)\n\{', source, re.M)
    assert match, name
    brace = source.index('{', match.start())
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end]


def macro(source, name):
    lines = source.splitlines()
    start = next(i for i, line in enumerate(lines)
                 if line.startswith('#define ' + name + '('))
    end = start
    while lines[end].endswith('\\'):
        end += 1
    return '\n'.join(lines[start:end + 1])


def vendor(source, prop):
    source = re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.S)
    match = re.search(re.escape(prop) + r'\s*=\s*\[([^]]*)\]', source)
    assert match, prop
    data = bytes.fromhex(match[1])
    events, offset = [], 0
    while offset < len(data):
        header = data[offset:offset + 7]
        assert len(header) == 7 and header[0] in [0x39, 0x29, 0x15, 0x05]
        size = int.from_bytes(header[5:7], 'big')
        payload = data[offset + 7:offset + 7 + size]
        assert len(payload) == size
        family = 'G' if header[0] == 0x29 else 'D'
        events.append(family + ' ' + payload.hex())
        if header[4]:
            events.append('W ' + str(header[4]))
        offset += 7 + size
    assert offset == len(data)
    return events


STUBS = r'''
// SPDX-License-Identifier: GPL-2.0-only
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
typedef unsigned char u8;
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define MIPI_DSI_MODE_LPM 1
#define dev_err(dev,...) ((void)(dev))
struct device {int unused;};
struct drm_panel {int unused;};
struct mipi_dsi_device {struct device dev;unsigned long mode_flags;};
struct mipi_dsi_multi_context {struct mipi_dsi_device *dsi;int accum_err;};
struct lg_fx0 {struct drm_panel panel;struct mipi_dsi_device *dsi;};
static unsigned attempted, fail_at;
static ssize_t transfer(struct mipi_dsi_device *dsi,char family,const void *data,size_t len)
{
 assert(!!(dsi->mode_flags & MIPI_DSI_MODE_LPM)==(family!='X'));
 printf("%c ",family=='X'?'D':family);
 const u8 *p=data;for(size_t i=0;i<len;i++)printf("%02x",p[i]);puts("");
 attempted++;return attempted==fail_at?-EIO:(ssize_t)len;
}
static ssize_t mipi_dsi_generic_write(struct mipi_dsi_device *dsi,const void *p,size_t n)
{return transfer(dsi,'G',p,n);}
static ssize_t mipi_dsi_dcs_write_buffer(struct mipi_dsi_device *dsi,const void *p,size_t n)
{return transfer(dsi,'D',p,n);}
static ssize_t mipi_dsi_dcs_write(struct mipi_dsi_device *dsi,u8 cmd,const void *p,size_t n)
{assert(!n && !p);return transfer(dsi,(dsi->mode_flags & MIPI_DSI_MODE_LPM)?'D':'X',&cmd,1);}
static void msleep(unsigned delay) {printf("W %u\n",delay);}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['kernel', 'driver', 'baseline', 'vendor-common', 'vendor-board', 'output']:
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700)
    header = args.kernel / 'include/drm/drm_mipi_dsi.h'
    core = args.kernel / 'drivers/gpu/drm/drm_mipi_dsi.c'
    constants = args.kernel / 'include/video/mipi_display.h'
    h, c = header.read_text(), core.read_text()
    helpers = ['enter_sleep_mode', 'exit_sleep_mode', 'set_display_off', 'set_display_on']
    defines = []
    for name in helpers:
        enum = 'MIPI_DCS_' + name.upper()
        match = re.search(r'\b' + enum + r'\s*=\s*(0x[0-9A-Fa-f]+)', constants.read_text())
        assert match, enum
        defines.append('#define ' + enum + ' ' + match[1])
    prefix = STUBS + '\n' + '\n'.join(defines) + '\n'
    prefix += '\n'.join(macro(h, n) for n in ['mipi_dsi_generic_write_seq_multi', 'mipi_dsi_dcs_write_seq_multi', 'mipi_dsi_msleep']) + '\n'
    prefix += '\n'.join(function(c, 'mipi_dsi_dcs_' + n) for n in helpers) + '\n'
    prefix += '\n'.join(function(c, n) for n in ['mipi_dsi_generic_write_multi', 'mipi_dsi_dcs_write_buffer_multi']) + '\n'
    prefix += '\n'.join(function(c, 'mipi_dsi_dcs_' + n + '_multi') for n in helpers) + '\n'
    prefix += 'static struct lg_fx0 *to_lg_fx0(struct drm_panel *p) {return container_of(p,struct lg_fx0,panel);}\n'
    common, board = args.vendor_common.read_text(), args.vendor_board.read_text()
    # Match the production in-cell override, not the preceding prototype panel.
    board = board[board.index('&dsi_jdi_incell_vid_dsv{'):]
    expected_on = vendor(common, 'qcom,mdss-dsi-on-command-with-tpcm') + vendor(board, 'lge,display-on-cmds')
    expected_off = vendor(board, 'lge,sleep-in-cmds')
    expected = expected_on + expected_off
    panel = args.driver.read_text()
    on, off = function(panel, 'lg_fx0_on'), function(panel, 'lg_fx0_disable')
    baseline = args.baseline.read_text()
    assert re.sub(r'\s', '', on) == re.sub(r'\s', '', function(baseline, 'lg_fx0_on'))
    assert re.sub(r'\s', '', off) == re.sub(r'\s', '', function(baseline, 'lg_fx0_disable'))
    variants = {'baseline': baseline, 'candidate': panel,
                'mutant-command': panel.replace('0x51, 0xff', '0x51, 0xfe', 1),
                'mutant-wait': panel.replace('mipi_dsi_msleep(&ctx, 120)', 'mipi_dsi_msleep(&ctx, 119)', 1),
                'mutant-order': panel.replace('mipi_dsi_dcs_set_display_on_multi(&ctx);\n\tmipi_dsi_dcs_exit_sleep_mode_multi(&ctx);', 'mipi_dsi_dcs_exit_sleep_mode_multi(&ctx);\n\tmipi_dsi_dcs_set_display_on_multi(&ctx);', 1)}
    rows = []
    env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:abort_on_error=1', 'UBSAN_OPTIONS': 'halt_on_error=1'}
    for name, source in variants.items():
        fixture = args.output / (name + '.c')
        binary = args.output / name
        body = prefix + function(source, 'lg_fx0_on') + '\n' + function(source, 'lg_fx0_disable')
        body += r'''
int main(int argc,char **argv) {
 assert(argc==3);bool off=atoi(argv[1]);fail_at=atoi(argv[2]);
 struct mipi_dsi_device dsi={.mode_flags=off?MIPI_DSI_MODE_LPM:0};
 struct lg_fx0 p={.dsi=&dsi};
 int ret=off?lg_fx0_disable(&p.panel):lg_fx0_on(&p);
 assert(!!(dsi.mode_flags & MIPI_DSI_MODE_LPM)==!off);
 printf("R %d\n",ret);return 0;
}
'''
        fixture.write_text(body + '\n')
        build = subprocess.run(['clang-21', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined', '-g', str(fixture), '-o', str(binary)], capture_output=True)
        (args.output / (name + '-compile.stderr')).write_bytes(build.stderr)
        assert build.returncode == 0 and not build.stderr
        cases, differences = 0, 0
        for phase, events in enumerate([expected_on, expected_off]):
            total = sum(not e.startswith('W ') for e in events)
            for fail in range(total + 1):
                result = subprocess.run([str(binary), str(phase), str(fail)], capture_output=True, env=env, timeout=20)
                assert result.returncode == 0 and not result.stderr
                got = result.stdout.decode().splitlines()
                end, attempted = len(events), 0
                if fail:
                    for i, event in enumerate(events):
                        if not event.startswith('W '):
                            attempted += 1
                            if attempted == fail:
                                end = i + 1
                                break
                wanted = events[:end] + ['R ' + str(-5 if fail else 0)]
                differences += got != wanted
                cases += 1
                (args.output / f'{name}-{phase}-{fail}.trace').write_bytes(result.stdout)
        assert differences == 0 if name in ['baseline', 'candidate'] else differences > 0, (name, differences)
        rows.append(dict(name=name, cases=cases, vendor_trace_differences=differences,
                         intended_result_verified=True, fixture_SHA256=sha(fixture)))
    record = dict(passed=True, rows=rows, expected_trace=expected,
                  input_SHA256={str(p): sha(p) for p in [args.driver, args.baseline, header, core, constants, args.vendor_common, args.vendor_board]},
                  packet_types_or_host_timing_qualified=False, physical_display_qualified=False,
                  actual_panel_functions_and_multi_helpers_executed=True, DSI_transport_and_sleep_mocked=True)
    (args.output / 'qualification.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(passed=True, rows=rows)))


if __name__ == '__main__':
    main()
