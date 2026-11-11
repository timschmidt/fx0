# sxmo-utils draft submission

Three patches for [sxmo-utils](https://git.sr.ht/~mil/sxmo-utils), based on
`master` at `303c755e88d2a25c01bdbc5b46aba1939318f839` (fetched October 31,
2026). Sxmo takes patches by email to `~mil/sxmo-devel@lists.sr.ht`. **Not
sent:** sending needs the owner's approval and Signed-off-by.

[The patch](0001-deviceprofiles-add-LG-Fx0.patch) adds
`scripts/deviceprofiles/sxmo_deviceprofile_lg,madai.sh`. It sets the power and
volume inputs, a 1.5 Sway scale, and the lisgd threshold and edge size
measured on the panel. Current sxmo-utils needs no per-device hook link: the
stock `sxmo_hook_lisgdstart.sh` reads both lisgd variables from the profile.

The phone currently runs a user hook that also passes `-r 25` to lisgd. That
flag cannot be set from a profile, and nothing in the record shows it is
needed, so it is not part of the patch.

Checks: `sh -n` and shellcheck (Alpine 3.24) are clean. On the phone the same
variables, used from `/usr/local/bin`, give working Sxmo gestures and buttons;
the owner confirmed input under the GLES2 session.

The [haptics follow-up](0002-deviceprofiles-fix-LG-Fx0-haptics.patch) exports
the board's persistent PM8226 input path and strength 39168. The native Sxmo
environment loader and installed utility pass as the graphical user. The
uncorrected r50 driver programs a 2.1 V target at that strength, and a
separate kernel candidate restores the intended range. The two profile
exports are installed locally and the next native Sway session inherits
both. System suspend and tactile qualification remain open. [Measurements and scope](../../diagnostics/vibrator/README.md)


The [notification completion draft](0003-notifs-dispatch-after-write-completion.patch)
removes attribute-triggered dispatch from the pinned master source. A real-inotify
fixture reproduces partial-file deletion and checks seven complete deliveries
without empty or early dispatch. All three patches apply in order with zero
fuzz. The installed 1.18.1 script also needs close-write monitoring and removal
of its premature touch; that release-specific correction and an opt-in Fx0 user
haptics hook are maintained in [the diagnostic](../../diagnostics/sxmo-notifications/README.md).
The real phone passes normal, muted and re-enabled notifications, including
Dunst replies and PMIC timing. The user hook is outside this upstream patch.
The drafts remain unsent.
