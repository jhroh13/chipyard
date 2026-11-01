`timescale 1ns/1ps
module tb_lq16_fma;
 parameter integer COUNT=6000,LATENCY=4;
 logic clk=0,reset=1,in_valid,in_ready,out_valid,out_ready;logic [15:0] a,b,c,result;
 logic [63:0] vectors[COUNT];integer sent=0,received=0,cycles=0,stalls=0,first_input=-1;
 always #5 clk=~clk;
 tiny_npu_lq16_fma_proto #(.LATENCY(LATENCY)) dut(.*);
 assign in_valid=sent<COUNT;assign a=vectors[sent<COUNT?sent:0][63:48];assign b=vectors[sent<COUNT?sent:0][47:32];assign c=vectors[sent<COUNT?sent:0][31:16];
 assign out_ready=(cycles<32)||((cycles%7)!=3&&(cycles%11)!=5);
 initial begin $readmemh("vectors.hex",vectors);repeat(4)@(negedge clk);reset=0;end
 always @(posedge clk)if(!reset)begin
  cycles<=cycles+1;
  if(in_valid&&in_ready)begin if(sent==0)first_input=cycles;sent<=sent+1;end
  if(out_valid&&!out_ready)stalls<=stalls+1;
  if(out_valid&&out_ready)begin
   if(received==0&&cycles-first_input!=LATENCY)$fatal(1,"latency mismatch");
   if(result!==vectors[received][15:0])$fatal(1,"FMA mismatch n=%0d got=%h expected=%h a=%h b=%h c=%h",received,result,vectors[received][15:0],vectors[received][63:48],vectors[received][47:32],vectors[received][31:16]);
   received<=received+1;
   if(received+1==COUNT)begin $display("LQ16_FMA_PASS count=%0d latency=%0d stalls=%0d",COUNT,LATENCY,stalls);$finish;end
  end
  if(cycles>COUNT*4)$fatal(1,"timeout");
 end
endmodule
