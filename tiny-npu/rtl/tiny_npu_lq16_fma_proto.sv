// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
// Exact S1/E7/M8 fused multiply-add reference RTL, RNE, gradual underflow.
// Arithmetic is combinational before LATENCY transport registers: LATENCY=4
// is NOT evidence of a timing-balanced 4-stage FMA or 1GHz feasibility.
module tiny_npu_lq16_fma_proto #(parameter integer LATENCY=4)(
 input logic clk,reset,in_valid,output logic in_ready,
 input logic [15:0] a,b,c,output logic out_valid,input logic out_ready,
 output logic [15:0] result
);
 logic [15:0] rounded;
 logic [8:0] ma,mb,mc;logic [17:0] product;
 logic [271:0] pmag,cmag,magnitude;
 logic signed [272:0] psigned,csigned,total;
 logic sign_product,sign_result,guard_bit,sticky;
 logic [9:0] quotient;
 integer qa,qb,qc,leading,rshift,rexp;
 always_comb begin
  ma={(|a[14:8]),a[7:0]};mb={(|b[14:8]),b[7:0]};mc={(|c[14:8]),c[7:0]};
  qa=(a[14:8]==0)?-70:integer'(a[14:8])-71;
  qb=(b[14:8]==0)?-70:integer'(b[14:8])-71;
  qc=(c[14:8]==0)?-70:integer'(c[14:8])-71;
  product=ma*mb;sign_product=a[15]^b[15];
  pmag={{254{1'b0}},product}<<(qa+qb+140);
  cmag={{263{1'b0}},mc}<<(qc+140);
  psigned=$signed({1'b0,pmag});if(sign_product)psigned=-psigned;
  csigned=$signed({1'b0,cmag});if(c[15])csigned=-csigned;
  total=psigned+csigned;sign_result=total[272];
  magnitude=sign_result?272'(-total):272'(total);
  leading=-1;for(integer i=0;i<272;i++)if(magnitude[i])leading=i;
  rshift=leading>=78?leading-8:70;
  quotient=10'(magnitude>>rshift);guard_bit=magnitude[rshift-1];sticky=0;
  for(integer i=0;i<272;i++)if(i<rshift-1)sticky=sticky|magnitude[i];
  if(guard_bit&&(sticky||quotient[0]))quotient=quotient+10'd1;
  if(leading>=78&&quotient[9])begin quotient=quotient>>1;leading=leading+1;end
  rexp=leading-77;
  if(magnitude==0)rounded=0;
  else if(leading<78)rounded={sign_result,6'b0,quotient[8:0]};
  else if(rexp>=127)rounded={sign_result,7'h7f,8'b0};
  else rounded={sign_result,7'(rexp),quotient[7:0]};
  if((a[14:8]==127&&a[7:0]!=0)||(b[14:8]==127&&b[7:0]!=0)||(c[14:8]==127&&c[7:0]!=0))rounded=16'h7f80;
  else if((a[14:8]==127&&b[14:0]==0)||(b[14:8]==127&&a[14:0]==0))rounded=16'h7f80;
  else if(a[14:8]==127||b[14:8]==127)begin
   if(c[14:8]==127&&c[15]!=sign_product)rounded=16'h7f80;
   else rounded={sign_product,7'h7f,8'b0};
  end else if(c[14:8]==127)rounded={c[15],7'h7f,8'b0};
 end
 logic [LATENCY-1:0] valid_pipe;logic [15:0] data_pipe[LATENCY];logic advance;
 assign advance=!valid_pipe[LATENCY-1]||out_ready;
 assign in_ready=advance&&!reset;assign out_valid=valid_pipe[LATENCY-1];assign result=data_pipe[LATENCY-1];
 always_ff @(posedge clk)begin
  if(reset)valid_pipe<=0;
  else if(advance)begin valid_pipe[0]<=in_valid;data_pipe[0]<=rounded;for(integer i=1;i<LATENCY;i++)valid_pipe[i]<=valid_pipe[i-1];end
 end
 for(genvar i=1;i<LATENCY;i++)begin:g_transport
  always_ff @(posedge clk)if(!reset&&advance)data_pipe[i]<=data_pipe[i-1];
 end
 initial if(LATENCY<1)$fatal(1,"LATENCY must be positive");
endmodule
