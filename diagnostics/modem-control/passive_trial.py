# SPDX-License-Identifier: MIT
"""Single-use RAM-trial ordering; all device access belongs to supplied callbacks.

``preflight`` must check durable attempt ownership, current operator approval and
the exact device/image/baseline. ``stage`` must report a reaped transfer with a
boolean ``terminal``, integer ``returncode`` and optional boolean ``timeout``.
Observers must be live before the durable BOOT-intent callback begins.

Once that intent barrier is reached, failures permit observation and native
verification only. The independent return timer belongs to the RAM image;
this module supplies neither a timer nor device recovery commands. Callback
failures propagate, so an attempted verification never implies acceptance.
"""


class Trial:
    def __init__(self, operations):
        self.ops = operations
        self.started = False
        self.boot_attempted = False

    def execute(self):
        if self.started:
            raise RuntimeError('Trial instance already used; inspect its result')
        self.started = True
        operations = self.ops
        operations.preflight()
        operations.enter()
        transfer = operations.stage()
        if transfer.get('terminal') is not True:
            raise RuntimeError('Transfer ownership uncertain; no recovery or BOOT allowed')
        returncode = transfer.get('returncode')
        timeout = transfer.get('timeout', False)
        if type(returncode) is not int or type(timeout) is not bool:
            raise RuntimeError('Transfer result uncertain; no recovery or BOOT allowed')
        if returncode != 0 or not operations.readback_matches():
            operations.return_native(reset=returncode != 0 and timeout)
            operations.native()
            return 'transfer failure; no BOOT'
        try:
            operations.start_observers()
            if not operations.observers_live():
                raise RuntimeError('Observers are not live before BOOT')
        except BaseException:
            # Stop observers successfully before issuing a pre-BOOT recovery.
            operations.stop_observers()
            operations.return_native(reset=False)
            operations.native()
            raise

        # Treat a failure while recording intent conservatively. The callback
        # may already have persisted its marker before reporting an error.
        self.boot_attempted = True
        try:
            operations.mark_boot_attempt()
            try:
                operations.boot()
            except Exception as error:
                operations.uncertain_boot(error)
        finally:
            # Neither callback may issue a speculative BOOT/reset/reboot.
            # Verification must still be attempted if observation/reporting or
            # a host-side interrupt fails. Any exception remains a failed run.
            try:
                operations.finish_observers()
            finally:
                operations.native()
        return 'BOOT attempted once; native return observed'
