`timescale 1ns/1ps
module tb_gemm;
 parameter integer ARRAYS=1,JOBS=8,BEATS=4576;
 localparam integer LANES=ARRAYS*32,TOTAL=ARRAYS*1024;
 logic clk=0,reset=1;always #0.5 clk=~clk;
 logic job_valid,job_ready,in_valid,in_ready,out_valid,out_ready,out_last;
 logic [15:0] job_k_blocks;logic [31:0] job_id,out_tile_id;
 logic [ARRAYS*128-1:0] in_a;
 logic [ARRAYS*256-1:0] in_b,in_scale_a,in_scale_b;
 logic [ARRAYS-1:0] in_active='1;
 logic [LANES*32-1:0] out_data;logic [4:0] out_chunk;
 logic [ARRAYS*128-1:0] av[BEATS];logic [ARRAYS*256-1:0] bv[BEATS],sa[BEATS],sb[BEATS];
 logic [31:0] expected[JOBS*TOTAL],ends[JOBS];logic [15:0] blocks[JOBS];
 integer pos=0,job=0,chunk=0,cycle=0,checked=0;logic started=0,waiting=0;
 logic [31:0] lfsr=32'h2468ace1;
 logic held=0;logic [LANES*32-1:0] hold_data;logic [4:0] hold_chunk;logic [31:0] hold_id;
 tiny_npu_gemm_stream #(.ARRAYS(ARRAYS)) dut(.*);
 initial begin
  $readmemh("a.hex",av);$readmemh("b.hex",bv);$readmemh("sa.hex",sa);$readmemh("sb.hex",sb);
  $readmemh("expected.hex",expected);$readmemh("ends.hex",ends);$readmemh("blocks.hex",blocks);
  job_valid=0;in_valid=0;out_ready=0;job_k_blocks=0;job_id=0;in_a=0;in_b=0;in_scale_a=0;in_scale_b=0;
  repeat(4)@(negedge clk);reset=0;
 end
 always @(negedge clk)if(!reset && job<JOBS)begin
  lfsr={lfsr[30:0],lfsr[31]^lfsr[21]^lfsr[1]^lfsr[0]};
  job_valid=!started;job_k_blocks=blocks[job];job_id=32'h2000+32'(job);
  in_valid=started&&pos<int'(ends[job])&&(waiting||lfsr[0]||lfsr[1]);out_ready=lfsr[2];
  if(pos<BEATS)begin in_a=av[pos];in_b=bv[pos];in_scale_a=sa[pos];in_scale_b=sb[pos];end
 end
 always @(posedge clk)if(!reset)begin
  cycle=cycle+1;if(cycle>100000)$fatal(1,"GEMM timeout job=%0d pos=%0d chunk=%0d",job,pos,chunk);
  if(held&&(!out_valid||out_data!==hold_data||out_chunk!==hold_chunk||out_tile_id!==hold_id))$fatal(1,"GEMM unstable output");
  held=out_valid&&!out_ready;if(held)begin hold_data=out_data;hold_chunk=out_chunk;hold_id=out_tile_id;end
  if(job_valid&&job_ready)started=1;
  waiting=in_valid&&!in_ready;if(in_valid&&in_ready)pos=pos+1;
  if(out_valid&&out_ready)begin
   if(pos<int'(ends[job]))$fatal(1,"Output before final K input");
   if(out_chunk!==5'(chunk)||out_tile_id!==32'h2000+32'(job)||out_last!==(chunk==31))$fatal(1,"GEMM metadata mismatch");
   for(integer lane=0;lane<LANES;lane=lane+1)begin
    if(out_data[lane*32+:32]!==expected[job*TOTAL+(lane/32)*1024+chunk*32+(lane%32)])
     $fatal(1,"GEMM mismatch job=%0d row=%0d lane=%0d got=%08x expected=%08x",job,chunk,lane,out_data[lane*32+:32],expected[job*TOTAL+(lane/32)*1024+chunk*32+(lane%32)]);
    checked=checked+1;
   end
   if(chunk==31)begin
    $display("PASS job=%0d K=%0d arrays=%0d",job,int'(blocks[job])*32,ARRAYS);
    job=job+1;chunk=0;started=0;
    if(job==JOBS)begin $display("GEMM_PASS arrays=%0d jobs=%0d comparisons=%0d cycles=%0d",ARRAYS,JOBS,checked,cycle);$finish;end
   end else chunk=chunk+1;
  end
 end
endmodule
