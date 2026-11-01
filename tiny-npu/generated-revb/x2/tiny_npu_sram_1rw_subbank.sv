// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
// Exactly one memory command (read OR write) per accepted clock.
// Multi-cycle elastic response pipeline models transport to/from the subbank.
// This is a single-subbank primitive, not the complete L0 arbitration fabric.
module tiny_npu_sram_1rw_subbank #(
 parameter integer WIDTH=256,DEPTH=1024,READ_LATENCY=16,ADDR_BITS=$clog2(DEPTH)
)(
 input logic clk,reset,cmd_valid,output logic cmd_ready,
 input logic cmd_write,input logic [ADDR_BITS-1:0] cmd_addr,
 input logic [WIDTH-1:0] cmd_data,input logic [WIDTH/8-1:0] cmd_mask,
 output logic rsp_valid,input logic rsp_ready,output logic [WIDTH-1:0] rsp_data
);
 logic [WIDTH-1:0] mem[DEPTH],data_pipe[READ_LATENCY];
 logic [READ_LATENCY-1:0] valid_pipe;
 logic advance;
 assign advance=!valid_pipe[READ_LATENCY-1]||rsp_ready;
 assign cmd_ready=advance&&!reset;
 assign rsp_valid=valid_pipe[READ_LATENCY-1];assign rsp_data=data_pipe[READ_LATENCY-1];
 always_ff @(posedge clk)begin
  if(reset)valid_pipe<=0;
  else if(advance)begin
   valid_pipe[0]<=cmd_valid&&!cmd_write;
   if(cmd_valid)begin
    if(cmd_write)begin
     for(integer b=0;b<WIDTH/8;b=b+1)if(cmd_mask[b])mem[cmd_addr][b*8+:8]<=cmd_data[b*8+:8];
    end else data_pipe[0]<=mem[cmd_addr];
   end
   for(integer i=1;i<READ_LATENCY;i=i+1)valid_pipe[i]<=valid_pipe[i-1];
  end
 end
 // Elaborate transport stages explicitly so long (>64-cycle) paths are portable
 // across simulators that limit nonblocking assignments to arrays in procedural loops.
 for(genvar stage=1;stage<READ_LATENCY;stage=stage+1)begin: g_transport
  always_ff @(posedge clk)if(!reset&&advance)data_pipe[stage]<=data_pipe[stage-1];
 end
 initial if(READ_LATENCY<1||WIDTH%8!=0)$fatal(1,"Invalid single-port subbank parameters");
endmodule
