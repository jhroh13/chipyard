// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
// Local-byte-offset request protection. Ingress wiring supplies owner/hart;
// software/NPU payloads must never be allowed to forge these identities.
// Five real pipeline stages; LATENCY>5 adds response transport only.
module tiny_npu_l0_boot_guard #(
 parameter integer ADDR_BITS=24,HARTS=8,LATENCY=5,TAG_BITS=8,
 parameter logic [ADDR_BITS:0] TOTAL_BYTES=25'd10485760,
 parameter logic [ADDR_BITS:0] BOOT_BASE=25'h9c0000,CODE_LIMIT=25'h9e0000
)(
 input logic clk,reset,
 input logic req_valid,output logic req_ready,input logic [1:0] req_owner,
 input logic [7:0] req_hart,input logic [TAG_BITS-1:0] req_tag,input logic req_write,
 input logic [ADDR_BITS-1:0] req_addr,input logic [12:0] req_bytes,
 output logic out_valid,input logic out_ready,output logic out_allow,
 output logic [2:0] out_error,output logic [1:0] out_owner,
 output logic [7:0] out_hart,output logic [TAG_BITS-1:0] out_tag,output logic [12:0] out_bytes,output logic out_write,
 output logic [ADDR_BITS-1:0] out_addr,
 input logic image_verified,rw_initialized,loader_idle,commit_valid,
 output logic commit_ready,commit_error,boot_ready
);
 // Owners:0=trusted loader,1=instruction fetch,2=CPU/control data,3=NPU payload.
 // Errors:0=none,1=range/length,2=hart,3=not ready,4=protected,5=loader locked.
 typedef struct packed {logic [1:0] owner;logic [7:0] hart;logic write_bit;logic [ADDR_BITS-1:0] addr;logic [12:0] count_minus1,byte_count;logic [TAG_BITS-1:0] tag;logic bad;} s1_t;
 typedef struct packed {s1_t request;logic [16:0] low_sum;} s2_t;
 typedef struct packed {s1_t request;logic [ADDR_BITS:0] last_byte;} s3_t;
 typedef struct packed {logic allow_bit;logic [TAG_BITS-1:0] tag;logic [12:0] byte_count;logic [2:0] error_code;logic [1:0] owner;logic [7:0] hart;logic write_bit;logic [ADDR_BITS-1:0] addr;} result_t;
 s1_t s1,d1;s2_t s2,d2;s3_t s3,d3;result_t s4,d4,selected_reply;logic [ADDR_BITS+TAG_BITS+27:0] reply[0:LATENCY-5];
 logic [LATENCY-1:0] valid_pipe;logic advance;logic [ADDR_BITS-16:0] high_sum;
 assign advance=!valid_pipe[LATENCY-1]||out_ready;
 assign req_ready=advance&&!reset&&!commit_valid;
 assign commit_ready=!reset&&(valid_pipe==0)&&loader_idle&&(boot_ready||(image_verified&&rw_initialized));
 assign commit_error=boot_ready;
 always_ff @(posedge clk)begin
  if(reset)boot_ready<=0;
  else if(commit_valid&&commit_ready&&!boot_ready)boot_ready<=1;
 end
 always_comb begin
  d1.owner=req_owner;d1.hart=req_hart;d1.write_bit=req_write;d1.addr=req_addr;
  d1.tag=req_tag;d1.byte_count=req_bytes;d1.count_minus1=req_bytes-13'd1;d1.bad=(req_bytes==0)||(req_bytes>4096);
  d2.request=s1;d2.low_sum={1'b0,s1.addr[15:0]}+{4'b0,s1.count_minus1};
  high_sum={1'b0,s2.request.addr[ADDR_BITS-1:16]}+{{(ADDR_BITS-16){1'b0}},s2.low_sum[16]};
  d3.request=s2.request;d3.last_byte={high_sum,s2.low_sum[15:0]};
  d4='0;d4.tag=s3.request.tag;d4.byte_count=s3.request.byte_count;d4.owner=s3.request.owner;d4.hart=s3.request.hart;d4.write_bit=s3.request.write_bit;d4.addr=s3.request.addr;
  if(s3.request.bad||s3.last_byte>=TOTAL_BYTES||{1'b0,s3.request.addr}>=TOTAL_BYTES)d4.error_code=1;
  else if((s3.request.owner==1||s3.request.owner==2)&&integer'(s3.request.hart)>=HARTS)d4.error_code=2;
  else case(s3.request.owner)
   0:begin
    if(boot_ready)d4.error_code=5;
    else if({1'b0,s3.request.addr}<BOOT_BASE)d4.error_code=4;
    else d4.allow_bit=1;
   end
   1:begin
    if(!boot_ready)d4.error_code=3;
    else if(s3.request.write_bit||{1'b0,s3.request.addr}<BOOT_BASE||s3.last_byte>=CODE_LIMIT)d4.error_code=4;
    else d4.allow_bit=1;
   end
   2:begin
    if(!boot_ready)d4.error_code=3;
    else if({1'b0,s3.request.addr}<BOOT_BASE||(s3.request.write_bit&&{1'b0,s3.request.addr}<CODE_LIMIT))d4.error_code=4;
    else d4.allow_bit=1;
   end
   3:begin
    if(s3.last_byte>=BOOT_BASE)d4.error_code=4;
    else d4.allow_bit=1;
   end
  endcase
 end
 assign selected_reply=reply[LATENCY-5];
 assign out_valid=valid_pipe[LATENCY-1];assign out_allow=selected_reply.allow_bit;
 assign out_tag=selected_reply.tag;assign out_bytes=selected_reply.byte_count;
 assign out_error=selected_reply.error_code;assign out_owner=selected_reply.owner;
 assign out_hart=selected_reply.hart;assign out_write=selected_reply.write_bit;assign out_addr=selected_reply.addr;
 always_ff @(posedge clk)begin
  if(reset)valid_pipe<=0;
  else if(advance)begin
   valid_pipe[0]<=req_valid&&req_ready;
   for(integer i=1;i<LATENCY;i++)valid_pipe[i]<=valid_pipe[i-1];
   if(req_valid&&req_ready)s1<=d1;
   if(valid_pipe[0])s2<=d2;
   if(valid_pipe[1])s3<=d3;
   if(valid_pipe[2])s4<=d4;
   if(valid_pipe[3])reply[0]<=s4;
  end
 end
 for(genvar i=1;i<=LATENCY-5;i++)begin:g_transport
  always_ff @(posedge clk)if(!reset&&advance&&valid_pipe[i+3])reply[i]<=reply[i-1];
 end
 initial if(ADDR_BITS<17||LATENCY<5)$fatal(1,"Invalid boot guard configuration");
endmodule
