# pm8xxx-vibrator review drafts

Three unsigned functional fixes, based on the input maintainer's
`master`/`next` at `8e16f8bbf1bd528975fd6f4081eaf00513c1d83e`:

1. Select the voltage range from the register layout.
2. Clamp the inclusive maximum voltage before encoding it.
3. Replace the previous drive bits during active strength changes.

The [cover letter](0000-cover-letter.patch) contains the symptoms, conditions,
AI-assistance disclosure, suggested recipients, and physical-test limits.
Apply the three files listed in [series](series) in order. They need no other
driver patches. The current allocation API is preserved.

The primary kernel.org advertisement and official mirror matched when the base
was selected. A later primary recheck still reports that base; the mirror
recheck failed to connect. See [reference checks](upstream-refs-recheck.json).

The base and all three prefixes compile as ARM objects with Clang 21.1.8,
`W=1`, KCFI, and full compressed DWARF5, without compiler diagnostics.
Adapting the earlier Fx0 configuration produced two `olddefconfig` notices
for the old modular `IPV6` and `NETFILTER_NETLINK` settings; this is distinct
from the clean object checks. These are object builds, without a full kernel
or module link. GCC and a full boot of this maintainer tree remain untested.

All five generated actual-C fixtures are byte-identical to the earlier
qualified fixtures: 768 ASan/UBSan cases, rejection of the original code, and
three independent regression controls. The unchanged tests are reused, with
their hashes recorded in [fixture equivalence](fixture-equivalence.json).
PMI632 upper-byte encoding is outside their coverage. Earlier signed RAM
trials exercise the same fixes on Fx0 PM8226 with the separate integration
kernel; other PMIC variants have no physical coverage here.

Each exported patch passes strict checkpatch with zero findings, with only
sign-off checking disabled. Exported prefixes replay to the expected Git trees.
The [commit mapping](draft-series.json), [object checks](prefix-object-checks.json),
[style results](draft-checkpatch.json), [export replay](export-replay.json),
and [recipient lookup](maintainer-lookup.json) retain the exact scope.

The current tree's `AGENTS.md` links to `README`, which requires its coding
assistant procedure. That procedure prohibits agents from adding DCO sign-offs
or sending submissions. Human review, certification, and any additional
maintainer testing remain before sending. The patches have not been mailed;
no PR, review, acceptance, or security impact is claimed.
