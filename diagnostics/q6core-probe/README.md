# ADSP q6core version probe

Audio step 3 needs the APR service versions of the Fx0's ADSP firmware before
the mainline QDSP6 AFE/ASM/ADM drivers can be reused. Mainline `q6core` sends
nothing at probe time, so `fx0_q6probe.c` calls `q6core_is_adsp_ready()` and
`q6core_get_svc_api_info()` for every APR service ID and logs the answers. It
sends only version and state queries and registers no audio devices.

Build it next to a copy of `sound/soc/qcom/qdsp6/q6core.c` and `q6core.h` as
an external module (this `Kbuild`), against the exact kernel source and
configuration of the running kernel plus `CONFIG_QCOM_APR=m`. Enabling the
full QDSP6 options would also turn on built-in compress/topology support that
the running kernel lacks. Use the same compiler as the kernel package (Alpine
clang 22.1.3 for r8). The modules are unsigned, so they taint that boot only.

Boot the matching kernel from RAM with a DTB that has the APR node (fx0-linux
`integration/fx0-apr-probe`), load `apr.ko` and its dependencies, then
`q6core.ko` and `fx0_q6probe.ko`, and read `fx0_q6probe:` from the kernel log.
