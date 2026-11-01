`timescale 1ps/1ps
module tb_bubble_trace;
 parameter integer LATENCY=16;
 logic clk=0,axi_clk=0,reset=1,active=0;always #500 clk=~clk;always #800 axi_clk=~axi_clk;
 logic [7:0] hart_clk,ctrl_valid,ctrl_ready,mem_valid,mem_ready,ic_valid,ic_ready,ic_miss,dc_miss,retire_valid;
 assign hart_clk={8{clk}};logic [7:0] hart_active;assign hart_active={4'b0,{4{active}}};
 logic [7:0] mem_resp_valid,mem_resp_ready;logic [15:0] mem_source[8],mem_resp_source[8];logic [2:0] mem_opcode[8],mem_resp_opcode[8];logic [39:0] mem_address[8];
 logic [31:0] hart_period_ps[8];logic [7:0] hart_stall[8];logic [15:0] hart_mem_bytes[8];
 logic mac_valid,mac_ready;logic [7:0] mac_stall;logic [31:0] mac_useful_ops;
 logic [1:0] ar_valid,ar_ready,aw_valid,aw_ready,r_valid,r_ready,r_last,w_valid,w_ready,w_last,b_valid,b_ready;
 logic [7:0] ar_len[2],aw_len[2];logic [39:0] ar_addr[2],aw_addr[2];logic [31:0] w_strb[2];
 logic [5:0] ar_id[2],aw_id[2],r_id[2],b_id[2];
 logic [63:0] mac_fire_count,mac_bubble_count,mac_cause_count[8],ctrl_fire_count[8],mem_fire_count[8],retire_count[8],axi_fire_count[2][5];
 logic [3:0] req_valid,req_write;logic [1:0] req_bank[4];logic [3:0] req_addr[4];logic [31:0] req_data[4];
 logic [3:0] cmd_valid,cmd_ready,cmd_write,rsp_valid,rsp_ready,fire_src;
 logic [3:0] cmd_addr[4];logic [31:0] cmd_data[4],rsp_data[4];integer owner[4];
 logic [31:0] expected_mem[4][16],expected_q[4][2048];logic initialized[4][16];integer head[4],tail[4];
 logic [3:0] sampled_cmd,sampled_rsp,sampled_write;logic [3:0] sampled_addr[4];logic [31:0] sampled_data[4],sampled_rsp_data[4];
 integer cycle=0,read_checks=0,write_checks=0,seed=27011;logic pause_oic;
 function automatic integer rnd();seed=integer'((32'(seed)*32'd1664525+32'd1013904223)&32'h7fffffff);return seed;endfunction
 for(genvar b=0;b<4;b++)begin:g_bank
  tiny_npu_sram_1rw_subbank #(.WIDTH(32),.DEPTH(16),.READ_LATENCY(LATENCY+b*3)) bank(
   .clk,.reset,.cmd_valid(cmd_valid[b]),.cmd_ready(cmd_ready[b]),.cmd_write(cmd_write[b]),.cmd_addr(cmd_addr[b]),.cmd_data(cmd_data[b]),.cmd_mask(4'hf),.rsp_valid(rsp_valid[b]),.rsp_ready(rsp_ready[b]),.rsp_data(rsp_data[b]));
 end
 always_comb begin
  ctrl_valid={4'b0,req_valid};ctrl_ready=0;mem_valid={4'b0,req_valid};mem_ready=0;
  mem_resp_valid=0;mem_resp_ready=0;ic_valid=0;ic_miss=0;dc_miss=0;ic_ready=0;retire_valid=0;
  for(integer h=0;h<8;h++)begin mem_source[h]=16'(h);mem_resp_source[h]=0;mem_opcode[h]=0;mem_resp_opcode[h]=0;mem_address[h]=0;hart_period_ps[h]=1000;hart_stall[h]=0;hart_mem_bytes[h]=4;
   if(h<4)begin mem_address[h]=40'(integer'(req_bank[h])*64+integer'(req_addr[h])*4);mem_opcode[h]=req_write[h]?3'd0:3'd4;end
  end
  for(integer b=0;b<4;b++)begin
   owner[b]=-1;cmd_valid[b]=0;cmd_write[b]=0;cmd_addr[b]=0;cmd_data[b]=0;
   for(integer h=0;h<4;h++)if(req_valid[h]&&integer'(req_bank[h])==b)begin
    if(pause_oic)hart_stall[h]=8;
    else if(owner[b]>=0)hart_stall[h]=4;
    else if(!req_write[h]&&tail[b]-head[b]>=4)hart_stall[h]=2;
    else begin owner[b]=h;cmd_valid[b]=1;cmd_write[b]=req_write[h];cmd_addr[b]=req_addr[h];cmd_data[b]=req_data[h];ctrl_ready[h]=cmd_ready[b];mem_ready[h]=cmd_ready[b];if(!cmd_ready[b])hart_stall[h]=16;end
   end
  end
  // Synthetic MAC readiness combines real read responses; ops=0 avoids claiming arithmetic work.
  mac_valid=|rsp_valid;mac_ready=|(rsp_valid&rsp_ready);mac_useful_ops=0;mac_stall=0;
  if(!mac_valid)mac_stall=1;
  for(integer h=0;h<4;h++)mac_stall=mac_stall|hart_stall[h];
 end
 tiny_npu_trace_monitor mon(.reset,.mac_clk(clk),.axi_clk,.hart_clk,.workload_active(active),.axi_active(1'b0),.*);
 always @(posedge clk)if(!reset)begin
  for(integer h=0;h<4;h++)fire_src[h]=ctrl_valid[h]&&ctrl_ready[h];
  for(integer b=0;b<4;b++)begin
   sampled_cmd[b]=cmd_valid[b]&&cmd_ready[b];sampled_rsp[b]=rsp_valid[b]&&rsp_ready[b];sampled_write[b]=cmd_write[b];sampled_addr[b]=cmd_addr[b];sampled_data[b]=cmd_data[b];sampled_rsp_data[b]=rsp_data[b];
  end
  #1;
  for(integer b=0;b<4;b++)begin
   if(sampled_rsp[b])begin
    if(head[b]>=tail[b]||sampled_rsp_data[b]!==expected_q[b][head[b]])$fatal(1,"response mismatch bank=%0d head=%0d",b,head[b]);
    head[b]++;read_checks++;
   end
   if(sampled_cmd[b])begin
    if(sampled_write[b])begin expected_mem[b][sampled_addr[b]]=sampled_data[b];initialized[b][sampled_addr[b]]=1;write_checks++;end
    else begin
     if(!initialized[b][sampled_addr[b]])$fatal(1,"uninitialized read");
     expected_q[b][tail[b]]=expected_mem[b][sampled_addr[b]];tail[b]++;
    end
   end
  end
 end
 initial begin
  $dumpfile("bubble.vcd");$dumpvars(0,tb_bubble_trace);
  req_valid=0;fire_src=0;rsp_ready='1;pause_oic=0;
  ar_valid=0;ar_ready=0;aw_valid=0;aw_ready=0;r_valid=0;r_ready=0;r_last=0;w_valid=0;w_ready=0;w_last=0;b_valid=0;b_ready=0;
  for(integer p=0;p<2;p++)begin ar_len[p]=0;aw_len[p]=0;ar_addr[p]=0;aw_addr[p]=0;w_strb[p]=0;ar_id[p]=0;aw_id[p]=0;r_id[p]=0;b_id[p]=0;end
  for(integer b=0;b<4;b++)begin head[b]=0;tail[b]=0;for(integer a=0;a<16;a++)initialized[b][a]=0;end
  repeat(4)@(negedge clk);reset=0;active=1;
  for(cycle=0;cycle<1200;cycle++)begin
   @(negedge clk);pause_oic=(rnd()%7)==0;
   for(integer b=0;b<4;b++)rsp_ready[b]=(rnd()%5)!=0;
   for(integer h=0;h<4;h++)if(!req_valid[h]||fire_src[h])begin
    req_valid[h]=(rnd()%5)!=0;req_bank[h]=2'(rnd()%4);req_addr[h]=4'(rnd()%16);req_data[h]=32'(rnd());
    req_write[h]=!initialized[req_bank[h]][req_addr[h]]||(rnd()%3)==0;
   end
  end
  @(negedge clk);req_valid=0;pause_oic=0;rsp_ready='1;
  repeat(LATENCY+32)@(negedge clk);
  for(integer b=0;b<4;b++)if(head[b]!=tail[b])$fatal(1,"lost response bank=%0d",b);
  if(read_checks<10||write_checks<10||mac_cause_count[0]==0||mac_cause_count[1]==0||mac_cause_count[2]==0||mac_cause_count[3]==0)$fatal(1,"missing scenario coverage");
  active=0;$display("BUBBLE_TRACE_PASS latency=%0d reads=%0d writes=%0d wait=%0d credit=%0d bank=%0d oic=%0d",LATENCY,read_checks,write_checks,mac_cause_count[0],mac_cause_count[1],mac_cause_count[2],mac_cause_count[3]);$finish;
 end
endmodule
