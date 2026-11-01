#!/usr/bin/env python3
import argparse,copy,hashlib,json,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'architecture/v2'))
from configuration import load_profile
from verify_config import resolve
from trace import Trace,to_vcd
from dram import run_axi
from local_stress import run_local
from analyze_trace import analyze

def run(out,cfg,profile,seed=None):
 cfg=resolve(cfg,profile)
 out=Path(out);out.mkdir(parents=True,exist_ok=True);seed=cfg['seed'] if seed is None else seed
 sha=hashlib.sha256(json.dumps(profile,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 run_sha=hashlib.sha256(json.dumps({'config':sha,'verification':cfg,'seed':seed},sort_keys=True).encode()).hexdigest()
 trace=Trace(out/'trace.jsonl.gz',dict(configuration_sha256=sha,verification_run_sha256=run_sha,seed=seed,rocket_parameters={k:v for k,v in profile.items() if k.startswith('ROCKET_')},cache_size_effect='not predicted; fixture miss probability is an independent stimulus',provenance={'AXI':'behavioral AXI agents','rocket':'control/cache traffic agents, not Rocket RTL','MAC':'reduced scheduling fixture, not arithmetic RTL'},latency_contract={'AR':'ARVALID&&ARREADY -> first RVALID&&RLAST','AW':'first AWVALID -> first WVALID; independent of AWREADY; accepted-AW latency also reported'},tests_are_independent='AXI and reduced local fixture overlap in the viewer but are not an end-to-end connected NPU'))
 try:
  axi=run_axi(trace,cfg['axi'],profile,seed)
  local=run_local(trace,cfg['local'],profile,seed+1)
 finally:trace.close()
 to_vcd(out/'trace.jsonl.gz',out/'waveform.vcd.gz')
 summary=analyze(out/'trace.jsonl.gz',out/'analysis')
 result=dict(status='PASS',scope='infrastructure/traffic-agent qualification, not integrated NPU throughput',seed=seed,configuration_sha256=sha,verification_run_sha256=run_sha,axi=axi,local=local,mac=summary['channels']['mac.issue'],diagnoses=summary['diagnoses'])
 (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');(out/'verification_config.json').write_text(json.dumps(cfg,indent=2)+'\n')
 with zipfile.ZipFile(out/'workload-artifacts.zip','w',zipfile.ZIP_DEFLATED) as z:
  for name in ['trace.jsonl.gz','waveform.vcd.gz','results.json','verification_config.json','analysis/workload.html','analysis/summary.json','analysis/bubbles.json','analysis/axi_transactions.json','analysis/chrome_trace.json','analysis/REPORT.md']:z.write(out/name,name)
 print(json.dumps({'status':'PASS','out':str(out),'AXI_payload_GBs':axi['achieved_shared_GBs'],'cross_ID_overtakes':axi['cross_ID_read_overtakes'],'retired_tokens':local['retired'],'MAC_scheduling_util':summary['channels']['mac.issue']['utilization']}))
 return result
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=ROOT/'build/workload');ap.add_argument('--verification-config',type=Path,default=ROOT/'configs/revb/verification.json');ap.add_argument('--seed',type=int);a=ap.parse_args();run(a.out,json.loads(a.verification_config.read_text()),load_profile(),a.seed)
