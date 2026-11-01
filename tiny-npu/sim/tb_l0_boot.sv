`timescale 1ps/1ps
// Qualification fixture, not a production TL manager. Payload is held by the
// single-outstanding test driver while the real guard pipelines its metadata.
module tb_l0_boot;
 parameter integer GUARD_LATENCY=5,READ_LATENCY=16,RELEASE_STAGES=2,HART_HALF_PERIOD=700;
 localparam integer TOTAL=10485760,BASE=10223616,CODE_LIMIT=10354688,WORDS=8192;
 logic clk=0,reset=1;always #500 clk=~clk;
 logic hart_clk=0,hold_harts=1;always #(HART_HALF_PERIOD) hart_clk=~hart_clk;
 logic [7:0] hart_reset;logic [63:0] reset_vector;logic preload_enable,harts_held_ack;
 logic req_valid=0,req_ready,req_write=0;logic [1:0] req_owner=0;logic [7:0] req_hart=0,req_tag=0;
 logic [23:0] req_addr=0;logic [12:0] req_bytes=32;
 logic out_valid,out_ready,out_allow,out_write;logic [2:0] out_error;logic [1:0] out_owner;logic [7:0] out_hart,out_tag;logic [12:0] out_bytes;logic [23:0] out_addr;
 logic image_verified=0,rw_initialized=0,preload_idle=0,commit_valid=0,commit_ready,commit_error,boot_ready;
 logic [255:0] held_data=0;logic [31:0] held_mask='1;
 logic [7:0] cmd_valid,cmd_ready,rsp_valid,rsp_ready;logic [255:0] rsp_data[8];logic [9:0] cmd_addr;
 logic cmd_write;integer selected_bank,word_index;
 logic [255:0] image[4096],shadow[WORDS];integer cycles=0,checks=0,reads=0,writes=0,denied=0,txn_number=0;
 logic trace_on=0;integer fd;
 tiny_npu_preloaded_boot #(.LATENCY(GUARD_LATENCY),.RELEASE_STAGES(RELEASE_STAGES)) boot(.fabric_reset(reset),.*);
 always_comb begin
  word_index=(integer'(out_addr)-BASE)/32;selected_bank=word_index%8;cmd_addr=10'(word_index/8);cmd_valid=0;cmd_write=out_write;
  out_ready=1;
  if(out_valid&&out_allow&&out_owner!=3&&integer'(out_addr)>=BASE)begin
   if(selected_bank>=0&&selected_bank<8)begin cmd_valid[selected_bank]=1;out_ready=cmd_ready[selected_bank];end
  end
 end
 for(genvar b=0;b<8;b++)begin:g_sram
  tiny_npu_sram_1rw_subbank #(.WIDTH(256),.DEPTH(1024),.READ_LATENCY(READ_LATENCY)) memory(
  .clk,.reset,.cmd_valid(cmd_valid[b]),.cmd_ready(cmd_ready[b]),.cmd_write,.cmd_addr,.cmd_data(held_data),.cmd_mask(held_mask),.rsp_valid(rsp_valid[b]),.rsp_ready(rsp_ready[b]),.rsp_data(rsp_data[b]));
 end
 always @(posedge clk)cycles<=cycles+1;
 always @(posedge clk)if(!reset&&trace_on)begin
  for(integer h=0;h<8;h++)$fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":1000,\"channel\":\"rocket%0d.reset_release\",\"valid\":%0d,\"ready\":%0d,\"active\":1,\"reset_pc\":%0d}\n",$time,h,!hold_harts,!hart_reset[h],reset_vector);
  $fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":1000,\"channel\":\"boot.request\",\"valid\":%0d,\"ready\":%0d,\"active\":1,\"owner\":%0d,\"hart\":%0d,\"address\":%0d}\n",$time,req_valid,req_ready,req_owner,req_hart,req_addr);
  $fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":1000,\"channel\":\"boot.guard_result\",\"valid\":%0d,\"ready\":%0d,\"active\":1,\"allow\":%0d,\"error\":%0d}\n",$time,out_valid,out_ready,out_allow,out_error);
  $fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":1000,\"channel\":\"boot.release\",\"valid\":%0d,\"ready\":%0d,\"active\":1}\n",$time,commit_valid,commit_ready);
  for(integer b=0;b<8;b++)$fwrite(fd,"{\"type\":\"sample\",\"time_ps\":%0d,\"period_ps\":1000,\"channel\":\"boot.bank%0d.read_response\",\"valid\":%0d,\"ready\":%0d,\"active\":%0d,\"bytes\":32}\n",$time,b,rsp_valid[b],rsp_ready[b],boot_ready);
 end
 task automatic send(input integer owner,hart,write_bit,address,length,allow_expected,error_expected,input logic [255:0] data,input logic [31:0] mask,input bit stall_response);
  integer start_cycle,bank,word,read_start,present_cycle;logic [255:0] saved;
  begin
   if(owner==0&&hart_reset!=8'hff)$fatal(1,"preload while CPU running");
   @(negedge clk);req_valid=1;req_owner=2'(owner);req_hart=8'(hart);req_tag=8'(txn_number);req_write=1'(write_bit);req_addr=24'(address);req_bytes=13'(length);held_data=data;held_mask=mask;
   @(posedge clk);while(!req_ready)@(posedge clk);start_cycle=cycles;
   @(negedge clk);req_valid=0;
   while(!out_valid)@(negedge clk);
   if(out_allow!=1'(allow_expected)||out_error!=3'(error_expected)||out_addr!=24'(address)||out_owner!=2'(owner)||out_hart!=8'(hart)||out_tag!=8'(txn_number)||out_bytes!=13'(length))$fatal(1,"guard mismatch seq=%0d owner=%0d addr=%h allow=%b err=%0d",txn_number,owner,address,out_allow,out_error);
   bank=((address-BASE)/32)%8;word=(address-BASE)/32;
   if((allow_expected!=0)&&owner!=3&&(write_bit==0)&&stall_response)rsp_ready[bank]=0;
   @(posedge clk);while(!out_ready)@(posedge clk);
   if(cycles-start_cycle!=GUARD_LATENCY)$fatal(1,"guard latency mismatch");
   read_start=cycles;checks++;if(allow_expected==0)denied++;
   if((allow_expected!=0)&&owner!=3&&(write_bit!=0))begin
    for(integer byte_no=0;byte_no<32;byte_no++)if(mask[byte_no])shadow[word][byte_no*8+:8]=data[byte_no*8+:8];writes++;
   end
   @(negedge clk);
   if((allow_expected!=0)&&owner!=3&&(write_bit==0))begin
    while(!rsp_valid[bank])@(negedge clk);
    present_cycle=cycles;
    if(present_cycle-read_start!=READ_LATENCY)$fatal(1,"SRAM latency mismatch got=%0d expected=%0d",present_cycle-read_start,READ_LATENCY);
    saved=rsp_data[bank];if(saved!==shadow[word])$fatal(1,"SRAM data mismatch word=%0d",word);
    if(stall_response)begin repeat(3)begin @(negedge clk);if(!rsp_valid[bank]||rsp_data[bank]!==saved)$fatal(1,"read changed under stall");end rsp_ready[bank]=1;end
    @(posedge clk);@(negedge clk);reads++;
   end
   txn_number++;
  end
 endtask
 initial begin
  fd=$fopen("boot_trace.jsonl","w");$fwrite(fd,"{\"type\":\"meta\",\"schema_version\":1,\"guard_cycles\":%0d,\"read_cycles\":%0d,\"provenance\":{\"source\":\"external SRAM preload with Rocket held-reset +8 single-port subbanks; synthetic fetches, not Rocket RTL\"}}\n",GUARD_LATENCY,READ_LATENCY);
  $readmemh("boot_words.hex",image);rsp_ready='1;
  for(integer i=0;i<WORDS;i++)shadow[i]='x;
  repeat(4)@(negedge clk);reset=0;
  req_owner=0;req_valid=1;
  while(!preload_enable)begin if(req_ready)$fatal(1,"preload accepted before reset acknowledgment");@(negedge clk);end
  req_valid=0;
  // Even an early external reset release cannot execute an uncommitted image.
  hold_harts=0;repeat(3)@(negedge hart_clk);if(hart_reset!=8'hff)$fatal(1,"uninitialized image escaped reset");hold_harts=1;

  trace_on=1;
  send(1,0,0,BASE,32,0,3,0,'1,0); // fetch before image commit
  send(0,0,1,BASE-32,32,0,4,0,'1,0); // loader cannot overwrite payload
  // Commit must wait for both verification and explicit RW initialization.
  @(negedge clk);commit_valid=1;preload_idle=1;repeat(3)@(negedge clk);if(commit_ready||boot_ready)$fatal(1,"released uninitialized code");commit_valid=0;preload_idle=0;
  trace_on=0;
  for(integer i=0;i<WORDS;i++)begin
   if(i>=WORDS-16)trace_on=1;
   send(0,0,1,BASE+i*32,32,1,0,i<4096?image[i]:256'b0,'1,0);
  end
  image_verified=1;rw_initialized=1;
  // Even with a verified image, release waits for all physical loader writes.
  @(negedge clk);commit_valid=1;repeat(3)@(negedge clk);if(commit_ready||boot_ready)$fatal(1,"released before loader idle");preload_idle=1;
  @(posedge clk);if(hart_reset!=8'hff)$fatal(1,"harts escaped reset during preload");if(!commit_ready||commit_error)$fatal(1,"commit not accepted");@(negedge clk);commit_valid=0;if(!boot_ready)$fatal(1,"no boot release");
  if(hart_reset!=8'hff||preload_enable||reset_vector!=64'h609c0000)$fatal(1,"bad sealed reset state/vector");
  // No ROM: external reset release directly selects the SRAM reset PC.
  @(negedge hart_clk);hold_harts=0;
  for(integer i=0;i<RELEASE_STAGES;i++)begin
   @(posedge hart_clk);#1;
   if(hart_reset!=(i==RELEASE_STAGES-1?8'h00:8'hff))$fatal(1,"reset deassert latency");
  end
  for(integer h=0;h<8;h++)begin
   send(1,h,0,BASE,32,1,0,0,'1,1); // every hart fetches real code at common entry
   send(1,h,0,BASE+(h%6)*32,32,1,0,0,'1,0);
   send(2,h,1,CODE_LIMIT+(h+1)*8192-8,8,1,0,(256'h12340000+256'(h))<<192,32'hff000000,0);
   send(2,h,0,CODE_LIMIT+(h+1)*8192-8,8,1,0,0,'1,0);
  end
  send(2,0,1,BASE,32,0,4,0,'1,0); // code sealed even against CPU stores
  @(negedge clk);req_owner=0;req_valid=1;req_write=1;req_addr=24'(BASE);
  repeat(3)begin @(negedge clk);if(req_ready||preload_enable)$fatal(1,"external preload reopened after seal");end req_valid=0;
  send(3,0,1,BASE,32,0,4,0,'1,0); // payload DMA cannot clobber firmware
  send(3,0,1,BASE-16,32,0,4,0,'1,0); // burst crossing payload/boot boundary
  send(1,0,0,CODE_LIMIT-16,32,0,4,0,'1,0); // fetch crossing executable limit
  send(1,8,0,BASE,32,0,2,0,'1,0); // invalid hart
  send(2,0,0,0,32,0,4,0,'1,0); // CPU cannot use payload path
  send(3,0,1,0,32,1,0,0,'1,0); // payload region remains available
  send(3,0,1,TOTAL-16,32,0,1,0,'1,0); // end-of-L0 overflow
  send(3,0,1,32'h00fffff0,4096,0,1,0,'1,0);
  send(1,0,0,BASE,0,0,1,0,'1,0);
  @(negedge clk);commit_valid=1;@(posedge clk);if(!commit_ready||!commit_error)$fatal(1,"repeat commit not rejected");@(negedge clk);commit_valid=0;
  // A CPU-only reset leaves SRAM bytes, permission seal and fabric alive.
  @(negedge hart_clk);hold_harts=1;#1;if(hart_reset!=8'hff)$fatal(1,"reset assertion not asynchronous");
  repeat(3)@(negedge clk);if(!boot_ready||preload_enable)$fatal(1,"CPU reset lost seal");
  @(negedge hart_clk);hold_harts=0;repeat(RELEASE_STAGES)@(posedge hart_clk);#1;
  if(hart_reset!=0)$fatal(1,"CPU restart failed");
  send(1,0,0,BASE,32,1,0,0,'1,1);
  $display("PRELOADED_SRAM_RESET_PASS entry=%h release_stages=%0d hart_half_period=%0d",reset_vector,RELEASE_STAGES,HART_HALF_PERIOD);
  $display("L0_BOOT_RTL_PASS guard=%0d read=%0d checks=%0d reads=%0d writes=%0d denied=%0d harts=8",GUARD_LATENCY,READ_LATENCY,checks,reads,writes,denied);$fclose(fd);$finish;
 end
endmodule
