// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
// Request planning only: plan_done is NOT DMA completion or AXI B completion.
module tiny_npu_dma_burst_planner #(
 parameter integer ADDR_BITS=40, DATA_BYTES=64, MAX_BURST_BYTES=4096
)(
 input logic clk,reset,cmd_valid,output logic cmd_ready,
 input logic [ADDR_BITS-1:0] cmd_addr,input logic [31:0] cmd_bytes,
 output logic req_valid,input logic req_ready,
 output logic [ADDR_BITS-1:0] req_addr,
 output logic [12:0] req_bytes,output logic [8:0] req_beats,
 output logic req_last,output logic plan_done,cmd_error
);
 logic busy;logic [ADDR_BITS-1:0] addr;logic [31:0] remaining,length_bytes,boundary;
 assign cmd_ready=!busy;assign req_valid=busy;assign req_addr=addr;
 always_comb begin
  boundary=4096-{20'b0,addr[11:0]};length_bytes=remaining;
  if(length_bytes>MAX_BURST_BYTES)length_bytes=MAX_BURST_BYTES;
  if(length_bytes>boundary)length_bytes=boundary;
 end
 assign req_bytes=13'(length_bytes);
 assign req_beats=9'((length_bytes+DATA_BYTES-1)/DATA_BYTES);
 assign req_last=remaining==length_bytes;
 always_ff @(posedge clk)begin
  if(reset)begin busy<=0;remaining<=0;addr<=0;plan_done<=0;cmd_error<=0;end
  else begin
   plan_done<=0;cmd_error<=0;
   if(cmd_valid&&cmd_ready)begin
    if((cmd_addr%ADDR_BITS'(DATA_BYTES))!=0)begin plan_done<=1;cmd_error<=1;end
    else if(cmd_bytes==0)plan_done<=1;
    else begin busy<=1;remaining<=cmd_bytes;addr<=cmd_addr;end
   end
   if(req_valid&&req_ready)begin
    addr<=addr+ADDR_BITS'(length_bytes);remaining<=remaining-length_bytes;
    if(req_last)begin busy<=0;plan_done<=1;end
   end
  end
 end
 initial if(MAX_BURST_BYTES>4096 || MAX_BURST_BYTES>256*DATA_BYTES || MAX_BURST_BYTES%DATA_BYTES!=0)
  $fatal(1,"Invalid DMA burst parameters");
endmodule
