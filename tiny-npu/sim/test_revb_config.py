#!/usr/bin/env python3
"""Config contract, invalid-input rejection, deterministic generation and RTL consumers."""
import copy,hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];ARCH=ROOT/'architecture/v2'
sys.path[:0]=[str(ARCH),str(ROOT/'tools')]
from configuration import load_profile,ConfigError,DEFAULT_CONFIG
from generate_revb import generate
from sweep_l0 import evaluate

TB='''`timescale 1ns/1ps
module tb_revb_config;
 import tiny_npu_revb_config_pkg::*;
 logic clk=0,reset=1,cmd_valid=0,cmd_write=0,rsp_ready=1;
 logic [$clog2(L0_REGIONS_0_DEPTH)-1:0] cmd_addr=0;
 logic [255:0] cmd_data=256'h1234,rsp_data;logic [31:0] cmd_mask='1;
 logic cmd_ready,rsp_valid;
 integer elapsed;
 always #5 clk=~clk;
 tiny_npu_revb_config_smoke dut(.*);
 initial begin
  repeat(3) @(negedge clk);
  reset=0;cmd_valid=1;cmd_write=1;
  @(negedge clk);if(!cmd_ready)$fatal(1,"write stalled");cmd_write=0;
  @(negedge clk);cmd_valid=0;elapsed=1;
  while(!rsp_valid)begin @(negedge clk);elapsed++;if(elapsed>1024)$fatal(1,"timeout");end
  if(elapsed!=int'(PATH_LATENCIES_CYCLES_SRCA))$fatal(1,"latency mismatch %0d",elapsed);
  if(rsp_data!=256'h1234)$fatal(1,"data mismatch");
  $display("REVB_CONFIG_PASS read_latency=%0d L0_bytes=%0d",elapsed,L0_BYTES);$finish;
 end
endmodule
'''

FMA_TB="""`timescale 1ns/1ps
module tb_generated_fma;
 import tiny_npu_revb_config_pkg::*;
 logic clk=0,reset=1,in_valid=0,in_ready,out_valid,out_ready=1;
 logic [15:0] a=16'h3f00,b=16'h3f00,c=16'h3f00,result;integer elapsed;
 always #5 clk=~clk;
 tiny_npu_revb_fma dut(.*);
 initial begin
  repeat(3)@(negedge clk);reset=0;in_valid=1;
  @(negedge clk);in_valid=0;elapsed=1;
  while(!out_valid)begin @(negedge clk);elapsed++;if(elapsed>128)$fatal(1,"FMA timeout");end
  if(elapsed!=int'(MAC_FMA_PIPE_CYCLES)||result!=16'h4000)$fatal(1,"generated FMA mismatch");
  $display("GENERATED_FMA_PASS latency=%0d",elapsed);$finish;
 end
endmodule
"""

