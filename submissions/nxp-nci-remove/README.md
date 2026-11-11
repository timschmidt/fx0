# NXP NCI removal review drafts

Two unsigned fixes target the NFC maintainer's advertised `for-linus` tip,
`b61732f47316d45f27706db7812950145d3327b5` (2026-09-23). Its current `for-next`
tip is Linux 7.3-rc3. The [primary reference recheck](primary-refs-recheck.json)
records that both advertised branches remain unchanged on 2026-11-11.
The same removal problems remain in the newer input tree at
`8e16f8bbf1bd528975fd6f4081eaf00513c1d83e`; intervening relevant changes are
allocation-helper conversions. This is a maintainer-branch draft, without a
claim that the base is the latest mainline.

Patch 1 unregisters outside the mode mutex so the close callback can take it.
Patch 2 preserves receive through the closing reset, then drains it before NCI
state is freed. Failed IRQ registration does not acquire IRQ ownership. The
series does not export the earlier intermediate ordering that drained receive
before unregister. Optional clocks, bindings and board changes remain separate.
Existing upstream protocol, error-handling, firmware and ID-table changes stay
intact.

The [cover letter](0000-cover-letter.patch) contains symptoms, conditions,
contacts, AI disclosure and qualification limits. Apply [series](series) in
order. [Commit mapping](fix-series.json), [strict style results](fix-checkpatch.json),
[recipient lookup](maintainer-lookup.json), and [export replay](export-replay.json)
record the exact review inputs. No mail or PR has been sent. Human review and
DCO certification remain; the pinned tree requires `Assisted-by: LLM` and
prohibits agent-added sign-offs.

Six [host tests](host-tests.json) pass nine modeled lifecycle cases and reject
six independent regression controls under ASan/UBSan. The [case results](host-fixture-results.json)
include recursive close locking, reset-before-drain ordering, pending IRQs,
optional callbacks, and failed IRQ ownership. The existing clock-aware harness
is reused with only clock-related model state omitted; all sixteen extracted
driver/NCI callback bodies remain exact. This exercises no NFC hardware or live
kernel endpoint. NCI 2.x notification timing, real timeouts, concurrent firmware
download and physical IRQ timing remain unqualified.

To run the tests from the coordination repository against a patched checkout:

```sh
PYTHONDONTWRITEBYTECODE=1 CC=clang \
FX0_NFC_REMOVE_SOURCE=/path/to/patched/linux \
python3 -m unittest discover -s tests -p test_nxp_nci_remove_upstream.py -v
```

The base and both prefixes pass matching core/I2C/firmware ARM object builds:
nine objects with Clang 21.1.8, `W=1`, KCFI and compressed DWARF5. There are no
compiler diagnostics. The old Fx0 configuration produces two conversion
notices during `olddefconfig`, for `IPV6` and `NETFILTER_NETLINK`.
[Object checks](prefix-object-checks.json) and [callback inspection](object-inspection.json)
retain the commands, hashes, flags and actual ARM type words.

Full kernel/module links, GCC, networking `allyesconfig`/`allmodconfig` builds,
and hardware open/unregister, RF, suspend and reliability remain open. The
private transport operations layout changes: any later module trial must use
a completely rebuilt and independently validated matching cohort. Earlier cold
Fx0 lifecycle results do not qualify this path. These drafts are not claimed
ready for sending or installation.
