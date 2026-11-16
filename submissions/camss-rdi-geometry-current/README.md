# Current RDI frame geometry and format limits

This carries integration 80d26059f27d onto the verified official media
committers next base 48fe5a7834cc10081887d7bcd9ff0a4cadc3fa8c, following
qualified DMA prerequisite 053ff674a48f79e6ee414f4da7135aff3437099a.
Source b45e74fd590590e274c15feb62a2229024c27d95 and combined integration
f31e5cf93121786b7c2c4fa2fb5cd6307c916a26 remain local and unpublished.
The official remote next ref was rechecked during this work and still
matched the pinned base. This is a prerequisite for proposed MSM8226
support; no mainline Fixes attribution is invented for an out-of-tree
feature. Human review and DCO certification remain pending.

MSM8226 VFE 4.0 uses the 4.1 operations. Its vendor driver programs frame
geometry even for frame-based RDI writes. The port adds an optional gen1
callback for words per line, height minus one and burst length. It checks
field bounds before taking ownership of queued buffers or enabling a
write master. A 12-bit height field holds at most 4096 lines; word count
has 16 bits. VFE and the capture node both advertise/negotiate the RDI
height limit. Other gen1 generations keep their generic limit, while PIX
keeps its prior line-based path and format behaviour. Generic preexisting
PIX format/advertisement differences are not changed by this feature.

The pinned vendor source is [Madai 03aba4427](https://github.com/peremen/android-kernel-lg-madai/tree/03aba4427a7666d57b5ae06d375e259ea337f351).
The fixture executes its actual geometry and packed-format word-count
functions as a register reference. Vendor RAW10/12 names are translated
by test data to current packed-format strides. It does not infer format
layout equivalence from equal fourcc names across these kernel eras.

The current-source model executes actual VFE enable, address initialization,
frame-drop, register setters, subdev TRY/ACTIVE, capture TRY_FMT and frame
size enumeration functions. All 3 RDI lines and 7 write masters are exercised
across 756 vendor-comparison cases with zero, one and two queued buffers.
Additional cases cover field edges, invalid configurations, optional NULL
callbacks, PIX dispatch and a modeled reserved restart. Format checks vary
height requests, packed-byte metadata, generation limits and TRY/ACTIVE.
There are 6433 modeled checks: baseline 1759 failures, candidate zero. Six
regressions fail as expected; see qualification.json.

Model structures, core services, locks and unrelated operations are
synthetic. V4L2 state helpers and format metadata are modeled. Host UAPI
headers supply public definitions; actual kernel ABI layouts, V4L2 IOCTL
core and concurrent kernel execution are not tested. Only the registration
limit assignment is executed, rather than full registration. The modeled
restart includes an explicit write-master disable, not a full physical
stream-off sequence. PIX dispatch is checked with modeled line operations;
physical PIX register behavior is not established. Two inherited unused-parameter diagnostics are scoped to their relevant
function bodies under the host-only flags, as described in NOTICE.
All other host warnings remain errors. ASan, UBSan and LeakSanitizer stay
enabled. Source extraction and frozen executed bodies are supplied.

Run `python3 replay.py /tmp/camss-rdi-replay` with Clang 21 and Linux UAPI
headers installed. The output directory must be new. The manifest is
verified, actual functions are re-extracted from the supplied snapshots,
and all 8 expected result sets are replayed without Git/network/phone access.
The source bodies must exactly match the frozen fixtures.

Four native COMPILE_TEST-disabled W=1 CAMSS component builds pass without
warnings: standalone ARM/ARM64 modules: 28 objects each, combined ARM
built-in: 27 objects and ARM64 module: 28 objects. The ARM built-in archive
contains all 27 components. Source and combined extracted model programs
are identical. See native-components.json and configs. Full kernel linking,
module installation and package/recovery qualification remain open.

Only 6 CAMSS files changed in the combined tree. Existing DMA guards,
MSM8226 resources and VFE completion code remain present. Arch and binding
trees are byte-identical to the prior fully validated frontend, retaining
all 19 DTB and full unfiltered Fx0 schema evidence without redundant DTB
builds. All other previously compiled runtime source remains unchanged.
The feature inventory keeps all 89 LTS paths, outstanding current ports
and NFC outside that delta. This is not a complete current runtime kernel
or a replacement for the maintained LTS phone baseline.

No phone action or publication was performed. Physical behavior on existing VFE 4.1 boards is unqualified. Physical V4L2 compliance,
full-frame integrity, all camera queues/modes/scenes/lens/flash interactions
and the remaining nonaudio hardware/reliability/soak work remain open.
The original r2 display-IOMMU failure is not proved fixed. Final package,
channel and kernel currency and normal update/recovery remain required.
