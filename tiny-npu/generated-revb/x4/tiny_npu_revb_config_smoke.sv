`timescale 1ns/1ps
// Generated isolated SRAM configuration consumer. Not the full L0 fabric.
module tiny_npu_revb_config_smoke (
 input logic clk,reset,cmd_valid,cmd_write,rsp_ready,
 input logic [$clog2(tiny_npu_revb_config_pkg::L0_REGIONS_0_DEPTH)-1:0] cmd_addr,
 input logic [255:0] cmd_data,input logic [31:0] cmd_mask,
 output logic cmd_ready,rsp_valid,output logic [255:0] rsp_data
);
 import tiny_npu_revb_config_pkg::*;
 tiny_npu_sram_1rw_subbank #(.WIDTH(256),.DEPTH(int'(L0_REGIONS_0_DEPTH)),
   .READ_LATENCY(int'(PATH_LATENCIES_CYCLES_SRCA))) sram (.*);
endmodule
