// Generated profile x4; K=32 compute core only, no DMA integration.
`timescale 1ns/1ps
module tiny_npu_x4 (
 input logic clk, reset, in_valid, output logic in_ready,
 input logic [5119:0] in_a,
 input logic [10239:0] in_b, in_scale_a, in_scale_b,
 input logic [39:0] in_active,
 input logic [31:0] in_tile_id,
 output logic out_valid, input logic out_ready,
 output logic [40959:0] out_data,
 output logic [31:0] out_tile_id, output logic [4:0] out_chunk,
 output logic out_last
);
 tiny_npu_mxfp4_matmul #(.ARRAYS(40),.OUT_LANES(1280)) core(.*);
endmodule
