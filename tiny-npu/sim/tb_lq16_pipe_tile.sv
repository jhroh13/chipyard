`timescale 1ns/1ps
// Native staged FMA with parameterized interleaved accumulators and actual result feedback.
// Predecoded MX operands are testbench inputs; no MX decoder/array is claimed.
module tb_lq16_pipe_tile;
 parameter integer K=32,CONTEXTS=12,LATENCY=11,FEEDBACK_EXTRA=1,COUNT=((1024+CONTEXTS-1)/CONTEXTS)*CONTEXTS*K;
 logic clk=0,reset=1,in_valid,in_ready,out_valid,out_ready;logic [15:0] a,b,c,result;
 logic [31:0] operands[COUNT];logic [15:0] expected[COUNT],acc[1024];
 integer sent=0,received=0,cycles=0,in_pixel,out_pixel,stalls=0;
 always #5 clk=~clk;
 assign in_pixel=(sent/(CONTEXTS*K))*CONTEXTS+(sent%CONTEXTS);assign out_pixel=(received/(CONTEXTS*K))*CONTEXTS+(received%CONTEXTS);
 assign in_valid=sent<COUNT;assign out_ready=(cycles%13)!=6&&(cycles%17)!=9;
 assign a=operands[sent<COUNT?sent:0][31:16];assign b=operands[sent<COUNT?sent:0][15:0];
 // Explicit feedback guard: no result-to-input combinational bypass in this fixture.
 assign c=(in_pixel>=1024||(sent/CONTEXTS)%K==0)?16'b0:acc[in_pixel];
 tiny_npu_lq16_fma_pipe #(.LATENCY(LATENCY)) dut(.*);
 initial begin
  if(CONTEXTS<LATENCY+FEEDBACK_EXTRA)$fatal(1,"insufficient feedback contexts");
  $readmemh("operands.hex",operands);$readmemh("expected.hex",expected);
  for(integer p=0;p<1024;p++)acc[p]=0;
  repeat(4)@(negedge clk);reset=0;
 end
 always @(posedge clk)if(!reset)begin
  cycles<=cycles+1;if(in_valid&&in_ready)sent<=sent+1;
  if(out_valid&&!out_ready)stalls<=stalls+1;
  if(out_valid&&out_ready)begin
   if(result!==expected[received])$fatal(1,"tile feedback mismatch step=%0d pixel=%0d got=%h expected=%h",received,out_pixel,result,expected[received]);
   if(out_pixel<1024)acc[out_pixel]<=result;received<=received+1;
   if(received+1==COUNT)begin $display("LQ16_PIPE_TILE_PASS M=32 N=32 K=%0d comparisons=%0d stalls=%0d",K,COUNT,stalls);$finish;end
  end
  if(cycles>COUNT*3)$fatal(1,"tile timeout");
 end
endmodule
