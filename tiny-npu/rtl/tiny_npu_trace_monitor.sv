// SPDX-License-Identifier: Apache-2.0
`timescale 1ps/1ps
// Passive probes: never drives ready/valid. Counter logic is synthesizable;
// JSONL file writer is simulation-only. Bind actual Rocket/AXI signals later.
module tiny_npu_trace_monitor #(
 parameter integer HARTS=8,PORTS=2,ID_BITS=6,ADDR_BITS=40,AXI_BYTES=32,
 parameter integer CORE_PERIOD_PS=1000,MAC_PERIOD_PS=1000,AXI_PERIOD_PS=1600,
 parameter logic [HARTS-1:0] HART_PERF_AVAILABLE='0,HART_RESPONSE_AVAILABLE='0
)(
 input logic reset,mac_clk,axi_clk,input logic [HARTS-1:0] hart_clk,
 input logic workload_active,axi_active,input logic [HARTS-1:0] hart_active,
 input logic [HARTS-1:0] ctrl_valid,ctrl_ready,mem_valid,mem_ready,mem_resp_valid,mem_resp_ready,
 input logic [HARTS-1:0] ic_valid,ic_ready,ic_miss,dc_miss,retire_valid,
 input logic [31:0] hart_period_ps[HARTS],
 input logic [15:0] mem_source[HARTS],mem_resp_source[HARTS],
 input logic [2:0] mem_opcode[HARTS],mem_resp_opcode[HARTS],
 input logic [ADDR_BITS-1:0] mem_address[HARTS],
 input logic [7:0] hart_stall[HARTS],input logic [15:0] hart_mem_bytes[HARTS],
 input logic mac_valid,mac_ready,input logic [31:0] mac_useful_ops,input logic [7:0] mac_stall,
 input logic [PORTS-1:0] ar_valid,ar_ready,aw_valid,aw_ready,r_valid,r_ready,r_last,w_valid,w_ready,w_last,b_valid,b_ready,
 input logic [ID_BITS-1:0] ar_id[PORTS],aw_id[PORTS],r_id[PORTS],b_id[PORTS],
 input logic [7:0] ar_len[PORTS],aw_len[PORTS],
 input logic [ADDR_BITS-1:0] ar_addr[PORTS],aw_addr[PORTS],
 input logic [AXI_BYTES-1:0] w_strb[PORTS],
 output logic [63:0] mac_fire_count,mac_bubble_count,mac_cause_count[8],
 output logic [63:0] ctrl_fire_count[HARTS],mem_fire_count[HARTS],retire_count[HARTS],axi_fire_count[PORTS][5]
);
 always_ff @(posedge mac_clk)begin
  if(reset)begin mac_fire_count<=0;mac_bubble_count<=0;for(integer i=0;i<8;i++)mac_cause_count[i]<=0;end
  else if(workload_active)begin
   if(mac_valid&&mac_ready)mac_fire_count<=mac_fire_count+1;
   else begin mac_bubble_count<=mac_bubble_count+1;for(integer i=0;i<8;i++)if(mac_stall[i])mac_cause_count[i]<=mac_cause_count[i]+1;end
  end
 end
 for(genvar h=0;h<HARTS;h++)begin:g_hart
  logic [63:0] ctrl_counter,mem_counter,retired_counter;
  assign ctrl_fire_count[h]=ctrl_counter;assign mem_fire_count[h]=mem_counter;assign retire_count[h]=retired_counter;
  always_ff @(posedge hart_clk[h])begin
   if(reset)begin ctrl_counter<=0;mem_counter<=0;retired_counter<=0;end
   else begin
    if(ctrl_valid[h]&&ctrl_ready[h])ctrl_counter<=ctrl_counter+1;
    if(mem_valid[h]&&mem_ready[h])mem_counter<=mem_counter+1;
    if(retire_valid[h])retired_counter<=retired_counter+1;
   end
  end
 end
 always_ff @(posedge axi_clk)begin
  for(integer p=0;p<PORTS;p++)begin
   if(reset)for(integer c=0;c<5;c++)axi_fire_count[p][c]<=0;
   else begin
    if(ar_valid[p]&&ar_ready[p])axi_fire_count[p][0]<=axi_fire_count[p][0]+1;
    if(r_valid[p]&&r_ready[p])axi_fire_count[p][1]<=axi_fire_count[p][1]+1;
    if(aw_valid[p]&&aw_ready[p])axi_fire_count[p][2]<=axi_fire_count[p][2]+1;
    if(w_valid[p]&&w_ready[p])axi_fire_count[p][3]<=axi_fire_count[p][3]+1;
    if(b_valid[p]&&b_ready[p])axi_fire_count[p][4]<=axi_fire_count[p][4]+1;
   end
  end
 end
`ifndef SYNTHESIS
 integer fd,trace_mac_enable;string filename,source,config_sha,run_sha;
 longint unsigned trace_start_ps,trace_end_ps;logic [HARTS-1:0] trace_hart_mask;logic [PORTS-1:0] trace_axi_mask;
 initial begin
  trace_start_ps=0;trace_end_ps=0;trace_hart_mask='1;trace_axi_mask='1;trace_mac_enable=1;
  if($value$plusargs("TRACE_START_PS=%d",trace_start_ps))begin end
  if($value$plusargs("TRACE_END_PS=%d",trace_end_ps))begin end
  if($value$plusargs("TRACE_HART_MASK=%h",trace_hart_mask))begin end
  if($value$plusargs("TRACE_AXI_MASK=%h",trace_axi_mask))begin end
  if($value$plusargs("TRACE_MAC_ENABLE=%d",trace_mac_enable))begin end
  if(!$value$plusargs("TRACE_FILE=%s",filename))filename="rtl_trace.jsonl";
  if(!$value$plusargs("TRACE_SOURCE=%s",source))source="unbound_probes";
  if(!$value$plusargs("TRACE_CONFIG_SHA256=%s",config_sha))config_sha="unknown";
  if(!$value$plusargs("TRACE_RUN_SHA256=%s",run_sha))run_sha="unknown";
  fd=$fopen(filename,"w");if(fd==0)$fatal(1,"trace file open failed");
  $fwrite(fd,"{\"type\":\"meta\",\"schema_version\":1,\"configuration_sha256\":\"%s\",\"verification_run_sha256\":\"%s\",\"capture\":{\"start_ps\":%0d,\"end_ps\":%0d,\"hart_mask\":%0d,\"axi_mask\":%0d,\"mac_enable\":%0d},\"provenance\":{\"source\":\"%s\",\"warning\":\"probe hookup determines whether signals are actual DUT or stimulus\"}}\n",config_sha,run_sha,trace_start_ps,trace_end_ps,trace_hart_mask,trace_axi_mask,trace_mac_enable,source);
 end
 final $fclose(fd);
 for(genvar h=0;h<HARTS;h++)begin:g_trace_hart
  always @(posedge hart_clk[h])if(!reset&&$time>=trace_start_ps&&(trace_end_ps==0||$time<trace_end_ps)&&trace_hart_mask[h])begin
   $fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":%0d,\"channel\":\"rocket.h%0d.control\",\"valid\":%0d,\"ready\":%0d,\"active\":%0d,\"stall_mask\":%0d}\n",$time,hart_period_ps[h],h,ctrl_valid[h],ctrl_ready[h],hart_active[h],hart_stall[h]);
   $fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":%0d,\"channel\":\"rocket.h%0d.memory\",\"valid\":%0d,\"ready\":%0d,\"active\":%0d,\"bytes\":%0d,\"dcache_miss\":%0d,\"source_id\":%0d,\"opcode\":%0d,\"address\":%0d}\n",$time,hart_period_ps[h],h,mem_valid[h],mem_ready[h],hart_active[h],hart_mem_bytes[h],dc_miss[h],mem_source[h],mem_opcode[h],mem_address[h]);
   $fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":%0d,\"channel\":\"rocket.h%0d.memory_response\",\"valid\":%0d,\"ready\":%0d,\"active\":%0d,\"source_id\":%0d,\"opcode\":%0d}\n",$time,hart_period_ps[h],h,mem_resp_valid[h],mem_resp_ready[h],hart_active[h]&&HART_RESPONSE_AVAILABLE[h],mem_resp_source[h],mem_resp_opcode[h]);
   $fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":%0d,\"channel\":\"rocket.h%0d.icache\",\"valid\":%0d,\"ready\":%0d,\"active\":%0d,\"cache_miss\":%0d,\"stall_mask\":%0d}\n",$time,hart_period_ps[h],h,ic_valid[h],ic_ready[h],hart_active[h]&&HART_PERF_AVAILABLE[h],ic_miss[h],ic_miss[h]?64:0);
   $fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":%0d,\"channel\":\"rocket.h%0d.retire\",\"valid\":%0d,\"ready\":1,\"active\":%0d}\n",$time,hart_period_ps[h],h,retire_valid[h],hart_active[h]&&HART_PERF_AVAILABLE[h]);
  end
 end
 always @(posedge mac_clk)if(!reset&&$time>=trace_start_ps&&(trace_end_ps==0||$time<trace_end_ps)&&trace_mac_enable!=0)$fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":%0d,\"channel\":\"mac.issue\",\"valid\":%0d,\"ready\":%0d,\"active\":%0d,\"ops\":%0d,\"stall_mask\":%0d}\n",$time,MAC_PERIOD_PS,mac_valid,mac_ready,workload_active,mac_useful_ops,mac_stall);
 always @(posedge axi_clk)if(!reset&&$time>=trace_start_ps&&(trace_end_ps==0||$time<trace_end_ps))for(integer p=0;p<PORTS;p++)if(trace_axi_mask[p])begin
  $fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":%0d,\"channel\":\"axi.p%0d.AR\",\"valid\":%0d,\"ready\":%0d,\"active\":%0d,\"id\":%0d,\"beats\":%0d,\"address\":%0d,\"beat_bytes\":%0d}\n",$time,AXI_PERIOD_PS,p,ar_valid[p],ar_ready[p],axi_active,ar_id[p],integer'(ar_len[p])+1,ar_addr[p],AXI_BYTES);
  $fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":%0d,\"channel\":\"axi.p%0d.R\",\"valid\":%0d,\"ready\":%0d,\"active\":%0d,\"id\":%0d,\"last\":%0d,\"bytes\":%0d}\n",$time,AXI_PERIOD_PS,p,r_valid[p],r_ready[p],axi_active,r_id[p],r_last[p],AXI_BYTES);
  $fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":%0d,\"channel\":\"axi.p%0d.AW\",\"valid\":%0d,\"ready\":%0d,\"active\":%0d,\"id\":%0d,\"beats\":%0d,\"address\":%0d,\"beat_bytes\":%0d}\n",$time,AXI_PERIOD_PS,p,aw_valid[p],aw_ready[p],axi_active,aw_id[p],integer'(aw_len[p])+1,aw_addr[p],AXI_BYTES);
  $fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":%0d,\"channel\":\"axi.p%0d.W\",\"valid\":%0d,\"ready\":%0d,\"active\":%0d,\"last\":%0d,\"bytes\":%0d}\n",$time,AXI_PERIOD_PS,p,w_valid[p],w_ready[p],axi_active,w_last[p],$countones(w_strb[p]));
  $fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":%0d,\"channel\":\"axi.p%0d.B\",\"valid\":%0d,\"ready\":%0d,\"active\":%0d,\"id\":%0d}\n",$time,AXI_PERIOD_PS,p,b_valid[p],b_ready[p],axi_active,b_id[p]);
 end
`endif
endmodule
