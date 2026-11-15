# Current mainline source applicability

The candidate patch at `250e7412a5a15068b2a2fe32b57b66c300c91b5f` applies
without edits to complete CAMSS source files fetched from verified mainline
head `23c62304dde29abe92013d85910d03a77dada35d`. Each fetched file matches
the Git blob ID returned by GitHub. The check includes the six changed files
and the shared VFE implementation used by the host harness.

Four of these full files differ from the candidate's f71 parent. This check
keeps those upstream changes; it does not replace the files with the stable
source. On the patched mainline export, ASan/UBSan passes all 28 scenarios for
each of the 4.1, 4.7 and 4.8 dispatchers (84 executions). All fifteen baseline
and unsafe-alternative controls reject the expected behavior.

This is a source-only application and extracted-function regression. It
does not establish a complete mainline ARM build, physical camera behavior
or readiness on the current media maintainer integration branch. Ref
discovery on the official media repository failed before its advertised
heads could be verified, using both HTTP/2 and HTTP/1.1. That gate remains
open. No publication or maintainer contact occurred.

[Sanitized evidence](../../evidence/2026-11-15-camera-vfe-mainline-source-applicability.json)

[Mainline gen1 source at the tested pin](https://github.com/torvalds/linux/blob/23c62304dde29abe92013d85910d03a77dada35d/drivers/media/platform/qcom/camss/camss-vfe-gen1.c)
