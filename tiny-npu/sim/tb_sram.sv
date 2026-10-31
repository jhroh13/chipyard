// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
module tb_sram;
  localparam integer WIDTH=256, DEPTH=16;
  logic clk=0;always #0.5 clk=~clk;
  logic rd_en=0,wr_en=0;
  logic [3:0] rd_addr=0,wr_addr=0;
  logic [255:0] rd_data,wr_data=0,expected;
  logic [31:0] wr_mask=0;
  logic [255:0] reference_mem[DEPTH];
  tiny_npu_sram_bank #(.WIDTH(WIDTH),.DEPTH(DEPTH)) dut(.*);
  initial begin
    for(integer i=0;i<DEPTH;i=i+1) begin
      @(negedge clk);wr_en=1;wr_addr=4'(i);wr_data=256'(i);wr_mask='1;
      reference_mem[i]=256'(i);
    end
    for(integer step=0;step<128;step=step+1) begin
      @(negedge clk);
      rd_en=1;wr_en=(step%3!=0);rd_addr=4'(step%DEPTH);
      wr_addr=(step%2==0) ? rd_addr : 4'((step+3)%DEPTH);
      wr_data={8{32'(step*12345)}};
      wr_mask=(step%2==0) ? 32'h55555555 : 32'haaaaaaaa;
      expected=reference_mem[rd_addr];
      for(integer b=0;b<32;b=b+1)
        if(wr_en && wr_mask[b]) begin
          reference_mem[wr_addr][8*b+:8]=wr_data[8*b+:8];
          if(wr_addr==rd_addr)expected[8*b+:8]=wr_data[8*b+:8];
        end
      @(posedge clk);#0.1;
      if(rd_data!==expected)$fatal(1,"SRAM byte-mask/read-write mismatch step=%0d",step);
    end
    $display("SRAM_PASS comparisons=128 width=256 port=1R1W read_latency=1 same_address=write_first");$finish;
  end
endmodule