def main():
 result={'scope':'configuration and isolated primitive consumers; not system NPU simulation','profiles':[],'rejected':[],'rtl':[]}
 old=json.loads((ROOT/'configs/revb/baseline_expected.json').read_text())
 for scale in (1,2,4):
  p=load_profile(scale)
  # Frozen regression fixture is a test oracle, never a configuration source.
  for key in ('L0_BYTES','ARRAY_COUNT','PEAK_TOPS','AXI_PORTS','AXI_RAW_GBS'):
   assert p[key]==old[str(scale)][key],(scale,key)
  assert p['NEAR_MAC_REGFILE_TOTAL_BYTES']==3133440*scale and p['PE_ACC_CONTEXT_BYTES']==245760*scale
  result['profiles'].append({'scale':scale,'L0_bytes':p['L0_BYTES'],'peak_TOPS':p['PEAK_TOPS']})
 invalid=[{'UNKNOWN':1},{'L0_BYTES':123},{'AXI_DATA_BITS':512},{'AXI_ID_BITS':4},{'AXI_MAX_BURST_BEATS':8},
  {'DMA_MAX_BURST_BYTES':4097},{'DMA_READ_BUFFER_BYTES':1024},{'AXI_PORTS':0},
  {'MEM_EFFICIENCY':0},{'MEM_EFFICIENCY':1.1},{'ROCKET_CORES':6},{'SRAM_PORT':'1R1W'},
  {'MAC_ACC_CONTEXTS':2},{'PATH_LATENCIES_CYCLES':{'SRCA':-1}},
  {'PATH_LATENCIES_CYCLES':{'UNKNOWN':1}},{'PATH_LATENCIES_CYCLES':{'SRCA':128},'SRCA_SLOTS':8},
  {'LOCAL_MAX_INFLIGHT_VECTORS':256},{'INTERNAL_ACC_FORMAT':'FP32'},
  {'L0_REGIONS':[{'name':'A'}]},{'AXI_PORTS':True},{'L0_CLOCK_HZ':0},
  {'DMA_PAYLOAD_TARGET_GBS':25},{'OIC_BITS':32},{'FMA_MAX_LOGIC_DEPTH':41},{'PATH_LATENCIES_CYCLES':{'FMA':10}},{'MAC_ACC_CONTEXTS':11}]
 for change in invalid:
  try:load_profile(overrides=change)
  except ConfigError as e:result['rejected'].append({'override':change,'reason':str(e)})
  else:raise AssertionError(f'Invalid config accepted: {change}')
 long=load_profile(overrides={'PATH_LATENCIES_CYCLES':{'SRCA':128}})
 assert long['SRCA_SLOTS']==long['SRCB_SLOTS']==32
 expanded=load_profile(overrides={'PATH_LATENCIES_CYCLES':{'SRCA':512},'LOCAL_MAX_INFLIGHT_VECTORS':512,'LOCAL_VECTOR_ID_BITS':9})
 assert expanded['SRCA_SLOTS']==64 and expanded['SRCB_SLOTS']==32
 assert evaluate(config=long)['serialized_vector_TOPS']<evaluate()['serialized_vector_TOPS']
 fma=load_profile(overrides={'PATH_LATENCIES_CYCLES':{'FMA':13},'MAC_ACC_CONTEXTS':16})
 assert fma['SRCA_SLOTS']==32 and fma['PE_ACC_CONTEXT_BYTES']==327680
 tf32=load_profile(overrides={'INTERNAL_ACC_FORMAT':'TF32_S1_E8_M10'})
 assert tf32['INTERNAL_EXP_BITS']==8 and tf32['PE_ACC_CONTEXT_BYTES']==491520
 mapping={'1':0,'2':0,'3':1,'4':2,'5':3,'6':3,'7':4,'8':5}
 assert load_profile(cores=6,overrides={'ROLE_TO_HART':mapping})['FLOAT_VECTOR_OWNER_HART']==5
 # Capacity changes originate only in physical geometry and propagate to every artifact.
 regions=copy.deepcopy(load_profile()['L0_REGIONS'])
 for r in regions:
  for key in ('bytes','physical_macros','combined_RW_GBs_at_1GHz'):r.pop(key)
  r['depth']*=2
 large=load_profile(overrides={'L0_REGIONS':regions})
 assert large['L0_BYTES']==20*1024**2 and large['L0_ADDRESS_BITS']==25
 with tempfile.TemporaryDirectory(prefix='revb-config-',dir=ROOT/'build') as temp:
  d=Path(temp)
  bad=json.loads(DEFAULT_CONFIG.read_text());bad['defaults']['TYPO']=1
  (d/'bad.json').write_text(json.dumps(bad))
  try:load_profile(config_path=d/'bad.json')
  except ConfigError:result['schema_unknown_default_rejected']=True
  else:raise AssertionError('Unknown authoring default accepted')
  # Invalid configurations cannot leave partial generated artifacts.
  for change in ({'AXI_PORTS':0},{'FMA_MAX_LOGIC_DEPTH':32}):
   try:generate(overrides=change,out=d/'invalid')
   except ConfigError:assert not (d/'invalid').exists()
   else:raise AssertionError('Invalid generation succeeded')
  planned=generate(overrides={'INTERNAL_ACC_FORMAT':'TF32_S1_E8_M10'},out=d/'planned-tf32',lint=True)
  assert not json.loads((planned/'manifest.json').read_text())['fma_native_emitted']
  assert not (planned/'tiny_npu_revb_fma.sv').exists()
  for name,changes in [('default',{}),('long',{'PATH_LATENCIES_CYCLES':{'SRCA':128}}),('capacity',{'L0_REGIONS':regions})]:
   dest=generate(out=d/name,overrides=changes,lint=True)
   manifest=json.loads((dest/'manifest.json').read_text())
   generate(out=dest,overrides=changes,lint=True)
   assert manifest==json.loads((dest/'manifest.json').read_text())
   p=json.loads((dest/'parameters.json').read_text());assert p==json.loads((dest/'model_input.json').read_text())
   assert evaluate(config=p)==json.loads((dest/'performance.json').read_text())['result']
   for file,digest in manifest['files'].items():assert hashlib.sha256((dest/file).read_bytes()).hexdigest()==digest
   amap=json.loads((dest/'address_map.json').read_text());assert amap['regions'][0]['base']==0
   for prev,cur in zip(amap['regions'],amap['regions'][1:]):assert prev['limit_exclusive']==cur['base']
   assert amap['regions'][-1]['limit_exclusive']==p['L0_BYTES']
   (dest/'check.c').write_text('#include "tiny_npu_revb_config.h"\n'+
    f'_Static_assert(TINY_NPU_L0_BYTES == {p["L0_BYTES"]},"L0");\n'+
    f'_Static_assert(TINY_NPU_PATH_LATENCIES_CYCLES_SRCA == {p["PATH_LATENCIES_CYCLES"]["SRCA"]},"latency");\n'+
    f'_Static_assert(TINY_NPU_L0_SCALE_METADATA_LIMIT_EXCLUSIVE == {p["L0_BYTES"]},"end");\n')
   subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsyntax-only','check.c'],cwd=dest,check=True)
   (dest/'tb.sv').write_text(TB)
   cmd=[shutil.which('verilator') or 'verilator','--binary','--timing','-j','2','--top-module','tb_revb_config','-f','rtl.f','tb.sv']
   run=subprocess.run(cmd,cwd=dest,capture_output=True,text=True)
   if run.returncode:raise AssertionError(run.stdout+run.stderr)
   log=subprocess.check_output([str(dest/'obj_dir/Vtb_revb_config')],cwd=dest,text=True)
   assert 'REVB_CONFIG_PASS' in log;print(log.strip())
   (dest/'fma_tb.sv').write_text(FMA_TB)
   run=subprocess.run([shutil.which('verilator') or 'verilator','--binary','--timing','-j','2','--top-module','tb_generated_fma','-f','rtl.f','fma_tb.sv'],cwd=dest,capture_output=True,text=True)
   if run.returncode:raise AssertionError(run.stdout+run.stderr)
   fma_log=subprocess.check_output([str(dest/'obj_dir/Vtb_generated_fma')],cwd=dest,text=True);assert 'GENERATED_FMA_PASS' in fma_log;print(fma_log.strip())
   result['rtl'].append({'configuration':name,'L0_bytes':p['L0_BYTES'],'latency':p['PATH_LATENCIES_CYCLES']['SRCA'],'result':log.strip(),'native_FMA':fma_log.strip()})
 result['status']='PASS'
 (ARCH/'config_tests.json').write_text(json.dumps(result,indent=2)+'\n')
 print(f'RevB configuration PASS: 3 scale profiles, {len(invalid)} rejected inputs, 3 C/SV consumers, deterministic manifests')
if __name__=='__main__':
 (ROOT/'build').mkdir(exist_ok=True);main()
