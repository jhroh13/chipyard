#!/usr/bin/env python3
"""Initial generic synthesis. No library/PVT/physical timing is fabricated."""
import argparse,collections,hashlib,json,os,re,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def logic_depth(module):
 cells=module['cells'];comb={n:c for n,c in cells.items() if 'DFF' not in c['type'].upper()}
 driver={}
 for n,c in comb.items():
  for port,bits in c['connections'].items():
   if c['port_directions'][port]=='output':
    for bit in bits:
     if isinstance(bit,int):driver[bit]=n
 deps={n:{driver[b] for port,bits in c['connections'].items() if c['port_directions'][port]=='input' for b in bits if isinstance(b,int) and b in driver and driver[b]!=n} for n,c in comb.items()}
 users=collections.defaultdict(list)
 for n,parents in deps.items():
  for parent in parents:users[parent].append(n)
 queue=collections.deque(n for n,v in deps.items() if not v);depth={n:1 for n in queue};count=0;indegree={n:len(v) for n,v in deps.items()}
 while queue:
  n=queue.popleft();count+=1
  for user in users[n]:
   depth[user]=max(depth.get(user,1),depth[n]+1);indegree[user]-=1
   if indegree[user]==0:queue.append(user)
 if count!=len(comb):raise ValueError('combinational cycle or unknown cell abstraction in depth graph')
 return max(depth.values(),default=0)

def run(reuse=False):
 out=ROOT/'build/synthesis';out.mkdir(parents=True,exist_ok=True)
 native=shutil.which('yosys');wasm=ROOT/'build/synth-tools/bin/yowasp-yosys';tool=native or (str(wasm) if wasm.exists() else None)
 if not tool:raise SystemExit('Install yosys or: python3 -m pip install --target tiny-npu/build/synth-tools yowasp-yosys')
 env=os.environ.copy()
 if not native:
  env['PYTHONPATH']=str(ROOT/'build/synth-tools')+os.pathsep+env.get('PYTHONPATH','');env['XDG_CACHE_HOME']=str(ROOT/'build/synth-cache')
 current_hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [ROOT/'rtl/tiny_npu_lq16_fma_proto.sv',ROOT/'rtl/tiny_npu_sram_1rw_subbank.sv']}
 if reuse:
  previous=json.loads((ROOT/'architecture/v2/synthesis_results.json').read_text())
  if previous['source_sha256']!=current_hashes:raise ValueError('Stale synthesis outputs: source changed; rerun without --reuse')
 for name in ('fma','fma_mapped','sram'):
  if not reuse:
   with (out/(name+'.log')).open('w') as log:subprocess.run([tool,'-s',f'synthesis/{name}.ys'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
 def module_stats(name):return next(iter(json.loads((out/(name+'_stats.json')).read_text())['modules'].values()))
 mapped=json.loads((out/'fma_mapped_netlist.json').read_text())['modules']['tiny_npu_lq16_fma_proto']
 sram=json.loads((out/'sram_netlist.json').read_text())['modules']['tiny_npu_sram_1rw_subbank']
 mem=[c for c in sram['cells'].values() if c['type']=='$mem_v2'];assert len(mem)==1
 mp={k:int(v,2) for k,v in mem[0]['parameters'].items() if k in ('WIDTH','SIZE','RD_PORTS','WR_PORTS','RD_CLK_ENABLE','WR_CLK_ENABLE')}
 assert mp['WIDTH']==256 and mp['SIZE']==1024 and mp['RD_PORTS']==mp['WR_PORTS']==1
 transport_bits=sum(int(c['parameters']['WIDTH'],2) for c in sram['cells'].values() if c['type'] in ('$dffe','$sdffe'))
 result=dict(status='GENERIC_SYNTHESIS_COMPLETE_PHYSICAL_TIMING_OPEN',tool=json.loads((out/'fma_stats.json').read_text())['creator'],
  fma=dict(unmapped_bit_cells=module_stats('fma')['num_cells'],ABC_simple_bit_cells=module_stats('fma_mapped')['num_cells'],logic_depth_simple_cells=logic_depth(mapped),transport_latency_cycles=4,functional_input_II_cycles=1,arithmetic_pipeline_balanced=False,area_um2=None,critical_path_ns=None,Fmax_Hz=None),
  sram=dict(parameters=mp,memory_bits=mp['WIDTH']*mp['SIZE'],transport_register_bits=transport_bits,single_port_condition='read and write command mutually exclusive; logical 1R/1W ports are not simultaneous physical ports',macro_mapped=False,area_um2=None,critical_path_ns=None),
  next_gate='Optimize/balance FMA arithmetic pipeline, prove numerical equivalence, map real PDK liberty + SRAM timing models and run STA before claiming 1GHz/10TOPS.',
  source_sha256={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [ROOT/'rtl/tiny_npu_lq16_fma_proto.sv',ROOT/'rtl/tiny_npu_sram_1rw_subbank.sv']})
 (ROOT/'architecture/v2/synthesis_results.json').write_text(json.dumps(result,indent=2)+'\n')
 for name in ('fma_stats.json','fma_mapped_stats.json','sram_stats.json'):(ROOT/'architecture/v2'/name).write_text((out/name).read_text().rstrip()+'\n')
 print(json.dumps(result,indent=2));return result
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--reuse',action='store_true');a=ap.parse_args();run(a.reuse)
