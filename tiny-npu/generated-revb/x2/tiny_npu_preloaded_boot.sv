// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
// Metadata ingress and reset controller. A downstream TL/bank manager must carry
// write payloads with tags and report preload_idle only after physical completion.
// This module does not instantiate a ROM, CPU, AXI bridge or SRAM data fabric.
module tiny_npu_preloaded_boot #(
 parameter integer ADDR_BITS=24,HARTS=8,LATENCY=5,TAG_BITS=8,RELEASE_STAGES=2,ACK_STAGES=2,
 parameter logic [ADDR_BITS:0] TOTAL_BYTES=25'd10485760,
 parameter logic [ADDR_BITS:0] BOOT_BASE=25'h9c0000,CODE_LIMIT=25'h9e0000,
 parameter logic [63:0] RESET_VECTOR=64'h609c0000
)(
 input logic clk,hart_clk,fabric_reset,hold_harts,
 input logic req_valid,output logic req_ready,input logic [1:0] req_owner,
 input logic [7:0] req_hart,input logic [TAG_BITS-1:0] req_tag,input logic req_write,
 input logic [ADDR_BITS-1:0] req_addr,input logic [12:0] req_bytes,
 output logic out_valid,input logic out_ready,output logic out_allow,
 output logic [2:0] out_error,output logic [1:0] out_owner,
 output logic [7:0] out_hart,output logic [TAG_BITS-1:0] out_tag,
 output logic [12:0] out_bytes,output logic out_write,output logic [ADDR_BITS-1:0] out_addr,
 input logic image_verified,rw_initialized,preload_idle,commit_valid,
 output logic commit_ready,commit_error,boot_ready,preload_enable,harts_held_ack,
 output logic [HARTS-1:0] hart_reset,output logic [63:0] reset_vector
);
 logic guard_valid,guard_ready,ingress_enable;
 assign ingress_enable=(req_owner!=0)||preload_enable;
 assign guard_valid=req_valid&&ingress_enable;
 assign req_ready=guard_ready&&ingress_enable;
 tiny_npu_l0_boot_guard #(.ADDR_BITS(ADDR_BITS),.HARTS(HARTS),.LATENCY(LATENCY),.TAG_BITS(TAG_BITS),
 .TOTAL_BYTES(TOTAL_BYTES),.BOOT_BASE(BOOT_BASE),.CODE_LIMIT(CODE_LIMIT)) guard(
 .clk,.reset(fabric_reset),.req_valid(guard_valid),.req_ready(guard_ready),.req_owner,.req_hart,.req_tag,.req_write,.req_addr,.req_bytes,
 .out_valid,.out_ready,.out_allow,.out_error,.out_owner,.out_hart,.out_tag,.out_bytes,.out_write,.out_addr,
 .image_verified,.rw_initialized,.preload_idle,.commit_valid,.commit_ready,.commit_error,.boot_ready);
 tiny_npu_sram_boot_control #(.HARTS(HARTS),.RELEASE_STAGES(RELEASE_STAGES),.ACK_STAGES(ACK_STAGES),.RESET_VECTOR(RESET_VECTOR)) control(
 .fabric_clk(clk),.hart_clk,.fabric_reset,.hold_harts,.boot_ready,.hart_reset,.reset_vector,.preload_enable,.harts_held_ack);
endmodule
