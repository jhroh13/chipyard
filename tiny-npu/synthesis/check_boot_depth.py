#!/usr/bin/env python3
"""Same-basis boot guard depth and post-synthesis metadata/permission regression."""
import hashlib,json,os,random,shutil,subprocess,sys
from pathlib import Path
from collections import deque
from gate_depth import audit
from netlist_sim import Netlist
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'architecture/v2'))
from configuration import load_profile

def qualify(module,p):
 sim=Netlist(module);rng=random.Random(914);pending=deque();checks=0
 sim.tick(reset=1);sim.tick(reset=1)
 base=p['L0_BOOT_OFFSET'];code=base+p['L0_BOOT_CODE_BYTES'];total=p['L0_BYTES']
 for running in (0,1):
  if running:
   blocked=sim.tick(commit_valid=1,loader_idle=0,image_verified=1,rw_initialized=1);assert not blocked['commit_ready']
   blocked=sim.tick(commit_valid=1,loader_idle=1,image_verified=0,rw_initialized=1);assert not blocked['commit_ready']
   committed=sim.tick(commit_valid=1,loader_idle=1,image_verified=1,rw_initialized=1);assert committed['commit_ready']
  for cycle in range(1300):
   owner=rng.randrange(4);hart=rng.choice([0,7,8,255]);write=rng.randrange(2);size=rng.choice([0,1,8,64,4096,4097]);tag=rng.randrange(256)
   addr=rng.choice([0,base-1,base,code-1,code,total-1,total,(1<<p['L0_ADDRESS_BITS'])-1,rng.randrange(total)])
   error=0
   if not 1<=size<=4096 or addr+size-1>=total or addr>=total:error=1
   elif owner in (1,2) and hart>=p['ROCKET_CORES']:error=2
   elif owner==0:error=5 if running else (4 if addr<base else 0)
   elif owner==1:error=3 if not running else (4 if write or addr<base or addr+size-1>=code else 0)
   elif owner==2:error=3 if not running else (4 if addr<base or (write and addr<code) else 0)
   elif addr+size-1>=base:error=4
   valid=int(cycle<1200 and rng.random()<.8);ready=int(rng.random()<.7)
   out=sim.tick(req_valid=valid,req_owner=owner,req_hart=hart,req_write=write,req_addr=addr,req_bytes=size,req_tag=tag,out_ready=ready)
   assert out['boot_ready']==running
   if out['out_valid']:
    assert pending
    assert tuple(out['out_'+k] for k in ('owner','hart','write','addr','bytes','tag','error','allow'))==pending[0]
    if ready:pending.popleft();checks+=1
   if valid and out['req_ready']:pending.append((owner,hart,write,addr,size,tag,error,int(error==0)))
  assert not pending
 assert checks>1000
 return dict(status='PASS',compared_requests=checks,coverage='mapped-gate metadata, full-burst permissions, pre/post commit, invalid hart/length, stalls; randomized regression, not formal equivalence')

def run():
 tool=shutil.which('yosys') or str(ROOT/'build/synth-tools/bin/yowasp-yosys');env=os.environ.copy();env.update(PYTHONPATH=str(ROOT/'build/synth-tools'),XDG_CACHE_HOME=str(ROOT/'build/synth-cache'))
 source=ROOT/'rtl/tiny_npu_l0_boot_guard.sv';reports=[]
 for scale in (1,2,4):
  p=load_profile(scale);d=ROOT/f'build/boot-guard-depth-x{scale}';d.mkdir(parents=True,exist_ok=True);rel=d.relative_to(ROOT)
  settings=dict(ADDR_BITS=p['L0_ADDRESS_BITS'],HARTS=p['ROCKET_CORES'],LATENCY=p['L0_BOOT_GUARD_CYCLES'],TOTAL_BYTES=p['L0_BYTES'],BOOT_BASE=p['L0_BOOT_OFFSET'],CODE_LIMIT=p['L0_BOOT_OFFSET']+p['L0_BOOT_CODE_BYTES'])
  script='read_verilog -sv rtl/tiny_npu_l0_boot_guard.sv\nchparam '+ ' '.join(f'-set {k} {v}' for k,v in settings.items())+' tiny_npu_l0_boot_guard\nhierarchy -top tiny_npu_l0_boot_guard\nsynth -top tiny_npu_l0_boot_guard -noabc\ncheck -assert\ndffunmap\nabc -g AND,OR\nopt_clean\nwrite_json '+str(rel/'netlist.json')+'\n'
  (d/'synth.ys').write_text(script)
  with (d/'synth.log').open('w') as log:subprocess.run([tool,'-s',str(rel/'synth.ys')],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
  m=json.loads((d/'netlist.json').read_text())['modules']['tiny_npu_l0_boot_guard'];r=audit(m,40);assert r['status']=='PASS',r['max_depth']
  r.update(scale=scale,parameters=settings,post_synthesis=qualify(m,p),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),netlist_sha256=hashlib.sha256((d/'netlist.json').read_bytes()).hexdigest());reports.append(r);print('Boot guard',scale,r['max_depth'],r['post_synthesis'],flush=True)
 (ROOT/'architecture/v2/l0_boot_gate_depth.json').write_text(json.dumps(reports,indent=2)+'\n')
if __name__=='__main__':run()
