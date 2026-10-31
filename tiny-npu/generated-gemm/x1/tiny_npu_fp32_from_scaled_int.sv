// SPDX-License-Identifier: Apache-2.0
// FP32 = signed integer * 2^(scale_a + scale_b - 262).
// E2M1 is decoded as 2*x; OCP MXINT8 is signed-int/128.
// E8M0 bias is 127. RNE, gradual underflow, infinities, canonical NaN.
`timescale 1ns/1ps
module tiny_npu_fp32_from_scaled_int (
  input logic signed [31:0] value,
  input logic [7:0] scale_a, scale_b,
  output logic [31:0] fp32
);
  logic sign_bit;
  logic [63:0] magnitude, rounded, remainder, half_value;
  integer msb, exponent_unbiased, scale_exp, shift_count;
  always_comb begin
    sign_bit = value[31];
    magnitude = sign_bit ? -{{32{value[31]}},value} : {32'b0,value};
    rounded = 0; remainder = 0; half_value = 0;
    msb = 0; exponent_unbiased = 0; shift_count = 0;
    scale_exp = int'({1'b0,scale_a}) + int'({1'b0,scale_b}) - 262;
    fp32 = 32'b0;
    for (integer bit_index=0; bit_index<32; bit_index=bit_index+1)
      if (magnitude[bit_index]) msb=bit_index;
    if (scale_a==8'hff || scale_b==8'hff) fp32=32'h7fc00000;
    else if (magnitude!=0) begin
      exponent_unbiased=msb+scale_exp;
      if (exponent_unbiased>127) fp32={sign_bit,8'hff,23'b0};
      else if (exponent_unbiased>=-126) begin
        if (msb<=23) rounded=magnitude << (23-msb);
        else begin
          shift_count=msb-23;
          rounded=magnitude >> shift_count;
          remainder=magnitude & ((64'd1 << shift_count)-1);
          half_value=64'd1 << (shift_count-1);
          if (remainder>half_value || (remainder==half_value && rounded[0])) rounded=rounded+1;
        end
        if (rounded[24]) begin rounded=rounded>>1; exponent_unbiased=exponent_unbiased+1; end
        if (exponent_unbiased>127) fp32={sign_bit,8'hff,23'b0};
        else fp32={sign_bit,8'(exponent_unbiased+127),rounded[22:0]};
      end else begin
        // A subnormal FP32 unit is 2^-149.
        shift_count=scale_exp+149;
        if (shift_count>=0) rounded=magnitude << shift_count;
        else if (-shift_count<=63) begin
          shift_count=-shift_count;
          rounded=magnitude >> shift_count;
          remainder=magnitude & ((64'd1 << shift_count)-1);
          half_value=64'd1 << (shift_count-1);
          if (remainder>half_value || (remainder==half_value && rounded[0])) rounded=rounded+1;
        end
        // rounded[23] naturally encodes the minimum normal value.
        fp32={sign_bit,rounded[30:0]};
      end
    end
  end
endmodule
