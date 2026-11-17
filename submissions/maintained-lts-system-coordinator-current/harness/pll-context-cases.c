// SPDX-License-Identifier: GPL-2.0-only
static struct pll_freq_tbl table[]={{384000000,20,0,1,0},{768000000,40,0,1,0},{1536000000,80,0,1,0},{1785600000,93,0,1,0},{0}};
static struct regmap map;
static struct clk_pll pll;
static void init(void) {
 delays=0;memset(&map,0,sizeof(map));memset(&pll,0,sizeof(pll));map.lock=true;
 pll.clkr.regmap=&map;pll.clkr.hw.name="synthetic-a7pll";pll.l_reg=4;pll.m_reg=8;pll.n_reg=12;pll.config_reg=0x14;pll.mode_reg=0;pll.status_reg=0x1c;pll.status_bit=16;pll.freq_tbl=table;
 pll.critical_rate=true;pll.suspend_valid=true;pll.suspend_config=0x12345678;pll.suspend_l=20;pll.suspend_m=0;pll.suspend_n=1;
 map.regs[0]=7;map.regs[1]=20;map.regs[2]=0;map.regs[3]=1;map.regs[5]=pll.suspend_config;map.regs[7]=BIT(16);
}
static int prepare(void) { int ret;catching=true;if (setjmp(fatal))ret=-EOWNERDEAD;else ret=clk_pll_sr2_ops.prepare(&pll.clkr.hw);catching=false;return ret; }
static int enable(void) { int ret;catching=true;if (setjmp(fatal))ret=-EOWNERDEAD;else ret=clk_pll_sr2_ops.enable(&pll.clkr.hw);catching=false;return ret; }
static int unprepare(void) { catching=true;if(setjmp(fatal)) {catching=false;return -EOWNERDEAD;}clk_pll_sr2_ops.disable(&pll.clkr.hw);clk_pll_sr2_ops.unprepare(&pll.clkr.hw);catching=false;return 0; }
static int set_rate(unsigned long rate) { int ret;catching=true;if(setjmp(fatal))ret=-EOWNERDEAD;else ret=clk_pll_sr2_ops.set_rate(&pll.clkr.hw,rate,19200000);catching=false;return ret; }
static void lost(unsigned int which) { map.regs[0]=0;map.regs[7]=0;if(which&1)map.regs[5]=0;if(which&2)map.regs[1]=0;if(which&4)map.regs[2]^=3;if(which&8)map.regs[3]=0; }
static void restored(void) { CHECK(map.regs[5]==pll.suspend_config);CHECK((map.regs[1]&0x3ff)==pll.suspend_l);CHECK((map.regs[2]&0x7ffff)==pll.suspend_m);CHECK((map.regs[3]&0x7ffff)==pll.suspend_n);CHECK(!map.unsafe_program); }
int main(void) {
 init();CHECK(!prepare()&&!map.writes);cases++;
 init();pll.suspend_valid=false;map.regs[0]|=PLL_VOTE_FSM_ENA;CHECK(!prepare()&&!map.reads&&!map.writes);cases++;
 init();map.regs[0]|=PLL_VOTE_FSM_ENA;CHECK(prepare()==-EOWNERDEAD);cases++;
 for(int bits=0;bits<16;bits++)for(int mode=0;mode<8;mode++) {
  init();CHECK(!unprepare()&&pll.suspend_armed);lost(bits);map.regs[0]=mode;
  CHECK(!prepare());CHECK(!(map.regs[0]&7)||!bits);CHECK(!pll.suspend_armed);restored();CHECK(!enable());CHECK(clk_pll_sr2_ops.recalc_rate(&pll.clkr.hw,19200000)==384000000);cases++;
 }
 for(int before=0;before<2;before++)for(int i=0;i<4;i++) {
  init();CHECK(!unprepare());lost(15);
  if(before)CHECK(!set_rate(table[i].freq));
  CHECK(!prepare());CHECK(!enable());
  if(!before)CHECK(!set_rate(table[i].freq));
  CHECK(pll.suspend_l==table[i].l&&pll.suspend_n==table[i].n&&pll.suspend_m==table[i].m);restored();CHECK(clk_pll_sr2_ops.recalc_rate(&pll.clkr.hw,19200000)==table[i].freq);cases++;
 }
 /* Every single API-level I/O fault either verifies a restored point or stops. */
 for(int type=0;type<5;type++)for(int n=1;n<=50;n++) {
  init();pll.suspend_armed=true;lost(15);map.regs[0]=7;
  if(type==0)map.drop_at=n;if(type==1)map.error_at=n;if(type==2){map.error_at=n;map.apply_error=true;}if(type==3)map.read_error_at=n;if(type==4)map.corrupt_read_at=n;
  int ret=prepare();CHECK(ret==0||ret==-EOWNERDEAD);CHECK(!map.unsafe_program);
  if(!ret) {restored();CHECK((map.regs[0]&7)==0);}
  cases++;
 }
 /* An off request that was dropped must not be followed by live PLL writes. */
 init();map.drop_at=1;CHECK(set_rate(1536000000)==-EOWNERDEAD);CHECK(!map.unsafe_program);cases++;
 init();pll.suspend_armed=false;map.regs[5]^=1;CHECK(prepare()==-EOWNERDEAD);CHECK(!map.writes);cases++;
 init();map.lock=false;map.regs[0]=0;map.regs[7]=0;CHECK(enable()==-EOWNERDEAD);CHECK(delays<=210);cases++;
 struct clk_rate_request req={.rate=500000000,.best_parent_rate=19200000};init();CHECK(!clk_pll_sr2_ops.determine_rate(&pll.clkr.hw,&req)&&req.rate==768000000);cases++;
 printf("{\"cases\":%d,\"checks\":%d,\"failures\":%d,\"caught_logical_fatals\":%d}\n",cases,checks,failures,panics);return failures?1:0;
}
