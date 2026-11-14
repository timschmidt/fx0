#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the actual pidfd client owner against real disposable Linux children."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

source = Path(__file__).with_name('pause-queue-test.py')
spec = importlib.util.spec_from_file_location('pause_camera', source)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
CODE = '''
import pathlib,signal,sys,time
p=pathlib.Path(sys.argv[1])
if sys.argv[2]=='ignore': signal.signal(signal.SIGINT,signal.SIG_IGN)
n=0
while True:
 q=p.with_suffix('.new');q.write_text(str(n));q.replace(p);n+=1;time.sleep(.005)
'''


def until(predicate):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.002)
    raise AssertionError('child fixture deadline')


def count(path):
    try:
        text = path.read_text()
        return int(text) if text else -1
    except FileNotFoundError:
        return -1


def spawn(path, *, session=True, ignore=False):
    child = subprocess.Popen([sys.executable, '-c', CODE, str(path), 'ignore' if ignore else 'normal'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=session)
    until(lambda: count(path) >= 2)
    return child


def reap(child):
    if child.poll() is None:
        child.kill()
    child.wait(timeout=2)


cases = []
with tempfile.TemporaryDirectory(prefix='fx0-owned-camera-') as tmp:
    root = Path(tmp)
    owned = spawn(root / 'owned')
    unrelated = spawn(root / 'unrelated')
    try:
        with worker.OwnedClient(owned) as owner:
            owner.pause()
            stopped = count(root / 'owned')
            other = count(root / 'unrelated')
            time.sleep(.05)
            assert count(root / 'owned') == stopped
            until(lambda: count(root / 'unrelated') > other)
            owner.resume()
            until(lambda: count(root / 'owned') > stopped)
        assert owned.returncode is not None and owner.closed
        cases.append('owned stop/resume/reap; unrelated session keeps running')
    finally:
        reap(owned)
        reap(unrelated)

    child = spawn(root / 'interrupted')
    try:
        try:
            with worker.OwnedClient(child) as owner:
                owner.pause()
                raise RuntimeError('injected paused-body failure')
        except RuntimeError as error:
            assert str(error) == 'injected paused-body failure'
        assert child.returncode is not None and owner.closed
        cases.append('exception while stopped resumes then terminates/reaps')
    finally:
        reap(child)

    child = spawn(root / 'ignore', ignore=True)
    try:
        with worker.OwnedClient(child, stop_timeout=.1) as owner:
            owner.pause()
        assert child.returncode == -signal.SIGKILL and owner.closed
        cases.append('SIGINT-ignoring stopped child reaches bounded group kill/reap')
    finally:
        reap(child)

    child = spawn(root / 'foreign-group', session=False)
    try:
        try:
            worker.OwnedClient(child)
        except ValueError:
            pass
        else:
            raise AssertionError('shared-session child accepted')
        before = count(root / 'foreign-group')
        until(lambda: count(root / 'foreign-group') > before)
        cases.append('shared caller session rejected before signals')
    finally:
        reap(child)

    child = subprocess.Popen([sys.executable, '-c', 'pass'], start_new_session=True)
    child.wait(timeout=2)
    try:
        worker.OwnedClient(child)
    except ValueError:
        cases.append('already reaped child rejected')
    else:
        raise AssertionError('dead child accepted')

    child = spawn(root / 'identity')
    try:
        with worker.OwnedClient(child) as owner:
            identity = owner.identity
            owner.identity = (*identity[:3], identity[3] + 1)
            try:
                owner.pause()
            except ValueError:
                pass
            else:
                raise AssertionError('wrong process start identity accepted')
            finally:
                owner.identity = identity
            assert not owner.paused
        cases.append('wrong start identity rejected before stop')
    finally:
        reap(child)

    child = spawn(root / 'resume-failure')
    try:
        owner = worker.OwnedClient(child, stop_timeout=.1)
        owner.pause()
        def failed_resume():
            raise RuntimeError('injected resume failure')
        owner.resume = failed_resume
        try:
            owner.close()
        except RuntimeError as error:
            assert str(error) == 'injected resume failure'
        assert child.returncode == -signal.SIGKILL and owner.closed
        cases.append('resume exception still uses pinned continue/kill/reap fallback')
    finally:
        reap(child)

    child = spawn(root / 'incomplete-stop')
    try:
        try:
            with worker.OwnedClient(child) as owner:
                real_states = owner._task_states
                owner._task_states = lambda: real_states() | {-1: 'R'}
                owner.pause()
        except RuntimeError as error:
            assert str(error) == 'owned child did not acknowledge stop'
        else:
            raise AssertionError('incomplete thread-stop observation accepted')
        assert child.returncode is not None and owner.closed
        cases.append('one running thread prevents acknowledgement and still cleans up')
    finally:
        reap(child)

    ready = root / 'threads-ready'
    code = '''
import pathlib,threading,time,sys
def work():
 while True: time.sleep(.002)
for i in range(7): threading.Thread(target=work,daemon=True).start()
p=pathlib.Path(sys.argv[1]);q=p.with_suffix('.new');q.write_text('ready');q.replace(p)
while True: time.sleep(.002)
'''
    child = subprocess.Popen([sys.executable, '-c', code, str(ready)], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        until(ready.exists)
        with worker.OwnedClient(child) as owner:
            owner.pause()
            observed = owner.pause_observation
            assert observed['kernel_group_stop_confirmed'] and observed['wait_status'] == signal.SIGSTOP
            assert len(observed['thread_states']) == 8 and set(observed['thread_states'].values()) <= {'T', 't'}
            owner.resume()
            assert owner.resume_observation['all_live_threads_resumed']
            assert len(owner.resume_observation['thread_states']) == 8
        assert child.returncode is not None and owner.closed
        cases.append('eight real threads and kernel group-stop notification checked before timing')
    finally:
        reap(child)

    child = spawn(root / 'exit-while-stopped')
    try:
        owner = worker.OwnedClient(child)
        owner.pause()
        child.kill()
        child.wait(timeout=2)
        owner.resume()
        assert owner.resume_observation['child_exited'] and not owner.resume_observation['all_live_threads_resumed']
        owner.close()
        assert owner.closed
        cases.append('client killed while stopped is recorded as exited, never resumed')
    finally:
        reap(child)

    grandchild_pid = root / 'grandchild-pid'
    code = '''
import pathlib,signal,subprocess,sys,time
p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
def stop(sig,frame):
 p.wait(timeout=1);sys.exit(0)
signal.signal(signal.SIGINT,stop)
ready=pathlib.Path(sys.argv[1]);tmp=ready.with_suffix('.new');tmp.write_text(str(p.pid));tmp.replace(ready)
while True: time.sleep(.01)
'''
    child = subprocess.Popen([sys.executable, '-c', code, str(grandchild_pid)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        until(grandchild_pid.exists)
        pid = int(grandchild_pid.read_text())
        with worker.OwnedClient(child):
            pass
        assert child.returncode == 0
        assert not Path('/proc', str(pid)).exists()
        cases.append('owned group interrupt lets parent reap its grandchild')
    finally:
        reap(child)

print(json.dumps({'owned_client_cases': len(cases), 'cases': cases,
                  'all_fixture_primary_children_reaped': True, 'camera_hardware_access': False}, indent=2))
