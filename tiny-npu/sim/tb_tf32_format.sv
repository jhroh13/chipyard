`timescale 1ns/1ps
module tb_tf32_format;
 parameter integer COUNT=20000;
 logic [31:0] in_fp32,in_tf32,out_tf32,out_fp32;
 logic tf32_encoding_error;
 logic [31:0] inputs[COUNT],expected[COUNT];
 tiny_npu_tf32_format dut(.*);
 initial begin
  $readmemh("input.hex",inputs);$readmemh("expected.hex",expected);
  for(integer i=0;i<COUNT;i=i+1)begin
   in_fp32=inputs[i];in_tf32=expected[i]|(i%7==0 ? 32'd1 : 32'd0);#1;
   if(out_tf32!==expected[i]||out_fp32!==in_tf32||tf32_encoding_error!==(i%7==0))
    $fatal(1,"TF32 format mismatch i=%0d in=%08x got=%08x expected=%08x",i,in_fp32,out_tf32,expected[i]);
  end
  $display("TF32_FORMAT_PASS inputs=%0d rounding=RNE container_bits=32 fraction_bits=10",COUNT);$finish;
 end
endmodule
