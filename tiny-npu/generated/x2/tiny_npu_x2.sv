// Generated profile x2; K=32 compute core only, no DMA integration.
`timescale 1ns/1ps
module tiny_npu_x2 (
 input logic clk, reset, in_valid, output logic in_ready,
 input logic [2559:0] in_a,
 input logic [5119:0] in_b, in_scale_a, in_scale_b,
 input logic [19:0] in_active,
 input logic [31:0] in_tile_id,
 output logic out_valid, input logic out_ready,
 output logic [20479:0] out_data,
 output logic [31:0] out_tile_id, output logic [4:0] out_chunk,
 output logic out_last
);
 tiny_npu_mxfp4_matmul #(.ARRAYS(20),.OUT_LANES(640)) core(.*);
endmodule
