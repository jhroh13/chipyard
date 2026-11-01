// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
// Native LQ16 S1/E7/M8 FMA: 11 arithmetic stages, global elastic backpressure.
// Fused RNE, gradual underflow, canonical NaN, exact cancellation -> +0.
// The 32-bit aligned window retains the full 18-bit product and sticky tail.
// LATENCY>11 adds explicitly identified output transport stages only.
module tiny_npu_lq16_fma_pipe #(parameter integer LATENCY=11)(
 input logic clk,reset,in_valid,output logic in_ready,
 input logic [15:0] a,b,c,output logic out_valid,input logic out_ready,
 output logic [15:0] result
);
 function automatic [36:0] normalize32(input logic [31:0] value);
  logic [31:0] v;logic [4:0] n;
  begin
   v=value;n=0;
   if(v[31:16]==0)begin v=v<<16;n=n+16;end
   if(v[31:24]==0)begin v=v<<8;n=n+8;end
   if(v[31:28]==0)begin v=v<<4;n=n+4;end
   if(v[31:30]==0)begin v=v<<2;n=n+2;end
   if(v[31]==0)begin v=v<<1;n=n+1;end
   normalize32={n,v};
  end
 endfunction
 function automatic [31:0] shift_jam(input logic [31:0] value,input logic [9:0] distance);
  logic [31:0] v;
  begin
   v=value;
   if(distance[0])v={1'b0,v[31:1]}|{31'b0,|v[0:0]};
   if(distance[1])v={2'b0,v[31:2]}|{31'b0,|v[1:0]};
   if(distance[2])v={4'b0,v[31:4]}|{31'b0,|v[3:0]};
   if(distance[3])v={8'b0,v[31:8]}|{31'b0,|v[7:0]};
   if(distance[4])v={16'b0,v[31:16]}|{31'b0,|v[15:0]};
   if(|distance[9:5])v={31'b0,|value};
   shift_jam=v;
  end
 endfunction
 // Parallel prefix carry avoids a 33-bit ripple/negate/absolute-value chain.
 function automatic [32:0] add_prefix(input logic [32:0] x,y,input logic carry_in);
  logic [32:0] p[7],g[7],carry;
  begin
   p[0]=x^y;g[0]=x&y;
   for(integer level=0;level<6;level++)begin
    for(integer i=0;i<33;i++)begin
     if(i>=(1<<level))begin
      g[level+1][i]=g[level][i]|(p[level][i]&g[level][i-(1<<level)]);
      p[level+1][i]=p[level][i]&p[level][i-(1<<level)];
     end else begin g[level+1][i]=g[level][i];p[level+1][i]=p[level][i];end
    end
   end
   carry[0]=carry_in;
   for(integer i=1;i<33;i++)carry[i]=g[6][i-1]|(p[6][i-1]&carry_in);
   add_prefix=p[0]^carry;
  end
 endfunction
 function automatic [9:0] subtract10(input logic [9:0] x,y);
  subtract10=10'(add_prefix({23'b0,x},{23'b0,~y},1'b1));
 endfunction
 typedef struct packed {logic special;logic [15:0] value;} special_t;
 typedef struct packed {logic [13:0] product_lo;logic [12:0] product_hi;logic [8:0] c_sig;logic signed [9:0] pq,cq;logic ps,cs;special_t exceptional;} s0_t;
 typedef struct packed {logic [17:0] product;logic [8:0] c_sig;logic signed [9:0] pq,cq;logic ps,cs;special_t exceptional;} s1_t;
 typedef struct packed {logic [31:0] pn,cn;logic signed [9:0] pe,ce;logic ps,cs;special_t exceptional;} s2_t;
 typedef struct packed {logic [31:0] mag_hi,mag_lo;logic [9:0] distance;logic signed [9:0] exponent;logic sign_bit,subtract;special_t exceptional;} s3_t;
 typedef struct packed {logic [31:0] mag_hi,mag_lo;logic signed [9:0] exponent;logic sign_bit,subtract;special_t exceptional;} s4_t;
 typedef struct packed {logic [32:0] magnitude;logic signed [9:0] exponent;logic sign_bit;special_t exceptional;} s5_t;
 typedef struct packed {logic [31:0] normalized;logic signed [9:0] exponent;logic sign_bit,is_zero;special_t exceptional;} s6_t;
 typedef struct packed {logic [8:0] retained;logic round_up;logic signed [9:0] exponent;logic sign_bit,is_zero,denormal;special_t exceptional;} s7_t;
 typedef struct packed {logic [31:0] pn,cn;logic signed [9:0] pbase,cbase;logic [4:0] plz,clz;logic pzero,czero,ps,cs;special_t exceptional;} norm_inputs_t;
 typedef struct packed {logic [31:0] normalized;logic [4:0] lz;logic signed [9:0] exponent_base;logic sign_bit,is_zero;special_t exceptional;} norm_sum_t;
 norm_inputs_t sn,dn;norm_sum_t an,dan;
 s0_t s0,d0;s1_t s1,d1;s2_t s2,d2;s3_t s3,d3;s4_t s4,d4;s5_t s5,d5;s6_t s6,d6;s7_t s7,d7;
 logic [15:0] d8;logic [15:0] output_pipe[0:LATENCY-11];logic [LATENCY-1:0] valid_pipe;logic advance;
 logic [8:0] ma,mb,mc;logic [6:0] ea,eb,ec;
 logic [36:0] np,nc,ns;logic product_big;logic [32:0] addend;logic [9:0] denormal_shift,rounded_sig;logic [31:0] underflow_value;logic signed [9:0] encoded_exp;
 // S0: decode/classify and parallel 9x5 / 9x4 partial products.
 always_comb begin
  ma={(|a[14:8]),a[7:0]};mb={(|b[14:8]),b[7:0]};mc={(|c[14:8]),c[7:0]};
  ea=a[14:8]==0?7'd1:a[14:8];eb=b[14:8]==0?7'd1:b[14:8];ec=c[14:8]==0?7'd1:c[14:8];
  // Pre-bias exponents here so S2 needs only one subtraction after LZ decode.
  d0='0;d0.product_lo=ma*mb[4:0];d0.product_hi=ma*mb[8:5];d0.c_sig=mc;
  d0.pq=$signed({3'b0,ea})+$signed({3'b0,eb})-10'sd125;
  d0.cq=$signed({3'b0,ec})-10'sd63;d0.ps=a[15]^b[15];d0.cs=c[15];
  if((a[14:8]==127&&a[7:0]!=0)||(b[14:8]==127&&b[7:0]!=0)||(c[14:8]==127&&c[7:0]!=0))begin d0.exceptional.special=1;d0.exceptional.value=16'h7f80;end
  else if((a[14:8]==127&&b[14:0]==0)||(b[14:8]==127&&a[14:0]==0))begin d0.exceptional.special=1;d0.exceptional.value=16'h7f80;end
  else if(a[14:8]==127||b[14:8]==127)begin
   d0.exceptional.special=1;
   d0.exceptional.value=(c[14:8]==127&&c[15]!=d0.ps)?16'h7f80:{d0.ps,7'h7f,8'b0};
  end else if(c[14:8]==127)begin d0.exceptional.special=1;d0.exceptional.value={c[15],7'h7f,8'b0};end
 end
 // S1: exact product recombination. This is a real arithmetic pipeline cut.
 always_comb begin
  d1.product=18'(add_prefix({19'b0,s0.product_lo},{15'b0,s0.product_hi,5'b0},1'b0));
  d1.c_sig=s0.c_sig;d1.pq=s0.pq;d1.cq=s0.cq;d1.ps=s0.ps;d1.cs=s0.cs;d1.exceptional=s0.exceptional;
 end
 // Normalization and exponent correction have separate register boundaries.
 always_comb begin
  np=normalize32({s1.product,14'b0});nc=normalize32({s1.c_sig,23'b0});dn='0;
  dn.pn=np[31:0]>>1;dn.cn=nc[31:0]>>1;dn.plz=np[36:32];dn.clz=nc[36:32];
  dn.pbase=s1.pq;dn.cbase=s1.cq;dn.pzero=s1.product==0;dn.czero=s1.c_sig==0;
  dn.ps=s1.ps;dn.cs=s1.cs;dn.exceptional=s1.exceptional;
 end
 always_comb begin
  d2='0;d2.pn=sn.pn;d2.cn=sn.cn;
  d2.pe=sn.pzero?-10'sd256:$signed(subtract10(sn.pbase,{5'b0,sn.plz}));
  d2.ce=sn.czero?-10'sd256:$signed(subtract10(sn.cbase,{5'b0,sn.clz}));
  d2.ps=sn.ps;d2.cs=sn.cs;d2.exceptional=sn.exceptional;
 end
 // S3: magnitude ordering. Subtraction always computes nonnegative mag_hi-mag_lo.
 always_comb begin
  product_big=(s2.pe>s2.ce)||((s2.pe==s2.ce)&&(s2.pn>=s2.cn));d3='0;
  d3.mag_hi=product_big?s2.pn:s2.cn;d3.mag_lo=product_big?s2.cn:s2.pn;
  d3.exponent=product_big?s2.pe:s2.ce;
  d3.distance=product_big?10'(s2.pe-s2.ce):10'(s2.ce-s2.pe);
  d3.sign_bit=product_big?s2.ps:s2.cs;d3.subtract=s2.ps^s2.cs;d3.exceptional=s2.exceptional;
 end
 // S4: one jammed right align, including all information needed by final RNE.
 always_comb begin
  d4.mag_hi=s3.mag_hi;d4.mag_lo=shift_jam(s3.mag_lo,s3.distance);d4.exponent=s3.exponent;
  d4.sign_bit=s3.sign_bit;d4.subtract=s3.subtract;d4.exceptional=s3.exceptional;
 end
 // S5: single unsigned prefix add/sub; no post-add wide absolute value.
 always_comb begin
  addend={1'b0,s4.mag_lo}^{33{s4.subtract}};
  d5.magnitude=add_prefix({1'b0,s4.mag_hi},addend,s4.subtract);
  d5.exponent=s4.exponent+10'sd1;d5.sign_bit=s4.sign_bit;d5.exceptional=s4.exceptional;
 end
 // Post-cancellation normalization and exponent correction are separate stages.
 always_comb begin
  ns=normalize32(s5.magnitude[31:0]);dan.normalized=ns[31:0];dan.lz=ns[36:32];
  dan.exponent_base=s5.exponent;dan.sign_bit=s5.sign_bit;dan.is_zero=s5.magnitude==0;dan.exceptional=s5.exceptional;
 end
 always_comb begin
  d6.normalized=an.normalized;d6.exponent=$signed(subtract10(an.exponent_base,{5'b0,an.lz}));
  d6.sign_bit=an.sign_bit;d6.is_zero=an.is_zero;d6.exceptional=an.exceptional;
 end
 // S7: gradual-underflow alignment, separated from rounding/packing.
 always_comb begin
  d7.denormal=s6.exponent< -10'sd62;
  denormal_shift=d7.denormal?10'(-10'sd62-s6.exponent):10'd0;
  underflow_value=shift_jam(s6.normalized,denormal_shift);
  d7.retained=underflow_value[31:23];d7.round_up=underflow_value[22]&&((|underflow_value[21:0])||underflow_value[23]);d7.exponent=s6.exponent+10'sd63;
  d7.sign_bit=s6.sign_bit;d7.is_zero=s6.is_zero;d7.exceptional=s6.exceptional;
 end
 // S8: one fused RNE and format pack. No product pre-rounding.
 always_comb begin
  rounded_sig={1'b0,s7.retained}+{9'b0,s7.round_up};
  encoded_exp=s7.exponent+$signed({9'b0,rounded_sig[9]});
  if(s7.denormal)d8={s7.sign_bit,6'b0,rounded_sig[8:0]};
  else if(encoded_exp>=127)d8={s7.sign_bit,7'h7f,8'b0};
  else d8={s7.sign_bit,encoded_exp[6:0],rounded_sig[9]?8'b0:rounded_sig[7:0]};
  if(s7.is_zero)d8=0;
  if(s7.exceptional.special)d8=s7.exceptional.value;
 end
 assign advance=!valid_pipe[LATENCY-1]||out_ready;
 assign in_ready=advance&&!reset;assign out_valid=valid_pipe[LATENCY-1];assign result=output_pipe[LATENCY-11];
 always_ff @(posedge clk)begin
  if(reset)valid_pipe<=0;
  else if(advance)begin
   valid_pipe[0]<=in_valid;for(integer i=1;i<LATENCY;i++)valid_pipe[i]<=valid_pipe[i-1];
   if(in_valid)s0<=d0;
   if(valid_pipe[0])s1<=d1;
   if(valid_pipe[1])sn<=dn;
   if(valid_pipe[2])s2<=d2;
   if(valid_pipe[3])s3<=d3;
   if(valid_pipe[4])s4<=d4;
   if(valid_pipe[5])s5<=d5;
   if(valid_pipe[6])an<=dan;
   if(valid_pipe[7])s6<=d6;
   if(valid_pipe[8])s7<=d7;
   if(valid_pipe[9])output_pipe[0]<=d8;
  end
 end
 for(genvar i=1;i<=LATENCY-11;i++)begin:g_output_transport
  always_ff @(posedge clk)if(!reset&&advance&&valid_pipe[i+9])output_pipe[i]<=output_pipe[i-1];
 end
 initial if(LATENCY<11)$fatal(1,"Eleven arithmetic stages required");
endmodule
