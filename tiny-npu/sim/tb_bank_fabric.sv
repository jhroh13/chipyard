`timescale 1ps/1ps
module tb_bank_fabric;
 parameter integer HASH=1,LATENCY=16,CONSUMER_STALL=0,BANKS=8,PORTS=8,COUNT=64;
 localparam integer BB=$clog2(BANKS),TOTAL=PORTS*COUNT;
 logic clk=0,reset=1;always #500 clk=~clk;
 logic [PORTS-1:0] req_valid=0,req_ready,req_write,stall_no_credit;
 logic [BB-1:0] req_bank[PORTS];logic [11:0] req_row[PORTS];logic [255:0] req_data[PORTS];logic [31:0] req_mask[PORTS];logic [15:0] req_tag[PORTS];
 logic [BANKS-1:0] bank_valid,bank_ready,bank_write,bank_contention,rsp_valid,rsp_ready;
 logic [11:0] bank_row[BANKS];logic [255:0] bank_data[BANKS],rsp_data[BANKS];logic [31:0] bank_mask[BANKS];logic [15:0] bank_tag[BANKS];
 logic returns_idle,layout_change_safe=1,sfr_valid=0,sfr_write=0,sfr_ready,sfr_error,idle,cfg_hash_enable,cfg_monitor_enable;
 logic [4:0] cfg_hash_shift;logic [3:0] sfr_addr=0;logic [31:0] sfr_wdata=0,sfr_rdata;
 integer seq[PORTS],phase=-1,phase_issued=0,cycles=0,first_cycle=-1,last_cycle=0,pending_reads=0;
 integer accepted_count=0,issued_count=0,read_count=0,no_credit_cycles=0,contention_cycles=0,blocked_cycles=0,response_blocked_cycles=0;
 integer first_seen[3*TOTAL],bank_count[BANKS];logic accepted[3*TOTAL],issued[3*TOTAL];
 logic [255:0] read_expected[BANKS][LATENCY];logic [LATENCY-1:0] expected_valid[BANKS];
 logic held[BANKS];logic [316:0] saved_packet[BANKS];integer fd,independent_progress=0;
 tiny_npu_hashed_bank_fabric #(.PORTS(PORTS),.BANKS(BANKS),.ROW_BITS(12)) dut(.*);
 for(genvar b=0;b<BANKS;b++)begin:g_mem
  tiny_npu_sram_1rw_subbank #(.READ_LATENCY(LATENCY),.DEPTH(4096)) mem(.clk,.reset,.cmd_valid(bank_valid[b]),.cmd_ready(bank_ready[b]),.cmd_write(bank_write[b]),.cmd_addr(bank_row[b]),.cmd_data(bank_data[b]),.cmd_mask(bank_mask[b]),.rsp_valid(rsp_valid[b]),.rsp_ready(rsp_ready[b]),.rsp_data(rsp_data[b]));
 end
 assign returns_idle=(pending_reads==0);
 function automatic logic [255:0] value_for(input integer row);
  value_for=256'hcafe0000+256'(row);
 endfunction
 always @(posedge clk)begin
  cycles=cycles+1;
  if(reset)begin for(integer b=0;b<BANKS;b++)begin expected_valid[b]='0;held[b]=0;end end
  else begin
   for(integer p=0;p<PORTS;p++)begin
    if(req_valid[p]&&req_ready[p])begin
     if(accepted[integer'(req_tag[p])])$fatal(1,"duplicate input tag");accepted[integer'(req_tag[p])]=1;first_seen[integer'(req_tag[p])]=cycles;accepted_count++;seq[p]++;
     if(first_cycle<0)first_cycle=cycles;
    end
    if(cfg_monitor_enable)begin
     if(stall_no_credit[p])no_credit_cycles++;
     $fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":1000,\"channel\":\"fabric.port%0d\",\"valid\":%0d,\"ready\":%0d,\"active\":1,\"stall_mask\":%0d}\n",$time,p,req_valid[p],req_ready[p],req_valid[p]&&!req_ready[p]?2:0);
    end
   end
   if(rsp_valid[0]&&!rsp_ready[0])for(integer b=1;b<BANKS;b++)if((bank_valid[b]&&bank_ready[b])||(rsp_valid[b]&&rsp_ready[b]))independent_progress++;
   for(integer b=0;b<BANKS;b++)begin
    logic [316:0] packet;integer tag,row,linear_id,expected_bank;
    packet={bank_row[b],bank_write[b],bank_data[b],bank_mask[b],bank_tag[b]};
    if(held[b]&&(!bank_valid[b]||packet!==saved_packet[b]))$fatal(1,"packet changed under SRAM stall");
    held[b]=bank_valid[b]&&!bank_ready[b];saved_packet[b]=packet;
    if(rsp_valid[b]!==expected_valid[b][LATENCY-1])$fatal(1,"response validity mismatch");
    if(rsp_valid[b])begin
     if(rsp_data[b]!==read_expected[b][LATENCY-1])$fatal(1,"SRAM read data mismatch bank=%0d",b);
     if(rsp_ready[b])begin pending_reads--;read_count++;last_cycle=cycles;end
    end
    if(bank_ready[b])begin
     for(integer st=LATENCY-1;st>0;st--)begin expected_valid[b][st]=expected_valid[b][st-1];read_expected[b][st]=read_expected[b][st-1];end
     expected_valid[b][0]=bank_valid[b]&&!bank_write[b];
     if(bank_valid[b])read_expected[b][0]=value_for(integer'(bank_row[b]));
    end
    if(bank_valid[b]&&bank_ready[b])begin
     tag=integer'(bank_tag[b]);row=integer'(bank_row[b]);linear_id=tag%TOTAL;
     expected_bank=(HASH!=0)?((row>>2)%BANKS):0;
     if(!accepted[tag]||issued[tag]||row!=linear_id*4||b!=expected_bank||bank_write[b]!=((tag<TOTAL)||((tag>=2*TOTAL)&&((linear_id%PORTS)%2==1))))$fatal(1,"issue routing/tag/order mismatch");
     if(bank_data[b]!==value_for(row)||bank_mask[b]!==32'hffffffff)$fatal(1,"write payload corrupted");
     issued[tag]=1;issued_count++;phase_issued++;bank_count[b]++;
     if(bank_write[b])last_cycle=cycles;else pending_reads++;
    end
    if(cfg_monitor_enable)begin
     if(bank_contention[b])contention_cycles++;
     if(bank_valid[b]&&!bank_ready[b])blocked_cycles++;
     if(rsp_valid[b]&&!rsp_ready[b])response_blocked_cycles++;
     $fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":1000,\"channel\":\"fabric.bank%0d.command\",\"valid\":%0d,\"ready\":%0d,\"active\":1,\"bytes\":32,\"stall_mask\":%0d}\n",$time,b,bank_valid[b],bank_ready[b],bank_valid[b]&&!bank_ready[b]?16:0);
     $fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":1000,\"channel\":\"fabric.bank%0d.response\",\"valid\":%0d,\"ready\":%0d,\"active\":1,\"bytes\":32,\"stall_mask\":%0d}\n",$time,b,rsp_valid[b],rsp_ready[b],rsp_valid[b]&&!rsp_ready[b]?16:0);
     $fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":1000,\"channel\":\"fabric.bank%0d.arbiter\",\"valid\":1,\"ready\":%0d,\"active\":%0d,\"stall_mask\":%0d}\n",$time,b,!bank_contention[b],bank_valid[b],bank_contention[b]?4:0);
    end
   end
  end
 end
 task automatic run_phase(input integer which);
  integer timeout;
  begin
   @(negedge clk);phase=which;phase_issued=0;first_cycle=-1;last_cycle=0;for(integer p=0;p<PORTS;p++)seq[p]=0;
   timeout=0;
   while(phase_issued<TOTAL||!idle)begin
    for(integer p=0;p<PORTS;p++)begin
     req_valid[p]=(seq[p]<COUNT);req_bank[p]='0;req_row[p]=12'((seq[p]*PORTS+p)*4);req_write[p]=(which==0)||((which==2)&&(p%2==1));
     req_data[p]=value_for(integer'(req_row[p]));req_mask[p]='1;req_tag[p]=16'(which*TOTAL+seq[p]*PORTS+p);
    end
    for(integer b=0;b<BANKS;b++)rsp_ready[b]=(CONSUMER_STALL==0)||((CONSUMER_STALL==2)&&(b!=0))||((cycles%23)<13);
    @(negedge clk);timeout++;if(timeout>10000)$fatal(1,"deadlock");
   end
   req_valid='0;
   $display("FABRIC_PHASE hash=%0d latency=%0d consumer_stall=%0d phase=%0d commands=%0d elapsed_cycles=%0d",HASH,LATENCY,CONSUMER_STALL,which,TOTAL,cycles-first_cycle+1);
  end
 endtask
 initial begin
  fd=$fopen("fabric_trace.jsonl","w");$fwrite(fd,"{\"type\":\"meta\",\"schema_version\":1,\"provenance\":{\"source\":\"actual hash+VOQ+arbiter+single-port SRAM RTL; no Rocket or MAC execution\"}}\n");
  for(integer t=0;t<3*TOTAL;t++)begin accepted[t]=0;issued[t]=0;end
  for(integer b=0;b<BANKS;b++)bank_count[b]=0;
  rsp_ready='1;repeat(4)@(negedge clk);reset=0;
  if(!cfg_hash_enable||!cfg_monitor_enable||cfg_hash_shift!=2)$fatal(1,"default hash/monitor config");
  if(HASH==0)begin
   sfr_valid=1;sfr_write=1;sfr_addr=0;sfr_wdata=32'h200;
   @(posedge clk);if(!sfr_ready||sfr_error)$fatal(1,"SFR selection failed");@(negedge clk);sfr_valid=0;
  end
  if(cfg_hash_enable!=1'(HASH))$fatal(1,"SFR readback mismatch");
  layout_change_safe=0;run_phase(0);run_phase(1);run_phase(2);
  // Idle alone does not permit relocating a live memory image.
  sfr_valid=1;sfr_write=1;sfr_addr=0;sfr_wdata=(HASH!=0)?32'h200:32'h201;
  repeat(4)begin @(negedge clk);if(sfr_ready||cfg_hash_enable!=1'(HASH))$fatal(1,"unsafe layout switch accepted");end
  layout_change_safe=1;@(posedge clk);if(!sfr_ready)$fatal(1,"safe layout switch rejected");@(negedge clk);sfr_valid=0;
  if(cfg_hash_enable==1'(HASH))$fatal(1,"safe layout config did not change");
  if(accepted_count!=3*TOTAL||issued_count!=3*TOTAL||read_count!=TOTAL+TOTAL/2)$fatal(1,"lost/duplicated transaction");
  if(HASH!=0&&CONSUMER_STALL==2&&independent_progress==0)$fatal(1,"unrelated banks did not make progress");
  $display("INDEPENDENT_BANK_PROGRESS samples=%0d",independent_progress);
  $display("BANK_FABRIC_PASS accepted=%0d issued=%0d reads=%0d contention_samples=%0d no_credit_samples=%0d bank_blocked_samples=%0d response_blocked_samples=%0d",accepted_count,issued_count,read_count,contention_cycles,no_credit_cycles,blocked_cycles,response_blocked_cycles);
  for(integer b=0;b<BANKS;b++)$display("BANK_COUNT bank=%0d commands=%0d",b,bank_count[b]);
  $fclose(fd);$finish;
 end
endmodule
