`timescale 1ns/1ps
module tb_c_hazard;
 logic clk=0,reset=1;always #0.5 clk=~clk;
 logic in_valid,in_ready,in_first_k,in_last_k,out_valid,out_ready,out_last;
 logic [31:0] in_data,out_data,in_tile_id=42,out_tile_id;
 logic [4:0] in_chunk,out_chunk;
 integer sent=0,received=0,cycles=0,blocked=0;
 logic [31:0] values[7];
 logic [31:0] wanted[3];
 tiny_npu_k_accumulator #(.LANES(1)) dut(.*);
 initial begin
  values[0]=32'h3f800000;values[1]=32'h40000000;values[2]=32'hc0400000;
  values[3]=1;values[4]=1;values[5]=32'h7f800000;values[6]=32'hff800000;
  wanted[0]=0;wanted[1]=2;wanted[2]=32'h7fc00000;
  in_valid=0;out_ready=0;in_data=0;in_chunk=0;in_first_k=0;in_last_k=0;
  repeat(4)@(negedge clk);reset=0;
 end
 always @(negedge clk)if(!reset)begin
  in_valid=sent<7;out_ready=(cycles%5!=0);
  if(sent<7)begin
   in_data=values[sent];in_chunk=sent<3 ? 0 : (sent<5 ? 1 : 2);
   in_first_k=(sent==0||sent==3||sent==5);in_last_k=(sent==2||sent==4||sent==6);
  end
 end
 always @(posedge clk)if(!reset)begin
  cycles=cycles+1;if(cycles>300)$fatal(1,"C hazard timeout");
  if(in_valid&&!in_ready)blocked=blocked+1;
  if(in_valid&&in_ready)sent=sent+1;
  if(out_valid&&out_ready)begin
   if(out_data!==wanted[received]||out_chunk!==5'(received)||out_tile_id!==42)$fatal(1,"C RMW hazard mismatch");
   received=received+1;
   if(received==3)begin
    if(blocked==0)$fatal(1,"No scoreboard hazard exercised");
    $display("C_HAZARD_PASS results=%0d blocked_cycles=%0d cycles=%0d",received,blocked,cycles);$finish;
   end
  end
 end
endmodule
