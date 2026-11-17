#define MSM_VFE_IMAGE_MASTERS_NUM 7
#define MSM_VFE_COMPOSITE_IRQ_NUM 4
#define VFE_FRAME_DROP_VAL 30
enum vfe_output_state {
	VFE_OUTPUT_OFF,
	VFE_OUTPUT_RESERVED,
	VFE_OUTPUT_SINGLE,
	VFE_OUTPUT_CONTINUOUS,
	VFE_OUTPUT_IDLE,
	VFE_OUTPUT_STOPPING,
	VFE_OUTPUT_ON,
};
enum vfe_line_id {
	VFE_LINE_NONE = -1,
	VFE_LINE_RDI0 = 0,
	VFE_LINE_RDI1 = 1,
	VFE_LINE_RDI2 = 2,
	VFE_LINE_PIX = 3,
	VFE_LINE_NUM_MAX = 4
};
struct vfe_output {
	u8 wm_num;
	u8 wm_idx[3];

	struct camss_buffer *buf[2];
	struct camss_buffer *last_buffer;
	struct list_head pending_bufs;

	unsigned int drop_update_idx;

	union {
		struct {
			int active_buf;
			int wait_sof;
		} gen1;
		struct {
			int active_num;
		} gen2;
	};
	enum vfe_output_state state;
	unsigned int sequence;

	int wait_reg_update;
	struct completion sof;
	struct completion reg_update;
};
struct vfe_isr_ops {
	void (*reset_ack)(struct vfe_device *vfe);
	void (*halt_ack)(struct vfe_device *vfe);
	/* WM indices whose saved completions belong to a drained output. */
	u32 (*reg_update)(struct vfe_device *vfe, enum vfe_line_id line_id);
	void (*sof)(struct vfe_device *vfe, enum vfe_line_id line_id);
	void (*comp_done)(struct vfe_device *vfe, u8 comp);
	void (*wm_done)(struct vfe_device *vfe, u8 wm);
};
