// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
// Four arithmetic stages: unpack/align, add/sub, normalize, round/pack.
// RNE, gradual underflow, canonical qNaN; no IEEE exception flags.
// Global elastic enable holds all pipeline registers when output is blocked.
module tiny_npu_fp32_add_pipe #(parameter integer TAG_BITS=38)(
 input logic clk,reset,in_valid, output logic in_ready,
 input logic [31:0] in_a,in_b, input logic [TAG_BITS-1:0] in_tag,
 output logic out_valid,input logic out_ready,
 output logic [31:0] out_sum,output logic [TAG_BITS-1:0] out_tag
);
 logic [3:0] valid;
 logic advance;
 logic [TAG_BITS-1:0] tags[4];
 logic special0,special1,special2,special_c;
 logic [31:0] special_word0,special_word1,special_word2,special_word_c;
 logic sign0,sign1,sign2,sign_c,same0,same_c;
 logic [8:0] exp0,exp1,exp2,exp_c,norm_exp;
 logic [26:0] big0,small0,big_c,small_c,norm2,norm_c;
 logic [27:0] raw1;
 logic [24:0] rounded;
 logic [31:0] packed_result;
 logic [23:0] sig_a,sig_b;
 logic [8:0] exp_a,exp_b;
 logic [26:0] extended_a,extended_b;
 integer difference;
 function automatic logic [26:0] jam(input logic [26:0] x,input integer shift);
   logic sticky;
   begin
    sticky=0;
    if(shift>=27) jam={26'b0,|x};
    else begin
      for(integer i=0;i<27;i=i+1)if(i<shift)sticky=sticky|x[i];
      jam=(x>>shift)|{26'b0,sticky};
    end
   end
 endfunction
 assign advance=!valid[3]||out_ready;
 assign in_ready=advance;
 assign out_valid=valid[3];
 assign out_tag=tags[3];
 always_comb begin
   exp_a=in_a[30:23]==0 ? 9'd1 : {1'b0,in_a[30:23]};
   exp_b=in_b[30:23]==0 ? 9'd1 : {1'b0,in_b[30:23]};
   sig_a={in_a[30:23]!=0,in_a[22:0]};sig_b={in_b[30:23]!=0,in_b[22:0]};
   extended_a={sig_a,3'b0};extended_b={sig_b,3'b0};
   sign_c=in_a[31];same_c=in_a[31]==in_b[31];
   exp_c=exp_a;big_c=extended_a;small_c=extended_b;difference=0;
   if(in_b[30:0]>in_a[30:0]) begin
     sign_c=in_b[31];exp_c=exp_b;big_c=extended_b;difference=int'(exp_b)-int'(exp_a);small_c=jam(extended_a,difference);
   end else begin difference=int'(exp_a)-int'(exp_b);small_c=jam(extended_b,difference);end
   special_c=0;special_word_c=0;
   if((in_a[30:23]==255 && |in_a[22:0]) || (in_b[30:23]==255 && |in_b[22:0])) begin
     special_c=1;special_word_c=32'h7fc00000;
   end else if(in_a[30:23]==255 || in_b[30:23]==255) begin
     special_c=1;
     if(in_a[30:23]==255 && in_b[30:23]==255 && !same_c)special_word_c=32'h7fc00000;
     else special_word_c=in_a[30:23]==255 ? {in_a[31],8'hff,23'b0} : {in_b[31],8'hff,23'b0};
   end
 end
 always_comb begin
   norm_exp=exp1;
   norm_c=raw1[26:0];
   if(raw1[27])begin norm_c=raw1[27:1]|{26'b0,raw1[0]};norm_exp=exp1+1'b1;end
   else begin
     for(integer i=0;i<26;i=i+1)
       if(!norm_c[26] && norm_c!=0 && norm_exp>1)begin norm_c=norm_c<<1;norm_exp=norm_exp-1'b1;end
   end
 end
 always_comb begin
   rounded={1'b0,norm2[26:3]};
   if(norm2[2] && (norm2[1] || norm2[0] || norm2[3]))rounded=rounded+1'b1;
   packed_result=0;
   if(special2)packed_result=special_word2;
   else if(exp2>=255)packed_result={sign2,8'hff,23'b0};
   else if(rounded[24])begin
     if(exp2>=254)packed_result={sign2,8'hff,23'b0};
     else packed_result={sign2,8'(exp2+1'b1),rounded[23:1]};
   end else if(rounded==0)packed_result={sign2,31'b0};
   else if(exp2==1 && !rounded[23])packed_result={sign2,8'b0,rounded[22:0]};
   else packed_result={sign2,exp2[7:0],rounded[22:0]};
 end
 always_ff @(posedge clk)begin
   if(reset)valid<=0;
   else if(advance)begin
     valid<={valid[2:0],in_valid};
     tags[0]<=in_tag;tags[1]<=tags[0];tags[2]<=tags[1];tags[3]<=tags[2];
     sign0<=sign_c;same0<=same_c;exp0<=exp_c;big0<=big_c;small0<=small_c;
     special0<=special_c;special_word0<=special_word_c;
     raw1<=same0 ? ({1'b0,big0}+{1'b0,small0}) : ({1'b0,big0}-{1'b0,small0});
     sign1<=((big0==small0)&&!same0) ? 1'b0 : sign0;
     exp1<=exp0;special1<=special0;special_word1<=special_word0;
     norm2<=norm_c;exp2<=norm_exp;sign2<=sign1;special2<=special1;special_word2<=special_word1;
     out_sum<=packed_result;
   end
 end
endmodule
