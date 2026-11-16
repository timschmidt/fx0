# NGD QMI power transaction allocation errors

An allocation failure in `qmi_txn_init()` was overwritten before a power request.
The helper could send an unregistered transaction and retire an unrelated
transaction whose ID matches the negative allocation error truncated to 16 bits.
Return the original error before send, wait or cancellation. Zero and positive
allocated IDs still work. The source patch stands alone on the pinned official
SLIMbus base; the runtime patch adds the same two lines to the existing Fx0 work.

Six exact NGD/QMI bodies pass 576 cases and 7,008 checks with logical IDR,
completion, mutex and socket services; the previous helper fails 896 checks.
The cases include active/inactive requests, allocation/send/wait/remote errors,
ID zero, positive IDs, and preservation of another live transaction. Five
independent regression controls are rejected. Normal LSan and fail-fast
ASan/UBSan are enabled. Eight ARM/ARM64 objects build with LLVM21 W=1 and strict
callback checking without diagnostics. The runtime kernel and 459 modules build;
module signature, ELF, release and dependency checks pass. This incremental build
does not establish clean reproducibility, installed package recovery or physical
acceptance. Nine earlier generated regression programs are byte-identical.

Run `python3 -B replay.py /tmp/new-qmi-replay-directory` with clang-21 and patch
installed. The replay uses only packet inputs, checks their hashes, applies both
patches without fuzz or offset, and reruns the synthetic before/after and five
regression controls. It requires normal LeakSanitizer support outside ptrace.

The attached NGD hardware stop contract and failed-suspend rollback remain open.
The primary upstream reset fix rules out simply retaining DMA across power
collapse. Vendor clock pause disconnects SPS endpoints before requesting QMI
inactivity; its framework return path is not proof that modern BAM reset is safe.
No undocumented NGD stop sequence or remote firmware guarantee is assumed.

Prior software admission, response storage and BAM callback synchronization
remain in `../slimbus-dma-admission-current` at review commit
332eac6142534c1e22c4790ff4704b8785e3c660. That prerequisite packet's archive SHA256
is b0c0157151c4bd274b91ca14bda95a10aa798c791c1e387b1609de89886453ae.
This small standalone replay establishes only the new QMI allocation-error scope.

Codex generated this patch and logical qualification. Original authorship and
human trailers on dependencies are preserved. Human review and DCO remain
pending. These heads are local and unpublished; the draft is unsent. No real
QMI, DMA, firmware, audio, phone, radio scan or network configuration is exercised.
