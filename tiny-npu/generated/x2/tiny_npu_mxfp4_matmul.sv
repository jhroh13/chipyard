// SPDX-License-Identifier: Apache-2.0
// RTL milestone R1: independent 32x32x32 MXFP4 x OCP-MXINT8 tiles.
// 1 K-vector/clock; 32 accepted vectors/tile. Two snapshot slots decouple
// compute from 32 output chunks. No DMA, host cache access or FP32 K-block add.
`timescale 1ns/1ps
module tiny_npu_mxfp4_matmul #(
  parameter integer ARRAYS=10,
  parameter integer OUT_LANES=ARRAYS*32,
  parameter integer TOTAL_RESULTS=ARRAYS*1024,
  parameter integer CHUNKS=TOTAL_RESULTS/OUT_LANES
)(
  input logic clk, reset,
  input logic in_valid,
  output logic in_ready,
  input logic [ARRAYS*32*4-1:0] in_a,
  input logic [ARRAYS*32*8-1:0] in_b,
  input logic [ARRAYS*32*8-1:0] in_scale_a, in_scale_b,
  input logic [ARRAYS-1:0] in_active,
  input logic [31:0] in_tile_id,
  output logic out_valid,
  input logic out_ready,
  output logic [OUT_LANES*32-1:0] out_data,
  output logic [31:0] out_tile_id,
  output logic [$clog2(CHUNKS)-1:0] out_chunk,
  output logic out_last
);
  logic signed [31:0] accum [TOTAL_RESULTS];
  logic signed [31:0] partial [2][ARRAYS][32][32];
  logic [ARRAYS*32*8-1:0] scale_a [2], scale_b [2];
  logic [31:0] tile_id [2];
  logic [ARRAYS-1:0] active_mask;
  logic [ARRAYS-1:0] slot_active [2];
  logic [1:0] slot_valid;
  logic write_slot, read_slot;
  logic [4:0] k_index;
  logic [$clog2(CHUNKS)-1:0] chunk_index;
  logic signed [4:0] a_decoded [ARRAYS*32];

  function automatic logic signed [4:0] decode_fp4(input logic [3:0] code);
    logic signed [4:0] magnitude;
    begin
      case (code[2:0])
        0:magnitude=0; 1:magnitude=1; 2:magnitude=2; 3:magnitude=3;
        4:magnitude=4; 5:magnitude=6; 6:magnitude=8; 7:magnitude=12;
      endcase
      decode_fp4=code[3] ? -magnitude : magnitude;
    end
  endfunction
  for(genvar a=0;a<ARRAYS*32;a=a+1) begin:g_decode
    assign a_decoded[a]=decode_fp4(in_a[a*4+:4]);
  end
  assign in_ready=(k_index!=0) || !slot_valid[write_slot];
  assign out_valid=slot_valid[read_slot];
  assign out_tile_id=tile_id[read_slot];
  assign out_chunk=chunk_index;
  assign out_last=(int'(chunk_index)==CHUNKS-1);

  for(genvar lane=0;lane<OUT_LANES;lane=lane+1) begin:g_output
    localparam integer ARRAY_ID=lane/32, COL_ID=lane%32;
    logic signed [31:0] selected_partial;
    logic [7:0] selected_a_scale, selected_b_scale;
    logic [31:0] converted;
    assign selected_partial=partial[read_slot][ARRAY_ID][chunk_index][COL_ID];
    assign selected_a_scale=scale_a[read_slot][(ARRAY_ID*32+int'(chunk_index))*8+:8];
    assign selected_b_scale=scale_b[read_slot][(ARRAY_ID*32+COL_ID)*8+:8];
    tiny_npu_fp32_from_scaled_int convert(
      .value(selected_partial),.scale_a(selected_a_scale),
      .scale_b(selected_b_scale),.fp32(converted));
    assign out_data[lane*32+:32]=slot_active[read_slot][ARRAY_ID] ? converted : 32'b0;
  end

  always_ff @(posedge clk) begin
    if(reset) begin
      slot_valid<=0; write_slot<=0; read_slot<=0;
      k_index<=0; chunk_index<=0; active_mask<=0;
    end else begin
      if(out_valid && out_ready) begin
        if(out_last) begin
          slot_valid[read_slot]<=0; read_slot<=!read_slot; chunk_index<=0;
        end else chunk_index<=chunk_index+1'b1;
      end
      if(in_valid && in_ready) begin
        if(k_index==0) begin
          scale_a[write_slot]<=in_scale_a; scale_b[write_slot]<=in_scale_b;
          tile_id[write_slot]<=in_tile_id; active_mask<=in_active; slot_active[write_slot]<=in_active;
        end
        if(k_index==31) begin
          slot_valid[write_slot]<=1; write_slot<=!write_slot; k_index<=0;
        end else k_index<=k_index+1'b1;
      end
    end
  end
  for(genvar array_id=0;array_id<ARRAYS;array_id=array_id+1) begin:g_array
    for(genvar row=0;row<32;row=row+1) begin:g_row
      for(genvar col=0;col<32;col=col+1) begin:g_col
        localparam integer INDEX=array_id*1024+row*32+col;
        logic signed [12:0] product_value;
        logic signed [31:0] next_sum;
        assign product_value=a_decoded[array_id*32+row] * $signed(in_b[(array_id*32+col)*8+:8]);
        assign next_sum=(k_index==0 ? 32'sd0 : accum[INDEX]) + {{19{product_value[12]}},product_value};
        always_ff @(posedge clk) begin
          if(!reset && in_valid && in_ready) begin
            accum[INDEX]<=next_sum;
            if(k_index==31) partial[write_slot][array_id][row][col]<=active_mask[array_id] ? next_sum : 32'sd0;
          end
        end
      end
    end
  end
  initial begin
    if(ARRAYS<1 || OUT_LANES!=ARRAYS*32 || TOTAL_RESULTS%OUT_LANES!=0 || CHUNKS<2)
      $fatal(1,"Invalid matmul parameters");
  end
endmodule
