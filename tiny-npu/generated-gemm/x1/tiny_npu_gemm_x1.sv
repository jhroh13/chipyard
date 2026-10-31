// Generated R2 stream-GEMM; no AXI DMA or RoCC wrapper.
`timescale 1ns/1ps
module tiny_npu_gemm_x1(
 input logic clk,reset,job_valid, output logic job_ready,
 input logic [15:0] job_k_blocks,input logic [31:0] job_id,
 input logic in_valid,output logic in_ready,
 input logic [1279:0] in_a,
 input logic [2559:0] in_b,in_scale_a,in_scale_b,
 input logic [9:0] in_active,
 output logic out_valid,input logic out_ready,
 output logic [10239:0] out_data,
 output logic [31:0] out_tile_id,output logic [4:0] out_chunk,output logic out_last
);
 tiny_npu_gemm_stream #(.ARRAYS(10)) core(.*);
endmodule
