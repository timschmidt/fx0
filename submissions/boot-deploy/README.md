# boot-deploy draft submission

One change for [boot-deploy](https://gitlab.postmarketos.org/postmarketOS/boot-deploy),
based on `main` at `a50452a054233c2d7bf6142cbc332c94c79cc18f` (unchanged
upstream as of October 31, 2026). boot-deploy takes merge requests on
postmarketOS GitLab. **Not sent:** opening the merge request needs the owner's
approval.

The [submission branch](https://github.com/timschmidt/fx0-boot-deploy/tree/submission/fx0-bootimg-offset)
is `c6e308d71517`. It squashes `integration/fx0-boot-offset` into one commit
with the same tree.

[The patch](0001-Preserve-a-configurable-prefix-when-flashing-Android.patch)
adds `deviceinfo_flash_bootimg_offset` (decimal bytes, default 0). With an
offset, `vendor_flash_android_bootimg()` writes the image after a reserved
prefix, as lk2nd needs (512 KiB), and keeps the prefix and trailing bytes. A
non-zero offset must be a multiple of 512, and the image must fit after it.

## Checks

- **Tests:** the upstream suite passes in Alpine 3.24, including the new
  `test_flash_bootimg_offset`. It covers rejected offsets, exact-fit writes, and
  prefix and trailing-byte preservation against real files.
- **shellcheck:** `boot-deploy`, `boot-deploy-functions.sh` and the test script
  are clean.
- **Hardware:** a backport to 0.23.0 is installed on the LG Fx0 as
  `boot-deploy-0.23.0-r1`. `mkinitfs` writes the image at offset 524288 with
  the lk2nd prefix unchanged, the device boots it, and kernel package upgrades
  (r7 to r8) update it. See the
  [evidence](../../evidence/2026-10-31-boot-deploy-offset-updates.json).

## Companion change

`pmaports` validates deviceinfo keys against `deviceinfo_schema.toml`. The
[fx0-storage pmaports branch](https://github.com/timschmidt/fx0-pmaports/tree/integration/fx0-storage)
adds `deviceinfo_flash_bootimg_offset` to the schema. That should be a separate
pmaports merge request once boot-deploy accepts the key.

The patch carries no Signed-off-by; the owner adds it before sending.
