// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
// Stream-fed GEMM: complete 32x32 outputs per array, K=32*job_k_blocks.
// Job is serial; input vectors come from a future DMA/SRAM loader.
module tiny_npu_gemm_stream #(parameter integer ARRAYS=10,LANES=ARRAYS*32)(
 input logic clk,reset,job_valid,output logic job_ready,
 input logic [15:0] job_k_blocks,input logic [31:0] job_id,
 input logic in_valid,output logic in_ready,
 input logic [ARRAYS*128-1:0] in_a,
 input logic [ARRAYS*256-1:0] in_b,in_scale_a,in_scale_b,
 input logic [ARRAYS-1:0] in_active,
 output logic out_valid,input logic out_ready,
 output logic [LANES*32-1:0] out_data,
 output logic [31:0] out_tile_id,output logic [4:0] out_chunk,output logic out_last
);
 logic active,core_ready,core_valid,core_out_ready,core_last;
 logic [15:0] blocks,input_block,output_block;
 logic [4:0] k_index,core_chunk;
 logic [31:0] id,core_id;
 logic [LANES*32-1:0] core_data;
 assign job_ready=!active;
 assign in_ready=active&&input_block<blocks&&core_ready;
 tiny_npu_mxfp4_matmul #(.ARRAYS(ARRAYS)) core(
  .clk(clk),.reset(reset),.in_valid(in_valid&&active&&input_block<blocks),.in_ready(core_ready),
  .in_a(in_a),.in_b(in_b),.in_scale_a(in_scale_a),.in_scale_b(in_scale_b),
  .in_active(in_active),.in_tile_id(id),.out_valid(core_valid),.out_ready(core_out_ready),
  .out_data(core_data),.out_tile_id(core_id),.out_chunk(core_chunk),.out_last(core_last));
 tiny_npu_k_accumulator #(.LANES(LANES)) accum(
  .clk(clk),.reset(reset),.in_valid(core_valid),.in_ready(core_out_ready),.in_data(core_data),
  .in_tile_id(core_id),.in_chunk(core_chunk),.in_first_k(output_block==0),.in_last_k(output_block==blocks-1'b1),
  .out_valid(out_valid),.out_ready(out_ready),.out_data(out_data),.out_tile_id(out_tile_id),.out_chunk(out_chunk),.out_last(out_last));
 always_ff @(posedge clk)begin
  if(reset)begin active<=0;blocks<=0;id<=0;input_block<=0;output_block<=0;k_index<=0;end
  else begin
   if(job_valid&&job_ready&&job_k_blocks!=0)begin
     active<=1;blocks<=job_k_blocks;id<=job_id;input_block<=0;output_block<=0;k_index<=0;
   end
   if(in_valid&&in_ready)begin
     if(k_index==31)begin k_index<=0;input_block<=input_block+1'b1;end
     else k_index<=k_index+1'b1;
   end
   if(core_valid&&core_out_ready&&core_last)output_block<=output_block+1'b1;
   if(out_valid&&out_ready&&out_last)active<=0;
  end
 end
endmodule
