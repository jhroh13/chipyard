// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
// Reserve RX byte credits and source ID before read issue. Release only after
// the complete response is drained, not on its first beat. No AXI master here.
module tiny_npu_dma_read_credits #(
 parameter integer MO=64,BUFFER_BYTES=131072,ID_BITS=$clog2(MO),CREDIT_BITS=$clog2(BUFFER_BYTES+1)
)(
 input logic clk,reset,issue_valid,output logic issue_ready,
 input logic [12:0] issue_bytes,output logic [ID_BITS-1:0] issue_id,
 input logic retire_valid,input logic [ID_BITS-1:0] retire_id,
 output logic retire_ready,output logic fault,
 output logic [CREDIT_BITS-1:0] free_bytes,
 output logic [$clog2(MO+1)-1:0] outstanding_count
);
 logic [MO-1:0] active;logic [12:0] reservation[MO];
 logic found,retire_ok;logic [CREDIT_BITS:0] available,next_credit;
 assign retire_ready=(int'(retire_id)<MO) ? active[retire_id] : 1'b0;
 assign retire_ok=retire_valid&&retire_ready;
 always_comb begin
  available={1'b0,free_bytes};
  if(retire_ok)available=available+(CREDIT_BITS+1)'(reservation[retire_id]);
  found=0;issue_id=0;outstanding_count=0;
  for(integer i=0;i<MO;i=i+1)begin
   if(active[i])outstanding_count=outstanding_count+1'b1;
   if(!found && (!active[i]||(retire_ok&&int'(retire_id)==i)))begin found=1;issue_id=ID_BITS'(i);end
  end
  issue_ready=found&&issue_bytes!=0&&available>=(CREDIT_BITS+1)'(issue_bytes);
  next_credit=available;
  if(issue_valid&&issue_ready)next_credit=available-(CREDIT_BITS+1)'(issue_bytes);
 end
 always_ff @(posedge clk)begin
  if(reset)begin active<=0;free_bytes<=CREDIT_BITS'(BUFFER_BYTES);fault<=0;end
  else begin
   free_bytes<=next_credit[CREDIT_BITS-1:0];
   if(retire_valid&&!retire_ready)fault<=1;
   if(retire_ok)active[retire_id]<=0;
   if(issue_valid&&issue_ready)begin active[issue_id]<=1;reservation[issue_id]<=issue_bytes;end
  end
 end
endmodule
