`timescale 1ns/1ps
module tb_dma_frontend;
 logic clk=0,reset=1;always #0.5 clk=~clk;
 logic cmd_valid=0,cmd_ready,req_valid,req_ready=1,req_last,plan_done,cmd_error;
 logic [39:0] cmd_addr=0,req_addr;logic [31:0] cmd_bytes=0;
 logic [12:0] req_bytes;logic [8:0] req_beats;
 logic iv=0,ir,rv=0,rr,fault;logic [12:0] ib=4096;
 logic [1:0] iid,rid=0;logic [13:0] free_bytes;logic [2:0] outstanding_count;
 integer requests=0,cycle=0,request_stalls=0;
 logic held=0;logic [39:0] held_addr;logic [12:0] held_bytes;logic planner_ok=0,credits_ok=0;
 tiny_npu_dma_burst_planner planner(.*);
 tiny_npu_dma_read_credits #(.MO(4),.BUFFER_BYTES(8192)) credits(
  .clk(clk),.reset(reset),.issue_valid(iv),.issue_ready(ir),.issue_bytes(ib),.issue_id(iid),
  .retire_valid(rv),.retire_id(rid),.retire_ready(rr),.fault(fault),.free_bytes(free_bytes),.outstanding_count(outstanding_count));
 task automatic command(input logic [39:0] a,input logic [31:0] n);
  @(negedge clk);cmd_valid=1;cmd_addr=a;cmd_bytes=n;
  do @(posedge clk);while(!cmd_ready);
  @(negedge clk);cmd_valid=0;
 endtask
 initial begin
  repeat(4)@(negedge clk);reset=0;
  command(40'hfc0,5000);wait(plan_done);@(negedge clk);
  if(cmd_error||requests!=3)$fatal(1,"Planner burst count");
  command(40'h1001,64);if(!cmd_error)$fatal(1,"Unaligned command not rejected");
  command(40'h2000,0);if(!plan_done||cmd_error)$fatal(1,"Zero length handling");
  planner_ok=1;
 end
 always @(negedge clk)if(!reset)begin cycle=cycle+1;req_ready=(cycle%3!=0);end
 always @(posedge clk)if(!reset)begin
  if(held&&(!req_valid||req_addr!==held_addr||req_bytes!==held_bytes))$fatal(1,"Planner changed while stalled");
  held=req_valid&&!req_ready;
  if(held)begin request_stalls=request_stalls+1;held_addr=req_addr;held_bytes=req_bytes;end
 end
 always @(posedge clk)if(!reset&&req_valid&&req_ready)begin
  case(requests)
   0:if(req_addr!==40'hfc0||req_bytes!==64||req_beats!==1||req_last)$fatal(1,"Boundary burst");
   1:if(req_addr!==40'h1000||req_bytes!==4096||req_beats!==64||req_last)$fatal(1,"Full burst");
   2:if(req_addr!==40'h2000||req_bytes!==840||req_beats!==14||!req_last)$fatal(1,"Tail burst");
   default:$fatal(1,"Unexpected request");
  endcase
  requests=requests+1;
 end
 initial begin
  wait(!reset);
  @(negedge clk);iv=1;@(posedge clk);if(!ir||iid!=0)$fatal(1,"First issue");
  @(negedge clk);@(posedge clk);if(!ir||iid!=1)$fatal(1,"Second issue");
  @(negedge clk);iv=0;if(ir||free_bytes!=0)$fatal(1,"Byte credit overflow");
  rv=1;rid=0;iv=1;#0.1;if(!rr||!ir||iid!=0)$fatal(1,"Simultaneous credit recycle");
  @(posedge clk);@(negedge clk);rv=0;iv=0;
  if(outstanding_count!=2||free_bytes!=0)$fatal(1,"Outstanding accounting");
  rv=1;rid=1;@(posedge clk);@(negedge clk);rid=0;@(posedge clk);@(negedge clk);rv=0;
  if(free_bytes!=8192||outstanding_count!=0)$fatal(1,"Credit return accounting");
  rv=1;rid=0;@(posedge clk);@(negedge clk);rv=0;
  if(!fault)$fatal(1,"Invalid retirement not detected");credits_ok=1;
 end
 initial begin
  wait(planner_ok&&credits_ok);if(request_stalls==0)$fatal(1,"Planner stall coverage missing");$display("DMA_FRONTEND_PASS bursts=3 boundary_split=1 byte_credit_stall=1 recycle=1 invalid_retire=1");$finish;
 end
 initial begin #1000;$fatal(1,"DMA frontend timeout");end
endmodule
