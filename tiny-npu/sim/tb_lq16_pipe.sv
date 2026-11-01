`timescale 1ns/1ps
module tb_lq16_pipe;
 parameter integer COUNT=6000,LATENCY=11,GAPS=0,FLUSH=0;
 logic clk=0,reset=1,in_valid,in_ready,out_valid,out_ready;logic [15:0] a,b,c,result;
 logic [63:0] vectors[COUNT];integer sent=0,received=0,cycles=0,stalls=0,first_input=-1,skipped=0,comparisons=0,trace_fd=0;
 logic source_valid=1,source_blocked=0,held=0;logic [15:0] held_result;string trace_name;
 always #5 clk=~clk;
 tiny_npu_lq16_fma_pipe #(.LATENCY(LATENCY)) dut(.*);
 logic ref_in_ready,ref_out_valid;logic [15:0] ref_result;
 tiny_npu_lq16_fma_proto #(.LATENCY(LATENCY)) reference_dut(.clk,.reset,.in_valid,.in_ready(ref_in_ready),.a,.b,.c,.out_valid(ref_out_valid),.out_ready,.result(ref_result));
 assign in_valid=(sent<COUNT)&&source_valid;assign a=vectors[sent<COUNT?sent:0][63:48];assign b=vectors[sent<COUNT?sent:0][47:32];assign c=vectors[sent<COUNT?sent:0][31:16];
 assign out_ready=(cycles<32)||((cycles%7)!=3&&(cycles%11)!=5);
 always @(negedge clk)if(!reset)begin
  if(source_blocked)source_valid<=1;
  else source_valid<=(GAPS==0)||cycles<32||(cycles%9!=5);
 end
 initial begin
  if($value$plusargs("PIPE_TRACE=%s",trace_name))begin
   trace_fd=$fopen(trace_name,"w");
   $fwrite(trace_fd,"{\"type\":\"meta\",\"schema_version\":1,\"latency_cycles\":%0d,\"arithmetic_stages\":11,\"capture_cycles\":256,\"provenance\":{\"source\":\"native LQ16 FMA RTL with exact golden comparison\"}}\n",LATENCY);
  end
 end
 final if(trace_fd!=0)$fclose(trace_fd);
 always @(posedge clk)if(!reset&&trace_fd!=0&&cycles<256)begin
  for(integer st=0;st<LATENCY;st++)$fwrite(trace_fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":10000,\"channel\":\"fma.stage%0d\",\"valid\":%0d,\"ready\":%0d,\"active\":1,\"stall_mask\":%0d}\n",$time*1000,st+1,dut.valid_pipe[st],dut.advance,dut.valid_pipe[st]?(dut.advance?0:16):1);
  $fwrite(trace_fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":10000,\"channel\":\"mac.issue\",\"valid\":%0d,\"ready\":%0d,\"active\":1,\"stall_mask\":%0d}\n",$time*1000,in_valid,in_ready,in_valid?(in_ready?0:16):1);
 end
 initial begin $readmemh("vectors.hex",vectors);repeat(4)@(negedge clk);reset=0;
  if(FLUSH!=0)begin wait(cycles>=100);@(negedge clk);reset=1;repeat(2)@(negedge clk);if(out_valid)$fatal(1,"reset did not flush valid");reset=0;end
 end
 always @(posedge clk)if(reset)begin
  source_blocked<=0;held<=0;
  if(cycles>0)begin skipped<=skipped+sent-received;received<=sent;end
 end else begin
  cycles<=cycles+1;source_blocked<=in_valid&&!in_ready;
  if(held&&(!out_valid||result!==held_result))$fatal(1,"output changed under backpressure");
  held<=out_valid&&!out_ready;held_result<=result;
  if(in_ready!==ref_in_ready||out_valid!==ref_out_valid)$fatal(1,"reference handshake mismatch");
  if(out_valid&&result!==ref_result)$fatal(1,"wide reference mismatch n=%0d",received);
  if(in_valid&&in_ready)begin if(sent==0)first_input=cycles;sent<=sent+1;end
  if(out_valid&&!out_ready)stalls<=stalls+1;
  if(out_valid&&out_ready)begin
   if(received==0&&cycles-first_input!=LATENCY)$fatal(1,"latency mismatch");
   if(result!==vectors[received][15:0])$fatal(1,"FMA mismatch n=%0d got=%h expected=%h a=%h b=%h c=%h",received,result,vectors[received][15:0],vectors[received][63:48],vectors[received][47:32],vectors[received][31:16]);
   received<=received+1;comparisons<=comparisons+1;
   if(received+1==COUNT)begin $display("LQ16_PIPE_PASS count=%0d comparisons=%0d skipped=%0d latency=%0d stalls=%0d gaps=%0d flush=%0d",COUNT,comparisons+1,skipped,LATENCY,stalls,GAPS,FLUSH);$finish;end
  end
  if(cycles>COUNT*4)$fatal(1,"timeout");
 end
endmodule
