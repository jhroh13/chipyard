`timescale 1ps/1ps
module tb_bank_hash;
 parameter integer BANKS=160,HASH=1;localparam integer BB=$clog2(BANKS),TOTAL=BANKS*1024;
 logic clk=0,reset=1;always #500 clk=~clk;
 logic cfg_enable=(HASH!=0);logic [4:0] cfg_shift=2;
 logic in_valid,in_ready,out_valid,out_ready,idle;logic [BB-1:0] in_bank,out_bank;
 logic [9:0] in_row,out_row;logic [31:0] in_payload,out_payload;
 integer sent=0,received=0,cycles=0,g,expected_bank;logic held=0;logic [BB+41:0] saved;
 tiny_npu_bank_hash #(.BANKS(BANKS),.ROW_BITS(10),.PAYLOAD_BITS(32)) dut(.*);
 assign in_valid=(sent<TOTAL);assign in_bank=BB'(sent%BANKS);assign in_row=10'(sent/BANKS);assign in_payload=32'(sent);
 always @(negedge clk)out_ready=((cycles%7)!=3)&&((cycles%11)!=4);
 always @(posedge clk)begin
  cycles++;
  if(!reset)begin
   if(held&&(!out_valid||{out_bank,out_row,out_payload}!==saved))$fatal(1,"mapper output changed under stall");
   held=out_valid&&!out_ready;saved={out_bank,out_row,out_payload};
   if(out_valid&&out_ready)begin
    g=((received/BANKS)>>2)&((1<<BB)-1);if(g>=BANKS)g-=BANKS;
    expected_bank=((received%BANKS)+((HASH!=0)?g:0))%BANKS;
    if(integer'(out_bank)!=expected_bank||integer'(out_row)!=(received/BANKS)||out_payload!=32'(received))$fatal(1,"hash bijection/metadata mismatch");
    received++;
   end
   if(in_valid&&in_ready)sent<=sent+1;
   if(received==TOTAL)begin $display("BANK_HASH_PASS banks=%0d hash=%0d checked=%0d",BANKS,HASH,received);$finish;end
   if(cycles>TOTAL*3)$fatal(1,"hash timeout");
  end
 end
 initial begin out_ready=1;repeat(4)@(negedge clk);reset=0;end
endmodule
