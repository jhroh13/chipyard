// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
// One region's command fabric. Explicit physical-bank/row decoder is upstream.
// Per-ingress/per-bank VOQs prevent an already-enqueued bank0 request from
// blocking that ingress's bank1 queue. Upstream must expose or schedule traffic
// for independent banks; a single blocked upstream FIFO can still cause HOL.
// One elastic output register per bank holds data/mask/tag stable under stall.
// SRAM response routing/read credits and address/permission decoding are separate.
module tiny_npu_bank_voq #(
 parameter integer PORTS=8,BANKS=8,DEPTH=2,DATA_BITS=256,ROW_BITS=10,TAG_BITS=16,
 parameter integer BANK_BITS=(BANKS>1?$clog2(BANKS):1)
)(
 input logic clk,reset,
 input logic [PORTS-1:0] req_valid,output logic [PORTS-1:0] req_ready,
 input logic [BANK_BITS-1:0] req_bank[PORTS],
 input logic [ROW_BITS-1:0] req_row[PORTS],input logic [PORTS-1:0] req_write,
 input logic [DATA_BITS-1:0] req_data[PORTS],input logic [DATA_BITS/8-1:0] req_mask[PORTS],
 input logic [TAG_BITS-1:0] req_tag[PORTS],
 output logic [BANKS-1:0] bank_valid,input logic [BANKS-1:0] bank_ready,
 output logic [ROW_BITS-1:0] bank_row[BANKS],output logic [BANKS-1:0] bank_write,
 output logic [DATA_BITS-1:0] bank_data[BANKS],output logic [DATA_BITS/8-1:0] bank_mask[BANKS],
 output logic [TAG_BITS-1:0] bank_tag[BANKS],
 output logic [PORTS-1:0] stall_no_credit,
 output logic [BANKS-1:0] bank_contention,output logic idle
);
 localparam integer PTR_BITS=(DEPTH>1?$clog2(DEPTH):1),COUNT_BITS=$clog2(DEPTH+1),PORT_BITS=(PORTS>1?$clog2(PORTS):1);
 localparam integer PACK_BITS=ROW_BITS+1+DATA_BITS+DATA_BITS/8+TAG_BITS;
 // Explicit packed-vector storage avoids synthesis struct-array truncation.
 logic [PACK_BITS-1:0] queue[PORTS][BANKS][DEPTH],output_packet[BANKS];
 logic [PTR_BITS-1:0] head[PORTS][BANKS],tail[PORTS][BANKS];
 logic [COUNT_BITS-1:0] count[PORTS][BANKS];
 logic [PORT_BITS-1:0] rr[BANKS],winner[BANKS];
 logic [PORTS-1:0] push[BANKS],pop[BANKS];logic [BANKS-1:0] found,advance;
 always_comb begin
  req_ready='0;stall_no_credit='0;idle=!(|bank_valid);
  for(integer p=0;p<PORTS;p++)for(integer b=0;b<BANKS;b++)if(count[p][b]!=0)idle=0;
  for(integer p=0;p<PORTS;p++)begin
   for(integer b=0;b<BANKS;b++)if(integer'(req_bank[p])==b)req_ready[p]=!reset&&(integer'(count[p][b])<DEPTH);
   stall_no_credit[p]=req_valid[p]&&!req_ready[p]&&!reset;
  end
  for(integer b=0;b<BANKS;b++)begin
   integer contenders,index;
   advance[b]=!bank_valid[b]||bank_ready[b];found[b]=0;winner[b]='0;contenders=0;
   push[b]='0;pop[b]='0;
   for(integer p=0;p<PORTS;p++)begin
    push[b][p]=req_valid[p]&&req_ready[p]&&(integer'(req_bank[p])==b);
    if(count[p][b]!=0)contenders++;
   end
   bank_contention[b]=(contenders>1)&&!reset;
   begin
    logic [PORTS-1:0] occupied,masked,chosen,grant;
    occupied='0;masked='0;chosen='0;grant='0;
    for(integer p=0;p<PORTS;p++)begin
     occupied[p]=(count[p][b]!=0);masked[p]=occupied[p]&&(p>=integer'(rr[b]));
    end
    chosen=(|masked)?masked:occupied;
    for(integer p=0;p<PORTS;p++)begin
     grant[p]=chosen[p]&&((chosen & ((PORTS'(1)<<p)-1'b1))=='0);
     if(grant[p])begin found[b]=1;winner[b]=PORT_BITS'(p);end
    end
   end
   if(advance[b]&&found[b]&&!reset)pop[b][winner[b]]=1;
  end
 end
 for(genvar b=0;b<BANKS;b++)begin:g_bank
  assign {bank_row[b],bank_write[b],bank_data[b],bank_mask[b],bank_tag[b]}=output_packet[b];
  always_ff @(posedge clk)begin
   if(reset)begin bank_valid[b]<=0;rr[b]<='0;end
   else if(advance[b])begin
    bank_valid[b]<=found[b];
    if(found[b])begin
     output_packet[b]<=queue[winner[b]][b][head[winner[b]][b]];
     rr[b]<=(integer'(winner[b])==PORTS-1)?'0:winner[b]+1'b1;
    end
   end
  end
  for(genvar p=0;p<PORTS;p++)begin:g_port
   always_ff @(posedge clk)begin
    if(reset)begin count[p][b]<='0;head[p][b]<='0;tail[p][b]<='0;end
    else begin
     case({push[b][p],pop[b][p]})
      2'b10:count[p][b]<=count[p][b]+1'b1;
      2'b01:count[p][b]<=count[p][b]-1'b1;
      default:begin end
     endcase
     if(push[b][p])begin
      queue[p][b][tail[p][b]]<={req_row[p],req_write[p],req_data[p],req_mask[p],req_tag[p]};
      tail[p][b]<=(integer'(tail[p][b])==DEPTH-1)?'0:tail[p][b]+1'b1;
     end
     if(pop[b][p])head[p][b]<=(integer'(head[p][b])==DEPTH-1)?'0:head[p][b]+1'b1;
    end
   end
  end
 end
 initial if(PORTS<1||BANKS<1||DEPTH<2||DATA_BITS%8!=0)$fatal(1,"Invalid bank VOQ geometry");
endmodule
