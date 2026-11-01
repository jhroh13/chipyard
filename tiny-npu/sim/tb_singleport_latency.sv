`timescale 1ns/1ps
module tb_singleport_latency;
 parameter integer LATENCY=16;
 logic clk=0,reset=1;always #0.5 clk=~clk;
 logic cmd_valid,cmd_ready,cmd_write,rsp_valid,rsp_ready;
 logic [3:0] cmd_addr;logic [255:0] cmd_data,rsp_data;
 logic [31:0] cmd_mask;logic [255:0] refmem[16],expected[256];integer issue_cycle[256];
 integer sent=0,issued=0,received=0,cycles=0,stalls=0;
 logic waiting=0,held=0;logic [255:0] held_data;logic [31:0] rng=32'h1f2e3d4c;
 tiny_npu_sram_1rw_subbank #(.DEPTH(16),.READ_LATENCY(LATENCY)) dut(.*);
 initial begin cmd_valid=0;rsp_ready=0;cmd_write=0;cmd_addr=0;cmd_data=0;cmd_mask=0;repeat(4)@(negedge clk);reset=0;end
 always @(negedge clk)if(!reset)begin
  rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
  cmd_valid=sent<144&&(waiting||received<8||rng[0]||rng[1]);
  rsp_ready=(received<8)||rng[2];cmd_addr=4'(sent%16);
  cmd_write=(sent<16)||(sent%3==0);cmd_data={8{32'(sent*12345)}};
  cmd_mask=sent<16 ? 32'hffffffff : (sent%2!=0 ? 32'haaaaaaaa : 32'h55555555);
 end
 always @(posedge clk)if(!reset)begin
  cycles=cycles+1;if(cycles>4000)$fatal(1,"Single-port timeout");
  if(held&&(!rsp_valid||rsp_data!==held_data))$fatal(1,"Single-port response changed on stall");
  held=rsp_valid&&!rsp_ready;if(held)begin held_data=rsp_data;stalls=stalls+1;end
  waiting=cmd_valid&&!cmd_ready;
  if(cmd_valid&&cmd_ready)begin
   if(cmd_write)begin for(integer b=0;b<32;b=b+1)if(cmd_mask[b])refmem[cmd_addr][b*8+:8]=cmd_data[b*8+:8];end
   else begin expected[issued]=refmem[cmd_addr];issue_cycle[issued]=cycles;issued=issued+1;end
   sent=sent+1;
  end
  if(rsp_valid&&rsp_ready)begin
   if(received>=issued||rsp_data!==expected[received])$fatal(1,"Single-port read mismatch");
   if(received<8&&cycles-issue_cycle[received]!=LATENCY)$fatal(1,"Wrong path latency");
   received=received+1;
  end
  if(sent==144&&received==issued)begin
   if(stalls==0)$fatal(1,"No response backpressure exercised");
   $display("SINGLEPORT_PASS latency=%0d commands=%0d read_results=%0d rsp_stalls=%0d",LATENCY,sent,received,stalls);$finish;
  end
 end
endmodule
