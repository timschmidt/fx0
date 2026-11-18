#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Build the ARM32 Venus kernel and its three modules in a new output directory.
set -eu
umask 077

if [ "$#" != 5 ]; then
	printf '%s\n' "Usage: $0 kernel-tree base-config reference-Module.symvers signer.pem new-output-directory" >&2
	exit 2
fi

kernel=$(realpath -- "$1")
config=$(realpath -- "$2")
symbols=$(realpath -- "$3")
signer=$(realpath -- "$4")
output=$(realpath -m -- "$5")

test -f "$config"
test -f "$symbols"
test -f "$signer"
test -z "$(git -C "$kernel" status --porcelain)"
commit=$(git -C "$kernel" rev-parse HEAD)
epoch=$(git -C "$kernel" show -s --format=%ct "$commit")
jobs=${FX0_BUILD_JOBS:-4}

mkdir -- "$output"
mkdir -- "$output/certs"
install -m 400 -- "$signer" "$output/certs/fx0-ram-signing.pem"
signer_hash=$(sha256sum < "$signer")
cp -- "$config" "$output/.config"
"$kernel/scripts/config" --file "$output/.config" --set-str MODULE_SIG_KEY certs/fx0-ram-signing.pem
cp -- "$output/.config" "$output/.config.expected"

export LC_ALL=C TZ=UTC SOURCE_DATE_EPOCH="$epoch"
export KBUILD_BUILD_USER=fx0 KBUILD_BUILD_HOST=ram-kernel KBUILD_BUILD_VERSION=1
KBUILD_BUILD_TIMESTAMP=$(date -u -d "@$epoch" '+%Y-%m-%d %H:%M:%S +0000')
export KBUILD_BUILD_TIMESTAMP

make -s -C "$kernel" O="$output" ARCH=arm LLVM=-21 LOCALVERSION= olddefconfig
cmp -- "$output/.config" "$output/.config.expected"
make -s -C "$kernel" O="$output" ARCH=arm LLVM=-21 LOCALVERSION= -j"$jobs" zImage

# Input module exports provide the rest of the linked runtime ABI. Use the
# new kernel's own exports for vmlinux and let modpost check every import.
awk '$3 != "vmlinux" && $3 !~ /\/qcom\/venus\/venus-(core|enc|dec)$/' "$symbols" \
	> "$output/linked-modules.symvers"
cp -- "$output/vmlinux.symvers" "$output/built-in.symvers"
cat > "$output/modpost-with-symbols" <<'SH'
#!/bin/sh
build_dir=${0%/*}
exec "$build_dir/scripts/mod/modpost" -i "$build_dir/linked-modules.symvers" "$@"
SH
chmod 700 "$output/modpost-with-symbols"
base=drivers/media/platform/qcom/venus
make -s -C "$kernel" O="$output" ARCH=arm LLVM=-21 LOCALVERSION= -j"$jobs" \
	"MODPOST=$output/modpost-with-symbols" \
	"$base/venus-core.ko" "$base/venus-enc.ko" "$base/venus-dec.ko"

test "$(sha256sum < "$signer")" = "$signer_hash"
test "$(sha256sum < "$output/certs/fx0-ram-signing.pem")" = "$signer_hash"
test "$(git -C "$kernel" rev-parse HEAD)" = "$commit"
test -z "$(git -C "$kernel" status --porcelain)"
printf '%s\n' "$commit" > "$output/source-commit"
printf 'Built %s in %s\n' "$commit" "$output"
