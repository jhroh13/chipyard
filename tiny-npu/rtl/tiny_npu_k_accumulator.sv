// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
// R2/R3 slice: 32 row-contexts, one synchronous 1R1W C bank per result lane.
// Sequential K-blocks for a single tile-group. Scoreboard prevents stale RMW.
module tiny_npu_k_accumulator #(parameter integer LANES=32)(
 input logic clk,reset,in_valid,output logic in_ready,
 input logic [LANES*32-1:0] in_data,
 input logic [31:0] in_tile_id,input logic [4:0] in_chunk,
 input logic in_first_k,in_last_k,
 output logic out_valid,input logic out_ready,
 output logic [LANES*32-1:0] out_data,
 output logic [31:0] out_tile_id,output logic [4:0] out_chunk,output logic out_last
);
 logic stage_valid,stage_first;
 logic [LANES*32-1:0] stage_data;
 logic [37:0] stage_tag;
 logic [31:0] busy_rows;
 logic [LANES-1:0] add_ready,add_valid;
 logic [37:0] add_tag[LANES];
 logic [31:0] add_data[LANES],c_data[LANES];
 logic stage_ready,add_output_ready,writeback;
 assign stage_ready=!stage_valid||add_ready[0];
 assign in_ready=stage_ready&&!busy_rows[in_chunk];
 assign out_valid=add_valid[0]&&add_tag[0][37];
 assign out_tile_id=add_tag[0][36:5];assign out_chunk=add_tag[0][4:0];
 assign out_last=out_chunk==31;
 assign add_output_ready=!add_tag[0][37]||out_ready;
 assign writeback=add_valid[0]&&add_output_ready;
 for(genvar lane=0;lane<LANES;lane=lane+1)begin:g_lane
   tiny_npu_sram_bank #(.WIDTH(32),.DEPTH(32)) c_bank(
     .clk(clk),.rd_en(in_valid&&in_ready),.rd_addr(in_chunk),.rd_data(c_data[lane]),
     .wr_en(writeback),.wr_addr(add_tag[0][4:0]),.wr_data(add_data[lane]),.wr_mask(4'hf));
   tiny_npu_fp32_add_pipe adder(
     .clk(clk),.reset(reset),.in_valid(stage_valid),.in_ready(add_ready[lane]),
     .in_a(stage_first ? 32'b0 : c_data[lane]),.in_b(stage_data[lane*32+:32]),.in_tag(stage_tag),
     .out_valid(add_valid[lane]),.out_ready(add_output_ready),.out_sum(add_data[lane]),.out_tag(add_tag[lane]));
   assign out_data[lane*32+:32]=add_data[lane];
 end
 always_ff @(posedge clk)begin
   if(reset)begin stage_valid<=0;busy_rows<=0;end
   else begin
     if(stage_ready)begin
       stage_valid<=in_valid&&in_ready;
       if(in_valid&&in_ready)begin
         stage_data<=in_data;stage_first<=in_first_k;stage_tag<={in_last_k,in_tile_id,in_chunk};
       end
     end
     if(writeback)busy_rows[add_tag[0][4:0]]<=0;
     if(in_valid&&in_ready)busy_rows[in_chunk]<=1;
   end
 end
endmodule
