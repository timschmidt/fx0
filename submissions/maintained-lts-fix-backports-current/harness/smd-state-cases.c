// SPDX-License-Identifier: GPL-2.0-only
static void reset(void) {memset(&edge,0,sizeof(edge));memset(channels,0,sizeof(channels));for(int i=0;i<4;i++)edge.channels.items[i]=&channels[i];creates=removes=fail_create=0;create_error=-ENOMEM;cases++;}
int main(void) {
 const char *names[]={"rpm_requests","diag","other","log"};
 for(int no_suspend=0;no_suspend<1;no_suspend++)for(int name=0;name<4;name++)for(unsigned int state=0;state<7;state++)for(unsigned int remote=0;remote<7;remote++)for(int registered=0;registered<2;registered++) {
  reset();edge.no_suspend=no_suspend;edge.channels.count=1;channels[0]=(struct qcom_smd_channel){names[name],state,remote,registered};
  bool create=state==SMD_CHANNEL_CLOSED&&!registered&&(!no_suspend||!name)&&(!name||remote==SMD_CHANNEL_OPENING||remote==SMD_CHANNEL_OPENED);
  bool remove=(state==SMD_CHANNEL_OPENING||state==SMD_CHANNEL_OPENED)&&remote!=SMD_CHANNEL_OPENING&&remote!=SMD_CHANNEL_OPENED;
  qcom_channel_state_worker(&edge.state_work);CHECK(!edge.channels_lock);EXPECT(creates==(int)create&&removes==(int)remove);EXPECT(channels[0].registered==(remove?false:create?true:(bool)registered));
 }
 const int errors[]={-ENOMEM,-EIO,-EPROBE_DEFER};
 for(int error=0;error<3;error++) {
  reset();edge.no_suspend=true;edge.channels.count=1;channels[0]=(struct qcom_smd_channel){"rpm_requests",SMD_CHANNEL_CLOSED,SMD_CHANNEL_OPENED,false};fail_create=1;create_error=errors[error];
  qcom_channel_state_worker(&edge.state_work);EXPECT(!channels[0].registered&&creates==1&&!removes);fail_create=0;qcom_channel_state_worker(&edge.state_work);EXPECT(channels[0].registered&&creates==2&&!removes);
  channels[0].state=SMD_CHANNEL_OPENED;channels[0].remote_state=SMD_CHANNEL_CLOSED;qcom_channel_state_worker(&edge.state_work);EXPECT(!channels[0].registered&&removes==1&&channels[0].state==SMD_CHANNEL_CLOSED);
  channels[0].remote_state=SMD_CHANNEL_OPENED;qcom_channel_state_worker(&edge.state_work);EXPECT(channels[0].registered&&creates==3&&removes==1);
 }
 reset();edge.channels.count=2;channels[0]=(struct qcom_smd_channel){"diag",SMD_CHANNEL_CLOSED,SMD_CHANNEL_OPENING,false};channels[1]=(struct qcom_smd_channel){"rpm_requests",SMD_CHANNEL_CLOSED,SMD_CHANNEL_CLOSED,false};fail_create=1;
 qcom_channel_state_worker(&edge.state_work);EXPECT(!channels[0].registered&&channels[1].registered&&creates==2);fail_create=0;qcom_channel_state_worker(&edge.state_work);EXPECT(channels[0].registered&&channels[1].registered&&creates==3);
 printf("{\"cases\":%d,\"checks\":%d,\"failures\":%d}\n",cases,checks,failures);return failures?1:0;
}
