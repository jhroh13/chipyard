#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'architecture/v2'))
from configuration import load_profile
from analyze_trace import analyze

def run(latency):
 out=ROOT/f'build/bubble-rtl-{latency}';out.mkdir(parents=True,exist_ok=True)
 sources=[ROOT/'rtl/tiny_npu_sram_1rw_subbank.sv',ROOT/'rtl/tiny_npu_trace_monitor.sv',ROOT/'sim/tb_bubble_trace.sv']
 cmd=[shutil.which('verilator') or 'verilator','--binary','--trace','--timing','-j','4','--top-module','tb_bubble_trace',f'-GLATENCY={latency}','--Mdir',str(out/'obj'),*[str(s) for s in sources]]
 with (out/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 sha=hashlib.sha256(json.dumps(load_profile(),sort_keys=True,separators=(',',':')).encode()).hexdigest()
 case=dict(canonical_configuration_sha256=sha,base_latency=latency,bank_latency_offsets=[0,3,6,9],per_bank_read_credit_limit=4,seed=27011,provenance='SRAM fixture only; synthetic/unconnected Rocket/MAC/AXI probes')
 case_sha=hashlib.sha256(json.dumps(case,sort_keys=True).encode()).hexdigest();case['verification_run_sha256']=case_sha
 (out/'run_manifest.json').write_text(json.dumps(case,indent=2)+'\n')
 with (out/'simulation.log').open('w') as f:subprocess.run([str(out/'obj/Vtb_bubble_trace'),'+TRACE_SOURCE=RTL_SRAM_fixture_synthetic_hart_MAC_AXI_unconnected','+TRACE_CONFIG_SHA256='+sha,'+TRACE_RUN_SHA256='+case_sha],cwd=out,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
 log=(out/'simulation.log').read_text();assert 'BUBBLE_TRACE_PASS' in log;summary=analyze(out/'rtl_trace.jsonl',out/'analysis')
 for h in range(8):assert f'rocket.h{h}.control' in summary['channels']
 assert len(summary['channels'])==51
 match=re.search(r'wait=(\d+) credit=(\d+) bank=(\d+) oic=(\d+)',log);assert match
 raw=summary['channels']['mac.issue']['raw_causes_ps']
 for name,value in zip(('wait-data','no-credit','bank-conflict','OIC-conflict'),match.groups()):assert raw[name]//1000==int(value),(name,raw[name],value)
 window_args=[str(out/'obj/Vtb_bubble_trace'),'+TRACE_FILE=window_trace.jsonl','+TRACE_START_PS=100000','+TRACE_END_PS=200000','+TRACE_HART_MASK=1','+TRACE_AXI_MASK=0']
 window_log=subprocess.check_output(window_args,cwd=out,text=True);assert 'BUBBLE_TRACE_PASS' in window_log
 rows=[json.loads(line) for line in (out/'window_trace.jsonl').read_text().splitlines()]
 for row in rows:
  if row['type']=='sample':assert 100000<=row['time_ps']<200000 and (row['channel'].startswith('rocket.h0.') or row['channel']=='mac.issue')
 assert rows[0]['capture']['hart_mask']==1 and rows[0]['capture']['axi_mask']==0
 print(log.strip());return dict(capture_window_mask_test='PASS',latency=latency,status='PASS',log=log.strip(),channels=len(summary['channels']),scope='actual single-port SRAM/arbitration fixture; hart/MAC agents; AXI unconnected')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--latencies',type=int,nargs='+',default=[16,64,128]);a=ap.parse_args();rows=[run(l) for l in a.latencies];(ROOT/'architecture/v2/rtl_trace_tests.json').write_text(json.dumps(rows,indent=2)+'\n')
