# sxmo-utils draft submission

One patch for [sxmo-utils](https://git.sr.ht/~mil/sxmo-utils), based on
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
