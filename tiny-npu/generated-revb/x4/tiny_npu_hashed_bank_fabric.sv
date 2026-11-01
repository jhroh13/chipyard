// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
// One region. Physical bank requests feed 1RW SRAMs; responses/credits are external.
// SFR0: enable bit0, row-shift bits12:8. SFR8: monitor enable bit0.
// Mapping writes block ingress and await all queues+external read returns idle,
// AND layout_change_safe (data invalidated/repacked by the owning job manager).
module tiny_npu_hashed_bank_fabric #(
 parameter integer PORTS=8,BANKS=8,DEPTH=2,DATA_BITS=256,ROW_BITS=10,TAG_BITS=16,
 parameter bit DEFAULT_HASH_ENABLE=1,DEFAULT_MONITOR_ENABLE=1,
 parameter integer DEFAULT_HASH_SHIFT=2,BANK_BITS=(BANKS>1?$clog2(BANKS):1)
)(
 input logic clk,reset,
 input logic [PORTS-1:0] req_valid,output logic [PORTS-1:0] req_ready,
 input logic [BANK_BITS-1:0] req_bank[PORTS],input logic [ROW_BITS-1:0] req_row[PORTS],
 input logic [PORTS-1:0] req_write,input logic [DATA_BITS-1:0] req_data[PORTS],
 input logic [DATA_BITS/8-1:0] req_mask[PORTS],input logic [TAG_BITS-1:0] req_tag[PORTS],
 output logic [BANKS-1:0] bank_valid,input logic [BANKS-1:0] bank_ready,
 output logic [ROW_BITS-1:0] bank_row[BANKS],output logic [BANKS-1:0] bank_write,
 output logic [DATA_BITS-1:0] bank_data[BANKS],output logic [DATA_BITS/8-1:0] bank_mask[BANKS],
 output logic [TAG_BITS-1:0] bank_tag[BANKS],
 input logic returns_idle,layout_change_safe,
 input logic sfr_valid,sfr_write,input logic [3:0] sfr_addr,input logic [31:0] sfr_wdata,
 output logic sfr_ready,sfr_error,output logic [31:0] sfr_rdata,
 output logic cfg_hash_enable,cfg_monitor_enable,output logic [4:0] cfg_hash_shift,
 output logic [PORTS-1:0] stall_no_credit,output logic [BANKS-1:0] bank_contention,
 output logic idle
);
 localparam integer PAYLOAD_BITS=1+DATA_BITS+DATA_BITS/8+TAG_BITS;
 logic [PORTS-1:0] map_ready,map_valid,map_idle,voq_ready;
 logic [BANK_BITS-1:0] mapped_bank[PORTS];logic [ROW_BITS-1:0] mapped_row[PORTS];
 logic [PAYLOAD_BITS-1:0] input_payload[PORTS],mapped_payload[PORTS];
 logic [PORTS-1:0] mapped_write;logic [DATA_BITS-1:0] mapped_data[PORTS];
 logic [DATA_BITS/8-1:0] mapped_mask[PORTS];logic [TAG_BITS-1:0] mapped_tag[PORTS];
 logic voq_idle,block_ingress;
 assign block_ingress=sfr_valid&&sfr_write&&(sfr_addr==0);
 assign req_ready=map_ready&{PORTS{!block_ingress}};
 assign idle=(&map_idle)&&voq_idle&&returns_idle;
 assign sfr_error=(sfr_addr>1)||(sfr_write&&sfr_addr==0&&(integer'(sfr_wdata[12:8])>=ROW_BITS));
 assign sfr_ready=!reset&&(!(sfr_write&&sfr_addr==0)||(idle&&layout_change_safe)||sfr_error);
 always_comb begin
  sfr_rdata='0;
  case(sfr_addr)
   0:begin sfr_rdata[0]=cfg_hash_enable;sfr_rdata[12:8]=cfg_hash_shift;end
   1:begin sfr_rdata[0]=cfg_monitor_enable;sfr_rdata[1]=idle;sfr_rdata[2]=layout_change_safe;end
   default:begin end
  endcase
 end
 always_ff @(posedge clk)begin
  if(reset)begin cfg_hash_enable<=DEFAULT_HASH_ENABLE;cfg_hash_shift<=5'(DEFAULT_HASH_SHIFT);cfg_monitor_enable<=DEFAULT_MONITOR_ENABLE;end
  else if(sfr_valid&&sfr_ready&&sfr_write&&!sfr_error)case(sfr_addr)
   0:begin cfg_hash_enable<=sfr_wdata[0];cfg_hash_shift<=sfr_wdata[12:8];end
   1:cfg_monitor_enable<=sfr_wdata[0];
   default:begin end
  endcase
 end
 for(genvar p=0;p<PORTS;p++)begin:g_mapper
  assign input_payload[p]={req_write[p],req_data[p],req_mask[p],req_tag[p]};
  assign {mapped_write[p],mapped_data[p],mapped_mask[p],mapped_tag[p]}=mapped_payload[p];
  tiny_npu_bank_hash #(.BANKS(BANKS),.ROW_BITS(ROW_BITS),.PAYLOAD_BITS(PAYLOAD_BITS)) mapper(
   .clk,.reset,.cfg_enable(cfg_hash_enable),.cfg_shift(cfg_hash_shift),
   .in_valid(req_valid[p]&&!block_ingress),.in_ready(map_ready[p]),.in_bank(req_bank[p]),.in_row(req_row[p]),.in_payload(input_payload[p]),
   .out_valid(map_valid[p]),.out_ready(voq_ready[p]),.out_bank(mapped_bank[p]),.out_row(mapped_row[p]),.out_payload(mapped_payload[p]),.idle(map_idle[p]));
 end
 tiny_npu_bank_voq #(.PORTS(PORTS),.BANKS(BANKS),.DEPTH(DEPTH),.DATA_BITS(DATA_BITS),.ROW_BITS(ROW_BITS),.TAG_BITS(TAG_BITS)) voq(
 .clk,.reset,.req_valid(map_valid),.req_ready(voq_ready),.req_bank(mapped_bank),.req_row(mapped_row),.req_write(mapped_write),.req_data(mapped_data),.req_mask(mapped_mask),.req_tag(mapped_tag),
 .bank_valid,.bank_ready,.bank_row,.bank_write,.bank_data,.bank_mask,.bank_tag,.stall_no_credit,.bank_contention,.idle(voq_idle));
 initial if(DEFAULT_HASH_SHIFT<0||DEFAULT_HASH_SHIFT>=ROW_BITS)$fatal(1,"Invalid default row hash shift");
endmodule
