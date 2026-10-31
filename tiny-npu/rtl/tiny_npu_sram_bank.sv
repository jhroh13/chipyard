// SPDX-License-Identifier: Apache-2.0
// 1R1W SRAM inference template. Same-address R/W is write-first by contract.
// Replace with foundry macro wrapper for PPA; storage is not reset.
`timescale 1ns/1ps
module tiny_npu_sram_bank #(
  parameter integer WIDTH=256, DEPTH=2048, ADDR_BITS=$clog2(DEPTH)
)(
  input logic clk,
  input logic rd_en,
  input logic [ADDR_BITS-1:0] rd_addr,
  output logic [WIDTH-1:0] rd_data,
  input logic wr_en,
  input logic [ADDR_BITS-1:0] wr_addr,
  input logic [WIDTH-1:0] wr_data,
  input logic [WIDTH/8-1:0] wr_mask
);
  logic [WIDTH-1:0] mem [DEPTH];
  always_ff @(posedge clk) begin
    for(integer b=0;b<WIDTH/8;b=b+1) begin
      if(wr_en && wr_mask[b]) mem[wr_addr][b*8+:8]<=wr_data[b*8+:8];
      if(rd_en) rd_data[b*8+:8] <= (wr_en && wr_addr==rd_addr && wr_mask[b]) ? wr_data[b*8+:8] : mem[rd_addr][b*8+:8];
    end
  end
endmodule
