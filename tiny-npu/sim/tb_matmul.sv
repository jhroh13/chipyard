// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
module tb_matmul;
  parameter integer ARRAYS=5, CASES=12;
  localparam integer LANES=ARRAYS*32, TOTAL=ARRAYS*1024, BEATS=CASES*32;
  logic clk=0,reset=1;
  always #0.5 clk=~clk;
  logic in_valid,in_ready,out_valid,out_ready,out_last;
  logic [ARRAYS*128-1:0] in_a;
  logic [ARRAYS*256-1:0] in_b,in_scale_a,in_scale_b;
  logic [ARRAYS-1:0] in_active;
  logic [31:0] in_tile_id,out_tile_id;
  logic [LANES*32-1:0] out_data;
  logic [4:0] out_chunk;
  logic [ARRAYS*128-1:0] a_mem[BEATS];
  logic [ARRAYS*256-1:0] b_mem[BEATS],sa_mem[CASES],sb_mem[CASES];
  logic [ARRAYS-1:0] mask_mem[CASES];
  logic [31:0] expected[CASES*TOTAL];
  integer in_pos=0,out_case=0,chunk=0,cycle=0,checked=0;
  integer previous_input_tile_cycle=-1,previous_output_tile_cycle=-1;
  integer input_stalls=0,output_stalls=0;
  logic [31:0] lfsr=32'h13579bdf;
  logic was_stalled=0;
  logic input_waiting=0;
  logic [LANES*32-1:0] held_data;
  logic [31:0] held_id;
  logic [4:0] held_chunk;
  tiny_npu_mxfp4_matmul #(.ARRAYS(ARRAYS)) dut(.*);
  initial begin
    $readmemh("a.hex",a_mem);$readmemh("b.hex",b_mem);
    $readmemh("sa.hex",sa_mem);$readmemh("sb.hex",sb_mem);
    $readmemh("mask.hex",mask_mem);$readmemh("expected.hex",expected);
    in_valid=0;out_ready=0;in_a=0;in_b=0;in_scale_a=0;in_scale_b=0;in_active=0;in_tile_id=0;
    repeat(4) @(negedge clk);
    reset=0;
  end
  always @(negedge clk) begin
    if(!reset) begin
      lfsr={lfsr[30:0],lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
      in_valid=(in_pos<BEATS) && ((in_pos<4*32) || input_waiting || lfsr[0] || lfsr[1]);
      out_ready=(out_case<4) || lfsr[2];
      if(in_pos<BEATS) begin
        in_a=a_mem[in_pos];in_b=b_mem[in_pos];
        in_scale_a=sa_mem[in_pos/32];in_scale_b=sb_mem[in_pos/32];
        in_active=mask_mem[in_pos/32];in_tile_id=32'h1000+32'(in_pos/32);
      end
    end
  end
  always @(posedge clk) begin
    if(!reset) begin
      cycle=cycle+1;
      if(cycle>20000) $fatal(1,"TIMEOUT in=%0d out=%0d chunk=%0d",in_pos,out_case,chunk);
      input_waiting=in_valid&&!in_ready;
      if(input_waiting) input_stalls=input_stalls+1;
      if(out_valid&&!out_ready) output_stalls=output_stalls+1;
      if(was_stalled && (!out_valid || out_data!==held_data || out_tile_id!==held_id || out_chunk!==held_chunk))
        $fatal(1,"Output changed while stalled");
      was_stalled=out_valid&&!out_ready;
      if(was_stalled) begin held_data=out_data;held_id=out_tile_id;held_chunk=out_chunk;end
      if(in_valid&&in_ready) begin
        if(in_pos%32==0 && in_pos<4*32) begin
          if(previous_input_tile_cycle>=0 && cycle-previous_input_tile_cycle!=32) $fatal(1,"Input II is not32");
          previous_input_tile_cycle=cycle;
        end
        in_pos=in_pos+1;
      end
      if(out_valid&&out_ready) begin
        if(out_tile_id!==32'h1000+32'(out_case) || out_chunk!==5'(chunk) || out_last!==(chunk==31))
          $fatal(1,"Output metadata mismatch");
        if(chunk==0 && out_case<4) begin
          if(previous_output_tile_cycle>=0 && cycle-previous_output_tile_cycle!=32) $fatal(1,"Output II is not32");
          previous_output_tile_cycle=cycle;
        end
        for(integer lane=0;lane<LANES;lane=lane+1) begin
          if(out_data[lane*32+:32]!==expected[out_case*TOTAL+(lane/32)*1024+chunk*32+(lane%32)])
            $fatal(1,"MISMATCH case=%0d index=%0d got=%08x expected=%08x",out_case,chunk*LANES+lane,out_data[lane*32+:32],expected[out_case*TOTAL+(lane/32)*1024+chunk*32+(lane%32)]);
          checked=checked+1;
        end
        if(chunk==31) begin
          $display("PASS case=%0d arrays=%0d elements=%0d",out_case,ARRAYS,TOTAL);
          out_case=out_case+1;chunk=0;
          if(out_case==CASES) begin
            if(in_pos!=BEATS) $fatal(1,"Incomplete input execution");
            if(input_stalls==0 || output_stalls==0) $fatal(1,"Backpressure coverage missing");
            $display("SIM_PASS arrays=%0d cases=%0d checked=%0d cycles=%0d input_II=32 output_II=32 input_stalls=%0d output_stalls=%0d",ARRAYS,CASES,checked,cycle,input_stalls,output_stalls);
            $finish;
          end
        end else chunk=chunk+1;
      end
    end
  end
endmodule
