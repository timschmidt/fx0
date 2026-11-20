# CAMSS: CSID without a same-index VFE (draft, not sent)

On MSM8916, MSM8226, MSM8939 and MSM8953 CAMSS has more CSIDs than VFEs and
routes every CSID through ISPIF. Commit b2c2715e5aaf made every CSID power the
VFE with its own index first, which indexed past the VFE array for CSID1 and
above; b1e6eef535df turned that into `-EINVAL`, so CSID1 cannot power on and a
sensor routed through it cannot stream. The draft makes the parent get/put a
no-op when ISPIF is present and no VFE has the CSID's index.

Status: built for ARM with the Fx0 MSM8226 configuration (W=1, no warnings,
module links). Hardware test pending: stream a sensor through CSID1
(`msm_csiphyN -> msm_csid1 -> msm_ispif -> msm_vfe0_rdiN`) on the Fx0.

Source: timschmidt/fx0-linux `development/fx0-camss-csid-without-vfe-01`.
Upstream sending waits for owner approval; the draft carries no Signed-off-by.
Target tree for submission: media.git next; rerun checkpatch there.
