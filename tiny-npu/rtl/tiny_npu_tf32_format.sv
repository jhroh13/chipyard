// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
// TF32 container: sign[31], exponent[30:23], fraction[22:13], zeros[12:0].
// Format primitive only; role authorization and TARGETR integration are external.
module tiny_npu_tf32_format(
 input logic [31:0] in_fp32,in_tf32,
 output logic [31:0] out_tf32,out_fp32,
 output logic tf32_encoding_error
);
 logic [32:0] rounded;
 always_comb begin
  rounded={1'b0,in_fp32}+33'h000000fff+{32'b0,in_fp32[13]};
  if(in_fp32[30:23]==8'hff)begin
   if(|in_fp32[22:0])out_tf32=32'h7fc00000;
   else out_tf32=in_fp32;
  end else out_tf32={rounded[31:13],13'b0};
 end
 assign out_fp32=in_tf32;
 assign tf32_encoding_error=|in_tf32[12:0];
endmodule
