# Fx0 Sxmo notifications

Installed `sxmo-utils-1.18.1-r6` watches attribute events while its writer first
touches an empty file. A real-inotify control deletes a partial notification
before the writer finishes. The pinned newer master source adds close-write
but retains the attribute race. Dispatch after close-write or atomic move
instead. Delete events still update notification counts.

[The release patch](notifs-close-write.patch) also removes the premature touch.
It is installed locally in `/usr/bin/sxmo_notifs.sh`, with the original retained
at `/var/tmp/fx0-notifications-01/sxmo_notifs.before.sh`. The APK database is
unchanged. A later package update may overwrite this local correction.
The [unsent upstream draft](../../submissions/sxmo-utils/0003-notifs-dispatch-after-write-completion.patch)
is based on `303c755e88d2a25c01bdbc5b46aba1939318f839`; it needs only the
attribute-event removal because that source already handles close-write.

## Haptics hook

The stock notification hook has vibration commented out. The installed
[device-specific user hook](sxmo_hook_notification.sh) at
`$XDG_CONFIG_HOME/sxmo/hooks/lg,madai/sxmo_hook_notification.sh` requests one
300 ms pulse through the installed utility, using the device profile's strength.
It respects Sxmo's existing `$XDG_CONFIG_HOME/sxmo/.novibrate` flag. The original
hook was absent. Only `sxmo_notificationmonitor` is stopped and started through
`superctl`; Sway keeps PID 1609 on the same native r50 boot.

Three synthetic notifications use the ordinary `sxmo_notifs.sh new` command
as the graphical user and the real monitor/Dunst bus. The observer matches
the exact test message and its D-Bus reply, then closes only that returned ID
and removes its own history entry and notification file.

| Case | Dunst Notify calls | PMIC enabled samples | Enable duration bounds |
| --- | --- | --- | --- |
| Normal | 1 | 42 | 293.06–306.84 ms |
| `.novibrate` present | 1 | 0 | No enable |
| Flag removed again | 1 | 42 | 290.63–303.98 ms |

Both enabled cases use code 21, a programmed 2.1 V target on uncorrected r50.
All finish off. This is electrical notification-path qualification; analogue
voltage, visual/tactile acceptance, lock and system suspend remain open.
The source-range-corrected kernel module remains unbooted.

## Regression fixture

On the phone, run as root against the login user's runtime directory:

```sh
python3 check-delivery.py \
  --original /var/tmp/fx0-notifications-01/sxmo_notifs.before.sh \
  --candidate /usr/bin/sxmo_notifs.sh \
  --runtime-dir /run/user/10000
```

The fixture uses real `inotifywait` and isolated directories. Desktop/hardware
hooks are mocked and reject empty or missing message content. It holds a file
open while generating an attribute event, checks no delivery before close,
then checks the completed notification, five ordinary writer calls and one
atomic move. The original loses the partial record; both release and pinned
upstream candidates deliver all seven without errors. Temporary directories
and fixture process groups are removed. An initial weaker fixture allowed an
empty dispatch to count; its result is retained separately and is not the
acceptance fixture. The upstream test body passed, but its outer wrapper had
a cleanup-name collision; separately verified cleanup removed the remaining
two-file payload directory.

## Rollback

Run in the graphical user's existing Sxmo environment after verifying that the
installed script/hook still match the evidence. Stop only the notification
service, restore its original script and remove the newly added board hook:

```sh
superctl stop sxmo_notificationmonitor
sudo install -m755 /var/tmp/fx0-notifications-01/sxmo_notifs.before.sh /usr/bin/sxmo_notifs.sh
rm -- "$XDG_CONFIG_HOME/sxmo/hooks/lg,madai/sxmo_hook_notification.sh"
superctl start sxmo_notificationmonitor
```

The original script SHA256 is
`c9ff07dec95585cf065dc4ce67c17aef9877b92a0ab0915b4376fe922c6525e5`.
Final boot, kernel/initramfs, package database/world and module hashes match
preflight, with zero taint and no pending or failed units. All test files,
displayed/waiting notifications and history entries are gone; the mute flag is
absent as before. These local overrides still need package/configuration
integration for a reproducible final installation.
[Evidence](../../evidence/2026-11-10-sxmo-notification-haptics.json)


## Reproducible r7 package candidate

The [r7 manifest](../../manifests/sxmo-utils-r7.json) pins the recipe at
[`8c60fa379d63`](https://github.com/timschmidt/fx0-pmaports/commit/8c60fa379d6377a08dd9c894010942cf0dfd9c43),
branch `integration/fx0-sxmo-r7`. It reconstructs the installed r6 recipe from
the exact Alpine base and retained hotspot patches. The r6 hotspot scripts
match the phone's signed cached APK byte for byte. The new package adds the
Fx0 profile, the notification write fix and a packaged board hook.

The loader now searches user device hooks, user generic hooks, packaged device
hooks and packaged generic hooks, in that order. Multiple data roots follow
`XDG_DATA_DIRS` order. Missing device directories add no empty PATH entry.
The generic notification hook remains unchanged. The new Fx0 hook has the
same bounded behavior as the tested user hook. It gains the normal generated
`configversion` line when packaged.

```sh
python3 check-packaged-hooks.py   --source /path/to/applied/sxmo-utils-1.18.1   --control-init /path/to/original-release/configs/profile.d/sxmo_init.sh
```

Seven cases execute the real environment loader with mocked vibration,
including user priority, multiple data roots, mute and an unaffected other
device. All four unsent upstream drafts apply in order to the pinned master.
The release recipe uses its matching notification backport.

Two full ARM source builds produce 14 byte-identical signed APKs. All signatures
verify against the current phone trust snapshot; altered signed metadata and
repository data fail independent verification. Four rebuilt helpers have the
expected ARM hard-float ABI and load with the target musl runtime. Their sources
are unchanged. Apart from those helpers, the only changed payloads are the
notification script and two installed copies of the environment loader; the
profile and shared hook are the only new files. The existing recipe's `!check`
setting is retained; targeted tests run separately. No audio test is performed.

A temporary native probe executes five exact signed-APK payloads from RAM,
with the real loader, rebuilt vibrator helper, isolated monitor and Dunst.
The installed-loader control delivers once without vibration; the new loader
selects the packaged board hook. Normal and re-enabled cases deliver once and
produce bounded 300 ms pulses; mute delivers once without enable. The original
monitor and Sway keep their PIDs, and installed files/database/world stay equal.
All probe payloads, notifications, history and owned FIFOs are gone afterward.
The monitor's existing duplicate exit-trap cleanup emits already-removed
messages; both isolated process groups and FIFOs are verified cleaned up.

Offline resolution against the current r50 database upgrades exactly the eight
installed Sxmo packages to r7. The three audio dependency subpackages remain
empty metadata packages with their existing dependency definitions. r7 is **not
installed**. The r6 local correction and user overrides remain active.

Before deployment, capture current package-owned files, database/scripts/triggers,
world, boot and the local profile/user hook on the phone and host; verify an
exact restoration rehearsal. Then run the normal eight-package transaction,
including its normal hooks, and verify boot readback and installed payloads.
Retire only the backed-up profile and notification overrides after the packaged
loader selects their replacements. Recheck real notifications, existing input
settings and a later session startup. These deployment, rollback and subsequent
session gates remain open. [Candidate evidence](../../evidence/2026-11-10-sxmo-r7-arm-candidate.json)
