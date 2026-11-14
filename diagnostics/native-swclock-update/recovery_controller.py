"""Call the exact native-qualified file recovery after the installer is terminal.
The external launcher establishes current-boot PID1 completion and empty cgroup.
No package uninstall or clock execution is used.
"""
from pathlib import Path
import fcntl,json,os,signal,sys
import clock_transaction as clock
from snapshot_core import sha

def recover(plan,work):
    work=Path(work).resolve(strict=True)
    assert os.getpid()==1 and work==clock.LIVE_WORK
    assert sha(work/'clock_transaction.py')==plan['controller_sha256']=='05269c291f744bf6d9203314b8683caa061e4a5bc57f0b74cbcbf9b1b918425c'
    assert sha(Path(__file__))==plan['recovery_controller_sha256']
    assert plan['unit']=='fx0-swclock-live-recover-01.service'
    assert plan['status_name']=='manager-recovery-status.json'
    assert work.stat().st_uid==0 and work.stat().st_mode&0o777==0o700
    assert Path('/usr/lib/apk/db/lock').stat().st_ino==8282
    descriptor=os.open(work/'transaction.lock',os.O_RDWR|os.O_CLOEXEC|os.O_NOFOLLOW)
    previous={}
    try:
        fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        ops=clock.ClockUpdate(plan,work)
        assert ops.hooks_terminal()
        # Completion of this already-started recovery remains mandatory on TERM.
        for number in [signal.SIGTERM,signal.SIGINT]:previous[number]=signal.signal(number,lambda n,f:setattr(ops,'stopping',True))
        ops.rollback()
        ops.verify_rollback()
        assert ops.hooks_terminal() and ops.state['stage']=='rollback-verified'
    finally:
        for number,handler in previous.items():signal.signal(number,handler)
        os.close(descriptor)
if __name__=='__main__':
    assert len(sys.argv)==3
    recover(json.loads(Path(sys.argv[1]).read_text()),Path(sys.argv[2]))
