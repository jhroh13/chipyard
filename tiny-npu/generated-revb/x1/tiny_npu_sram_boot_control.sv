// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
// S0SRAM is the reserved boot/control region of L0SRAM, not a second memory.
// Separate fabric/SRAM reset from Rocket reset. Host preloads SRAM with harts
// held in reset, commits and seals the image, then drops hold_harts.
module tiny_npu_sram_boot_control #(
 parameter integer HARTS=8,RELEASE_STAGES=2,ACK_STAGES=2,
 parameter logic [63:0] RESET_VECTOR=64'h609c0000
)(
 input logic fabric_clk,hart_clk,fabric_reset,hold_harts,boot_ready,
 output logic [HARTS-1:0] hart_reset,
 output logic [63:0] reset_vector,
 output logic preload_enable,harts_held_ack
);
 (* async_reg="true" *) logic [RELEASE_STAGES-1:0] release_pipe;
 (* async_reg="true" *) logic [ACK_STAGES-1:0] held_pipe;
 logic async_hold;
 assign async_hold=fabric_reset||hold_harts||!boot_ready;
 // Asynchronous assertion and synchronous deassertion in the hart clock domain.
 always_ff @(posedge hart_clk or posedge async_hold)
  if(async_hold)release_pipe<='0;
  else release_pipe<={release_pipe[RELEASE_STAGES-2:0],1'b1};
 assign hart_reset={HARTS{!release_pipe[RELEASE_STAGES-1]}};
 // Require observed reset assertion before accepting external preload writes.
 always_ff @(posedge fabric_clk)
  if(fabric_reset)held_pipe<='0;
  else held_pipe<={held_pipe[ACK_STAGES-2:0],(&hart_reset)};
 assign harts_held_ack=held_pipe[ACK_STAGES-1];
 assign preload_enable=!fabric_reset&&!boot_ready&&harts_held_ack;
 assign reset_vector=RESET_VECTOR;
 initial if(HARTS<1||RELEASE_STAGES<2||ACK_STAGES<2)$fatal(1,"Invalid boot reset parameters");
endmodule
