#!/usr/bin/env python3
"""Synthesize selected native FMA configurations and fail above40 basic gates."""
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'architecture/v2'))
from configuration import load_profile
from gate_depth import audit

def run(latencies=(11,13),reuse=False):
 p=load_profile();limit=p.get('FMA_MAX_LOGIC_DEPTH',40)
 if not 1<=limit<=40:raise ValueError('User requires <=40 gates; cannot relax this limit')
 out=ROOT/'build/synthesis-pipe';out.mkdir(parents=True,exist_ok=True)
 native=shutil.which('yosys');wasm=ROOT/'build/synth-tools/bin/yowasp-yosys';tool=native or str(wasm)
 if not Path(tool).exists() and not native:raise SystemExit('Install synthesis/requirements.txt into build/synth-tools')
 env=os.environ.copy()
 if not native:env.update(PYTHONPATH=str(ROOT/'build/synth-tools')+os.pathsep+env.get('PYTHONPATH',''),XDG_CACHE_HOME=str(ROOT/'build/synth-cache'))
 source=ROOT/'rtl/tiny_npu_lq16_fma_pipe.sv';sha=hashlib.sha256(source.read_bytes()).hexdigest();reports={}
 for latency in latencies:
  directory=out/f'latency-{latency}';directory.mkdir(exist_ok=True)
  if not reuse:
   script=f'''read_verilog -sv rtl/tiny_npu_lq16_fma_pipe.sv
chparam -set LATENCY {latency} tiny_npu_lq16_fma_pipe
hierarchy -top tiny_npu_lq16_fma_pipe
synth -top tiny_npu_lq16_fma_pipe -noabc
check -assert
dffunmap
abc -g AND,OR
opt_clean
tee -o build/synthesis-pipe/latency-{latency}/stats.json stat -json
write_json build/synthesis-pipe/latency-{latency}/netlist.json
'''
   (directory/'synth.ys').write_text(script)
   with (directory/'synth.log').open('w') as log:subprocess.run([tool,'-s',str((directory/'synth.ys').relative_to(ROOT))],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
   (directory/'source.sha256').write_text(sha)
  elif (directory/'source.sha256').read_text()!=sha:raise ValueError('Stale synthesis; rerun without --reuse')
  data=json.loads((directory/'netlist.json').read_text());report=audit(data['modules']['tiny_npu_lq16_fma_pipe'],limit)
  report.update(latency=latency,arithmetic_stages=11,output_transport_stages=latency-11,tool=data['creator'],source_sha256=sha,netlist_sha256=hashlib.sha256((directory/'netlist.json').read_bytes()).hexdigest())
  (directory/'depth.json').write_text(json.dumps(report,indent=2)+'\n');reports[str(latency)]=report
  print('FMA depth',latency,'cycles:',report['max_depth'],'/',limit,report['status'],flush=True)
  if report['status']!='PASS':raise SystemExit(1)
 baseline_path=out/'reference_netlist.json';baseline=None
 ref_source=ROOT/'rtl/tiny_npu_lq16_fma_proto.sv';ref_script=ROOT/'synthesis/fma_reference_aon.ys'
 ref_sha=hashlib.sha256(ref_source.read_bytes()+ref_script.read_bytes()).hexdigest();stamp=out/'reference_flow.sha256'
 if not reuse and (not stamp.exists() or stamp.read_text()!=ref_sha):
  with (out/'reference.log').open('w') as log:subprocess.run([tool,'-s','synthesis/fma_reference_aon.ys'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
  stamp.write_text(ref_sha)
 if baseline_path.exists():
  if not stamp.exists() or stamp.read_text()!=ref_sha:raise ValueError('Stale reference baseline; rerun without --reuse')
  ref=json.loads(baseline_path.read_text())['modules']['tiny_npu_lq16_fma_proto'];baseline=audit(ref,limit)
  baseline['source_sha256']=hashlib.sha256(ref_source.read_bytes()).hexdigest()
 artifact=ROOT/'architecture/v2/fma_gate_depth.json'
 # Retain only measurements for this exact source and gate contract.
 if artifact.exists():
  previous=json.loads(artifact.read_text())
  if previous.get('source_sha256')==sha and previous.get('register_basis','').startswith('plain DFF'):
   existing={k:v for k,v in previous['configurations'].items() if v['limit']==limit};existing.update(reports);reports=existing
 result=dict(status='PASS',source_sha256=sha,gate_basis='AND2_OR2_NOT',hard_limit=limit,configurations=reports,reference=baseline,register_basis='plain DFF; enable and synchronous-reset muxes decomposed into basic gates',scope='gate depth only; no GHz/PVT/physical delay claim; native LQ16 only')
 artifact.write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--latencies',type=int,nargs='+',default=[11,13]);ap.add_argument('--reuse',action='store_true');a=ap.parse_args();run(a.latencies,a.reuse)
