`timescale 1ns/1ps
module tiny_npu_revb_preloaded_boot(
 input logic clk,hart_clk,fabric_reset,hold_harts,req_valid,output logic req_ready,input logic [1:0] req_owner,
 input logic [7:0] req_hart,input logic [7:0] req_tag,input logic req_write,
 input logic [int'(tiny_npu_revb_config_pkg::L0_ADDRESS_BITS)-1:0] req_addr,
 input logic [12:0] req_bytes,output logic out_valid,input logic out_ready,
 output logic out_allow,output logic [2:0] out_error,output logic [1:0] out_owner,
 output logic [7:0] out_hart,output logic [7:0] out_tag,output logic [12:0] out_bytes,output logic out_write,
 output logic [int'(tiny_npu_revb_config_pkg::L0_ADDRESS_BITS)-1:0] out_addr,
 input logic image_verified,rw_initialized,preload_idle,commit_valid,
 output logic commit_ready,commit_error,boot_ready,preload_enable,harts_held_ack,
 output logic [int'(tiny_npu_revb_config_pkg::ROCKET_CORES)-1:0] hart_reset,output logic [63:0] reset_vector
);
 import tiny_npu_revb_config_pkg::*;
 tiny_npu_preloaded_boot #(.ADDR_BITS(int'(L0_ADDRESS_BITS)),.HARTS(int'(ROCKET_CORES)),
 .LATENCY(int'(L0_BOOT_GUARD_CYCLES)),.TOTAL_BYTES((int'(L0_ADDRESS_BITS)+1)'(L0_BYTES)),
 .BOOT_BASE((int'(L0_ADDRESS_BITS)+1)'(L0_BOOT_OFFSET)),
 .CODE_LIMIT((int'(L0_ADDRESS_BITS)+1)'(L0_BOOT_OFFSET+L0_BOOT_CODE_BYTES)),.RELEASE_STAGES(int'(L0_BOOT_HART_RELEASE_CDC_CYCLES)),.ACK_STAGES(int'(BOOT_RESET_ACK_CYCLES)),.RESET_VECTOR(ROCKET_RESET_VECTOR)) boot(.*);
endmodule
