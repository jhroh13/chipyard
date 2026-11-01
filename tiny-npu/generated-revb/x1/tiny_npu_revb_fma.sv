`timescale 1ns/1ps
// Native LQ16 primitive only: MX decode/array/TF32 store are not connected.
module tiny_npu_revb_fma(
 input logic clk,reset,in_valid,output logic in_ready,
 input logic [15:0] a,b,c,output logic out_valid,input logic out_ready,
 output logic [15:0] result
);
 tiny_npu_lq16_fma_pipe #(.LATENCY(int'(tiny_npu_revb_config_pkg::MAC_FMA_PIPE_CYCLES))) fma(.*);
endmodule
