# Current private provisioning rollback images

The current capture is five images, 43,515,904 bytes: persist (32 MiB), modemst1,
modemst2 and FSG (3 MiB each), and FSC (512 KiB). The modem firmware partition
is excluded. Original factory-era backups are preserved separately.

The private locations are:

- Phone: `/var/lib/fx0-rollback/modem-provisioning-01`, on rootfs p35.
- Host: `local/modem-provisioning-backup-01/host-backup`, on encrypted storage.
- Unit binding: `local/modem-provisioning-backup-01/unit-binding.private.json`,
  tied to the exact manifest and original private card record.

This is two persistent copies on different phone/host filesystems, with one
off-device copy. The phone copy shares the source eMMC. Neither copy proves
physical restoration or power-loss survival. Keep original dumps, private
manifests, card records and current snapshots out of public Git.

## Capture and verify

`capture-provisioning.py` runs on the unchanged installed r50 phone. It requires
a fresh destination directly beneath `/var/lib/fx0-rollback` on rootfs p35,
expected current-boot identity and a private map of five source digests. Obtain
that baseline with the modem disabled; do not substitute factory-era hashes.

The helper checks native services, zero taint, absent MSS/storage daemons,
exact partition labels/offsets/sizes and no source writer descriptors. Sources
must be unmounted or mounted read-only. It opens source devices read-only,
copies each exact bounded image to a mode-600 file and fsyncs/rereads it. The
entire source set must match before and after capture, and native state must
remain unchanged. A failed slot is preserved and cannot be reused automatically.
Only successful capture creates a complete manifest and terminal success record.

Send the public helper through the established private SSH client and collect
its manifest privately. Copy only the five verified images and the manifest/
controller to a fresh mode-700 host folder; verify every transfer before treating
it as a backup. Fsync files and directory. Reread both persistent copies, compare
fresh source digests and verify original card identity privately.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 diagnostics/modem-control/verify-provisioning-backup.py \
  --backup local/modem-provisioning-backup-01/host-backup \
  --output local/provisioning-verification-new.json
```

The verifier requires the complete fixed five-image set, terminal successful
capture, exact source map, private regular files, exact sizes and agreement
between every image and recorded source reread. Its output omits per-partition
digests and payload. It verifies bytes and receipts, not receipt authenticity or
the phone's current state. Always recheck freshness before a future firmware
trial or restoration. Public evidence pins the private manifest and verifier;
individual provisioning-image digests remain private.

```sh
TMPDIR="$PWD/local/kernel-reconstruction/tmp" PYTHONDONTWRITEBYTECODE=1 \
python3 -m unittest discover -s tests -p test_modem_provisioning_backup.py -v
```

Four methods/25 synthetic cases cover bounded copy, unchanged source, no-clobber,
short/oversized/changed/symlink/nondevice sources and eighteen bad snapshot/map/
digest/permission/controller cases. Native system/proc guards passed during the
real capture; they are not fault-injected by these file-fixture tests.

## Restoration prerequisites and limits

No automatic restore helper or physical provisioning write was run. The host
payload rehearsal copied all five images to fresh regular files and verified
their digests; those disposable files were then removed.

For an actual restoration, use the established standalone RAM rescue with modem
and remote-storage services inactive. Verify the original private card identity,
both GPT copies and these exact targets before authorizing writes:

| Image | Partition | First sector | Sectors |
| --- | --- | ---: | ---: |
| persist | mmcblk0p14 | 212992 | 65536 |
| modemst1 | mmcblk0p17 | 409600 | 6144 |
| modemst2 | mmcblk0p18 | 415744 | 6144 |
| fsg | mmcblk0p20 | 425984 | 6144 |
| fsc | mmcblk0p21 | 432128 | 1024 |

All target filesystems must be unmounted, with no writers or consumers; writing
under a mounted persist filesystem is not the documented restoration route.
Verify the complete current snapshot and unit binding first. Restore only the
selected consistent provisioning set to its exact bounded targets, sync, and
independently read/hash every restored target before leaving rescue. Do not
replace modem firmware, boot, GPT or unrelated partitions as part of that action.
Retain both original and pre-restoration current images for review. Physical
restore qualification remains unfinished and must be recorded separately.

The current newest-boot display/touch gate remains pending. No RAM entry,
firmware start, modem/radio action or package installation follows from making
these backups. See [evidence](../../evidence/2026-11-09-modem-provisioning-backup.json).
