#!/usr/bin/env python3
"""Generate a consistent RevB config package, SW header, address map, model, manifest.
This emits configuration RTL plus an isolated SRAM wrapper, not a complete NPU.
"""
import argparse,csv,hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];ARCH=ROOT/'architecture/v2';sys.path.insert(0,str(ARCH))
from configuration import load_profile,ConfigError,DEFAULT_CONFIG
from sweep_l0 import evaluate

def dump(path,data):path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
def flatten(obj,prefix=''):
 for key,val in sorted(obj.items()):
  name=(prefix+'_'+str(key)).strip('_').upper()
  if isinstance(val,dict):yield from flatten(val,name)
  elif isinstance(val,list):
   for i,v in enumerate(val):
    if isinstance(v,dict):yield from flatten(v,f'{name}_{i}')
    else:yield f'{name}_{i}',v
  else:yield name,val

def address_map(p):
 offset=0;regions=[]
 for r in p['L0_REGIONS']:
  regions.append(dict(name=r['name'],base=offset,size_bytes=r['bytes'],limit_exclusive=offset+r['bytes'],logical_banks=r['banks'],subbanks_per_bank=r['subbanks'],word_bytes=r['width']//8,depth=r['depth']))
  offset+=r['bytes']
 return dict(address_space='NPU_LOCAL_BYTE_OFFSET',cpu_mmio_base=None,AXI_system_mapping='integration_pending',L0_bytes=offset,bounds_check_required=True,regions=regions)

def generate(scale=1,config_path=None,overrides=None,out=None,lint=False):
 # Resolve every constraint before touching output directories.
 p=load_profile(scale,overrides=overrides,config_path=config_path)
 result=evaluate(config=p)
 model_input=dict(p);mapping=address_map(p)
 source=Path(config_path or DEFAULT_CONFIG);source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
 identity=hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 d=Path(out) if out else ROOT/f'generated-revb/x{scale}';d.mkdir(parents=True,exist_ok=True)
 dump(d/'parameters.json',p);dump(d/'model_input.json',model_input);dump(d/'address_map.json',mapping)
 modeled=set('ARRAY_COUNT ACCEL_CLOCK_HZ L0_CLOCK_HZ AXI_CLOCK_HZ VECTOR_CLOCK_HZ AXI_DATA_BITS AXI_PORTS MEM_EFFICIENCY DMA_PAYLOAD_TARGET_GBS DRAM_READ_LATENCY_NS DMA_READ_MO DMA_WRITE_MO DMA_MAX_BURST_BYTES MAC_ACC_CONTEXTS PATH_LATENCIES_CYCLES L0_REG_LATENCY_MAX_CYCLES SLOT_SIZING_POLICY SUBBANK_ISSUE_II_CYCLES TC_ISSUE_II_CYCLES L0_CONFLICT_EFFICIENCY L0_REGIONS L0_BYTES VECTOR_LANES VECTOR_ISSUE_II_CYCLES JOB_DISPATCH_CYCLES OIC_OPERATION_BUDGET_PER_GROUP OIC_REQUEST_PORTS FINAL_FP32_STRIP_ROWS FINAL_FP32_STRIP_SLOTS REFERENCE_M REFERENCE_N REFERENCE_K SRCA_SLOTS SRCB_SLOTS SRCC_SLOTS TARGETR_SLOTS'.split())
 dump(d/'parameter_coverage.json',{k:dict(SV_package=True,C_header=True,model_status='consumed_or_derived' if k in modeled else 'contract_validation_or_planned_only; no independent timing sensitivity claimed') for k in p})
 dump(d/'performance.json',dict(configuration_sha256=identity,scope='planning estimate, not integrated RTL throughput',result=result))
 constants=dict(p)
 for r in mapping['regions']:
  key='L0_'+r['name'].upper();constants[key+'_BASE']=r['base'];constants[key+'_LIMIT_EXCLUSIVE']=r['limit_exclusive']
 constants['CONFIG_SHA256']=identity
 sv=['// Generated; edit configs/revb/default.json instead.','`timescale 1ns/1ps','package tiny_npu_revb_config_pkg;']
 h=['/* Generated; edit configs/revb/default.json instead. */','#ifndef TINY_NPU_REVB_CONFIG_H','#define TINY_NPU_REVB_CONFIG_H','#include <stdint.h>']
 for name,value in flatten(constants):
  if isinstance(value,bool):typ='bit';lit="1'b1" if value else "1'b0";clit='1' if value else '0'
  elif isinstance(value,int):typ='longint unsigned';lit=f"64'd{value}";clit=f'UINT64_C({value})'
  elif isinstance(value,float):typ='real';lit=repr(value);clit=lit
  else:typ='string';lit=json.dumps(value);clit=lit
  sv.append(f'  localparam {typ} {name} = {lit};');h.append(f'#define TINY_NPU_{name} {clit}')
 sv+=['endpackage'];h+=['#endif']
 (d/'tiny_npu_revb_config_pkg.sv').write_text('\n'.join(sv)+'\n');(d/'tiny_npu_revb_config.h').write_text('\n'.join(h)+'\n')
 wrapper='''`timescale 1ns/1ps
// Generated isolated SRAM configuration consumer. Not the full L0 fabric.
module tiny_npu_revb_config_smoke (
 input logic clk,reset,cmd_valid,cmd_write,rsp_ready,
 input logic [$clog2(tiny_npu_revb_config_pkg::L0_REGIONS_0_DEPTH)-1:0] cmd_addr,
 input logic [255:0] cmd_data,input logic [31:0] cmd_mask,
 output logic cmd_ready,rsp_valid,output logic [255:0] rsp_data
);
 import tiny_npu_revb_config_pkg::*;
 tiny_npu_sram_1rw_subbank #(.WIDTH(256),.DEPTH(int'(L0_REGIONS_0_DEPTH)),
   .READ_LATENCY(int'(PATH_LATENCIES_CYCLES_SRCA))) sram (.*);
endmodule
'''
 (d/'tiny_npu_revb_config_smoke.sv').write_text(wrapper)
 shutil.copyfile(ROOT/'rtl/tiny_npu_sram_1rw_subbank.sv',d/'tiny_npu_sram_1rw_subbank.sv')
 files=['tiny_npu_revb_config_pkg.sv','tiny_npu_sram_1rw_subbank.sv','tiny_npu_revb_config_smoke.sv']
 (d/'rtl.f').write_text('\n'.join(files)+'\n')
 metadata=json.loads(source.read_text())['metadata']
 with (d/'parameters.csv').open('w',newline='') as f:
  w=csv.writer(f,lineterminator='\n');w.writerow(['parameter','resolved_value','description','allowed_or_rule'])
  for key,val in sorted(p.items()):w.writerow([key,json.dumps(val,ensure_ascii=False),metadata.get(key,{}).get('description','derived; see configuration.py'),metadata.get(key,{}).get('allowed_or_rule','derived / validated contract')])
 (d/'REPORT.md').write_text(f'''# RevB generated configuration x{scale}

Config SHA256: `{identity}`

| Item | Resolved |
|---|---:|
| Rocket cores | {p['ROCKET_CORES']} |
| L0 bytes / physical subbanks | {p['L0_BYTES']} / {p['L0_TOTAL_SUBBANKS']} |
| MAC arrays / peak TOPS | {p['ARRAY_COUNT']} / {p['PEAK_TOPS']:.3f} |
| AXI ports x data bits | {p['AXI_PORTS']} x {p['AXI_DATA_BITS']} |
| Requested effective GB/s | {p['DMA_PAYLOAD_TARGET_GBS']} |
| A/B/C/TARGETR slots | {'/'.join(str(p[x+'_SLOTS']) for x in ('SRCA','SRCB','SRCC','TARGETR'))} |
| Planning TOPS, serialized vector | {result['serialized_vector_TOPS']:.6f} |

The model reads `model_input.json`, identical to `parameters.json`. `address_map.json` uses NPU-local byte offsets; CPU MMIO and system AXI mappings await integration. The generated SV package and C header carry the same resolved values and configuration hash. `rtl.f` builds only the configuration package and isolated single-port SRAM wrapper.

No new MAC/TC/OIC/AXI/RoCC system RTL is generated here. Configuration propagation does not establish feature implementation, timing closure, numeric accuracy, or sustained 10 TOPS. See `parameter_coverage.json` for model coverage. Stage-breakdown planning fields do not automatically replace aggregate `PATH_LATENCIES_CYCLES`. Physical SRAM, precise arbitration/DDR traces and unimplemented controls still require calibration. `performance.json` is a planning estimate.
''')
 if lint:
  run=subprocess.run([shutil.which('verilator') or 'verilator','--lint-only','--top-module','tiny_npu_revb_config_smoke',*files],cwd=d,capture_output=True,text=True)
  (d/'lint.log').write_text(run.stdout+run.stderr)
  if run.returncode:raise ConfigError(f'RTL lint failed: {d / "lint.log"}')
 generated=['parameter_coverage.json','parameters.json','model_input.json','address_map.json','performance.json','parameters.csv','REPORT.md','tiny_npu_revb_config.h','rtl.f',*files]
 manifest=dict(schema_version=1,source_config_sha256=source_sha,configuration_sha256=identity,scale=scale,overrides=overrides or {},rtl_scope='config_package_and_isolated_sram_only',files={n:hashlib.sha256((d/n).read_bytes()).hexdigest() for n in generated})
 dump(d/'manifest.json',manifest)
 print(f'x{scale}: generated {len(generated)} files, lint={lint}, planning TOPS={result["serialized_vector_TOPS"]:.6f}',flush=True)
 return d

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path,default=DEFAULT_CONFIG);ap.add_argument('--scale',type=int,nargs='+',choices=[1,2,4],default=[1,2,4]);ap.add_argument('--set',action='append',default=[],metavar='KEY=JSON');ap.add_argument('--out',type=Path);ap.add_argument('--lint',action='store_true');ap.add_argument('--check',action='store_true',help='reject stale committed outputs without modifying them');a=ap.parse_args()
 try:
  overrides={}
  for item in a.set:
   key,value=item.split('=',1);cursor=overrides
   parts=key.split('.')
   for part in parts[:-1]:cursor=cursor.setdefault(part,{})
   cursor[parts[-1]]=json.loads(value)
  if a.out and len(a.scale)!=1:raise ConfigError('--out requires exactly one --scale')
  for scale in a.scale:
   if not a.check:generate(scale,a.config,overrides,a.out,a.lint)
   else:
    destination=a.out or ROOT/f'generated-revb/x{scale}'
    with tempfile.TemporaryDirectory(prefix='revb-check-') as temp:
     generated=generate(scale,a.config,overrides,Path(temp),a.lint)
     manifest=json.loads((generated/'manifest.json').read_text())
     for name in [*manifest['files'],'manifest.json']:
      if not (destination/name).exists() or (destination/name).read_bytes()!=(generated/name).read_bytes():
       raise ConfigError(f'Stale generated output: {destination/name}; run make generate-revb')
    print(f'x{scale}: generated outputs match canonical source')
 except (ConfigError,ValueError,KeyError) as e:ap.exit(2,f'Configuration error: {e}\n')
