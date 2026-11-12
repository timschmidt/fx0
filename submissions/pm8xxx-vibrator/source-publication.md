# Public vibrator source branch

The three unsigned [review patches](README.md) are published on
[submit/pm8xxx-vibrator-voltage-v1](https://github.com/timschmidt/fx0-linux/tree/submit/pm8xxx-vibrator-voltage-v1)
at `cc01b2298aec8bf692d61f41a896f76dc62ab643`. The branch preserves the
original commit authors and upstream ancestry. No email or upstream PR was sent.

The primary Input advertisement and official mirror both reported
`master`/`next` at `8e16f8bbf1bd528975fd6f4081eaf00513c1d83e` on
November 12, 2026, at 02:28 UTC. [Publication and verification details](source-publication.json)
retain the exact source tree and checks.

The recovered local graph has no missing reachable objects. All three exported
prefixes now replay with ordinary `git write-tree`, without its missing-object
option. The local repository retains three boundaries already available in
the destination fork; it does not contain all mainline history locally.

The original stable diffs and receiving-tree diffs use different blob IDs
because the receiving file uses `devm_kzalloc_obj`. Every non-index diff byte
matches, and the complete file before and after each patch differs from the
qualified stable version only in that expected allocation call. The published
receiving-tree source and exported patches remain unchanged.

Existing qualification is reused: four ARM object prefixes with Clang 21.1.8,
`W=1`, KCFI and compressed DWARF5; final callback type-word inspection;
768 actual-C ASan/UBSan cases; rejection of the original and three independent
regressions; and strict style checks. Their recorded input, fixture and object
hashes were checked. These unchanged compilation and behavior tests were not
rerun for publication.

Full receiving-tree kernel/module links remain pending while host memory is
below the prepared build's start threshold. This tree has not been booted on
the phone. GCC, other PMIC hardware and PMI632 upper-byte encoding remain
unqualified. The earlier Fx0 PM8226 RAM results apply to the separate integration
kernel. Human review and DCO certification remain pending.
