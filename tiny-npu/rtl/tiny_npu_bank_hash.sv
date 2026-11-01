// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
// Four real elastic stages. Input is a region-relative LINEAR bank/row tuple;
// address division, bounds and region decoding are upstream responsibilities.
// For any BANKS, b'=(b+g(row)) mod BANKS, row unchanged: invertible permutation.
module tiny_npu_bank_hash #(
 parameter integer BANKS=8,ROW_BITS=10,PAYLOAD_BITS=300,
 parameter integer BANK_BITS=(BANKS>1?$clog2(BANKS):1)
)(
 input logic clk,reset,cfg_enable,input logic [4:0] cfg_shift,
 input logic in_valid,output logic in_ready,input logic [BANK_BITS-1:0] in_bank,
 input logic [ROW_BITS-1:0] in_row,input logic [PAYLOAD_BITS-1:0] in_payload,
 output logic out_valid,input logic out_ready,output logic [BANK_BITS-1:0] out_bank,
 output logic [ROW_BITS-1:0] out_row,output logic [PAYLOAD_BITS-1:0] out_payload,
 output logic idle
);
 localparam integer PACK_BITS=ROW_BITS+PAYLOAD_BITS;
 logic [3:0] valid_pipe;logic advance;
 logic [PACK_BITS-1:0] payload[4];
 logic [BANK_BITS-1:0] b1,b2,g1,g2;
 logic [BANK_BITS:0] sum3;
 assign advance=!valid_pipe[3]||out_ready;
 assign in_ready=advance&&!reset;assign idle=!(|valid_pipe);
 assign out_valid=valid_pipe[3];assign {out_row,out_payload}=payload[3];
 always_ff @(posedge clk)begin
  if(reset)valid_pipe<='0;
  else if(advance)begin
   valid_pipe<={valid_pipe[2:0],in_valid&&in_ready};
   if(in_valid&&in_ready)begin
    payload[0]<={in_row,in_payload};b1<=in_bank;
    g1<=cfg_enable?BANK_BITS'(in_row>>cfg_shift):'0;
   end
   if(valid_pipe[0])begin
    payload[1]<=payload[0];b2<=b1;
    g2<=(integer'(g1)>=BANKS)?g1-BANK_BITS'(BANKS):g1;
   end
   if(valid_pipe[1])begin payload[2]<=payload[1];sum3<={1'b0,b2}+{1'b0,g2};end
   if(valid_pipe[2])begin
    payload[3]<=payload[2];out_bank<=(integer'(sum3)>=BANKS)?BANK_BITS'(sum3-(BANK_BITS+1)'(BANKS)):BANK_BITS'(sum3);
   end
  end
 end
 initial if(BANKS<1||ROW_BITS<1||ROW_BITS>32)$fatal(1,"Invalid bank hash geometry");
endmodule
