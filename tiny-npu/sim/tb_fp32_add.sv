`timescale 1ns/1ps
module tb_fp32_add;
 parameter integer COUNT=20000;
 logic clk=0,reset=1;always #0.5 clk=~clk;
 logic in_valid,in_ready,out_valid,out_ready;
 logic [31:0] in_a,in_b,out_sum;
 logic [37:0] in_tag,out_tag;
 logic [31:0] a[COUNT],b[COUNT],expected[COUNT];
 integer sent=0,received=0,cycles=0,first_input=-1,previous_output=-1;logic waiting=0;
 logic [31:0] lfsr=32'h12345678;
 logic held=0;logic [31:0] held_sum;logic [37:0] held_tag;
 tiny_npu_fp32_add_pipe dut(.*);
 initial begin
  $readmemh("add_a.hex",a);$readmemh("add_b.hex",b);$readmemh("add_expected.hex",expected);
  in_valid=0;out_ready=0;in_a=0;in_b=0;in_tag=0;
  repeat(4)@(negedge clk);reset=0;
 end
 always @(negedge clk)if(!reset)begin
  lfsr={lfsr[30:0],lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
  in_valid=sent<COUNT && (sent<128||waiting||lfsr[0]||lfsr[1]);out_ready=(received<128)||lfsr[2]||lfsr[3];
  if(sent<COUNT)begin in_a=a[sent];in_b=b[sent];in_tag=38'(sent);end
 end
 always @(posedge clk)if(!reset)begin
  cycles=cycles+1;if(cycles>100000)$fatal(1,"Adder timeout");
  if(held&&(!out_valid||out_sum!==held_sum||out_tag!==held_tag))$fatal(1,"Adder stall stability");
  held=out_valid&&!out_ready;if(held)begin held_sum=out_sum;held_tag=out_tag;end
  waiting=in_valid&&!in_ready;
  if(in_valid&&in_ready)begin if(sent==0)first_input=cycles;sent=sent+1;end
  if(out_valid&&out_ready)begin
   if(received==0&&cycles-first_input!=4)$fatal(1,"Adder latency is not4");
   if(received>0&&received<128&&cycles-previous_output!=1)$fatal(1,"Adder II is not1");
   previous_output=cycles;
   if(out_tag!==38'(received)||out_sum!==expected[received])$fatal(1,"ADD mismatch i=%0d a=%08x b=%08x got=%08x expected=%08x",received,a[received],b[received],out_sum,expected[received]);
   received=received+1;
   if(received==COUNT)begin $display("FP32_ADD_PASS comparisons=%0d cycles=%0d pipeline_stages=4",received,cycles);$finish;end
  end
 end
endmodule
