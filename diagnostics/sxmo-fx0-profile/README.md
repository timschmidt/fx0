# Fx0 Sxmo development profile

Tested with Nura v26.06, the signed native 6.18.59-r3 kernel and UPower r3.
The owner confirms visible terminal/keyboard, correct typing, and bottom-edge
keyboard close/open. GPIO Home and both volume buttons each produce a matched
press/release in this installed boot; prior RAM testing records three each.

Install `sxmo_deviceprofile_lg,madai.sh` in `/usr/local/bin/`, the hook in the
login user's `$XDG_CONFIG_HOME/sxmo/hooks/`, the wrapper in `/usr/local/libexec/`,
and the desktop entry in `/usr/share/wayland-sessions/`. Scripts must be executable;
the user hook belongs to the login user. Use the normal packaged TinyDM login
and input/seat groups as described in the native Wayland console fixture.

The profile uses observed power/GPIO identifiers and scale1.5. Physical gesture
recordings have continuous motion, no drops, and durations below200ms. Defaults
require125px travel and a50px edge band, excluding the measured attempts. The
Fx0 profile uses60px travel and120px edges. The hook permits25-degree slant;
measured otherwise vertical swipes include about20 degrees. Synthetic replay
reproduces failure with defaults and passes with these settings. A subsequent
physical installed test confirms both keyboard gestures. The compositor uses
identity calibration; the board DT applies both required axis inversions.

The wrapper selects Pixman and the stable native DRM by-path node. Audio/modem
integration remains disabled during this development test. The `unlock` state
restriction and the user's `sxmo.noidle`/`sxmo.nosuspend` cache files retain the
current no-idle/no-suspend policy. The TinyDM first-start gate also remains.
The foot user config uses `[colors-dark]` for the installed version's supported
section spelling. These fixtures do not qualify GPU, charging, suspend or the
complete phone interface. Home's final UI action, long presses and wake are open.

After installation, validate shell syntax, select the desktop entry with
`tinydm-set-session -f -s`, and explicitly open the development first-start gate.
Use the actual login user and runtime directory. For recognizer diagnostics add
`-v` to the hook temporarily and capture raw events independently; keep full
logs private. The installed test completed with verbose tracing removed and the
same60/120/25 settings verified. See the installed r3 and gesture-profile evidence.
