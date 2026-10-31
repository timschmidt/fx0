# Persistent nl80211 scan EBUSY after interface down

`nl80211_trigger_scan.py IFNAME [TIMEOUT]` sends one `NL80211_CMD_TRIGGER_SCAN` and
prints the kernel's errno. It then follows the nl80211 `scan` multicast group
and reports whether the scan completed or was aborted, and how long it took. It
uses only the Python standard library, so it runs on Nura without `iw`.

## Finding

On installed r5 (6.18.59), the first Wi-Fi connection works. After
NetworkManager brings `wlan0` down during a scan, every later scan fails:
wpa_supplicant logs `CTRL-EVENT-SCAN-FAILED ret=-16` indefinitely and
reconnection fails with "network could not be found". Reasons for that
interface cycle include applying Nura's default `wifi.cloned-mac-address=stable`
and deleting or reactivating a profile.

The localisation steps:

- wcn36xx tracing with dynamic debug: a stuck scan request causes no driver
  activity.
- `cfg80211:rdev_scan` and `mac80211:drv_hw_scan` tracepoints: neither fires.
  nl80211 rejects the request itself, because `rdev->scan_req` or
  `rdev->scan_msg` is set.
- A `wcn36xx` reload clears the state, because it frees the wiphy. Toggling the
  radio does not.

The cause is mainline `dab68a74e90b` ("wifi: cfg80211: don't free driver-owned
scan requests"), which is also in 6.18.59 stable. At `NETDEV_DOWN`, cfg80211
completes a pending scan with `___cfg80211_scan_done(rdev, false)` and parks
the netlink message in `rdev->scan_msg`. Before that commit, the driver's late
`cfg80211_scan_done()` queued `scan_done_wk`, which sent and cleared the
message. Since then a request the driver still owns is only marked stale, and
its completion frees it without queueing the work. wcn36xx completes cancelled
firmware-offload scans asynchronously, so the parked message is never sent.

The fix queues `scan_done_wk` whenever the message is parked.

## Test procedure

Reloading `cfg80211` re-registers the nl80211 family. Restart wpa_supplicant
afterwards. Otherwise it falls back to Wireless Extensions
(`ioctl[SIOCSIWSCAN]: Not a tty`) and every scan fails for an unrelated reason.
The first control run hit this and is kept privately as invalid.

The control and fix runs use the same 10-cycle loop: connect, scan while
associated, disconnect, then up to five probe scans.

| Kernel | Result |
| --- | --- |
| r5 `cfg80211` (control) | Cycle 0 passes; from cycle 1 every probe gets EBUSY with no `rdev_scan`; no later cycle connects |
| r5 with fixed `cfg80211` module | 10/10 cycles; scans 1.8–3.8 s; 0 wpa_supplicant scan failures |
| Installed signed r6 | 10/10 cycles; 0 scan failures, 0 WEXT fallbacks; taint 0 |
