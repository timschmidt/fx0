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
