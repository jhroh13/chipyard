#!/usr/bin/env python3
"""Actual hash/SFR/VOQ/arbiter + single-port SRAM; measured traffic, no MAC TOPS."""
import json,re,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'sim'))
from run_extended import compile_run
from trace import to_vcd
from analyze_trace import analyze
rows=[]
for latency,stall in [(16,0),(32,0),(32,1),(32,2)]:
 for hashing in (0,1):
  d=ROOT/f'build/bank-fabric-h{hashing}-l{latency}-s{stall}';d.mkdir(parents=True,exist_ok=True)
  log=compile_run(d,'tb_bank_fabric',['rtl/tiny_npu_bank_hash.sv','rtl/tiny_npu_bank_voq.sv','rtl/tiny_npu_hashed_bank_fabric.sv','rtl/tiny_npu_sram_1rw_subbank.sv','sim/tb_bank_fabric.sv'],dict(HASH=hashing,LATENCY=latency,CONSUMER_STALL=stall),shutil.which('verilator'))
  assert 'BANK_FABRIC_PASS' in log
  phases=[dict(phase=int(p),commands=int(n),cycles=int(c),commands_per_cycle=int(n)/int(c),GBs_at_reference_1GHz=32*int(n)/int(c)) for p,n,c in re.findall(r'phase=(\d+) commands=(\d+) elapsed_cycles=(\d+)',log)]
  assert len(phases)==3 and all(x['cycles']>0 for x in phases),log
  match=re.search(r'contention_samples=(\d+) no_credit_samples=(\d+) bank_blocked_samples=(\d+) response_blocked_samples=(\d+)',log)
  row=dict(hashing=bool(hashing),latency=latency,consumer_stall=bool(stall),stall_mode=stall,rows_per_bank=4096,requests_per_port_per_phase=64,independent_progress_samples=int(re.search(r'INDEPENDENT_BANK_PROGRESS samples=(\d+)',log)[1]),status='PASS',phases=phases,bank_contention_samples=int(match[1]),VOQ_no_credit_samples=int(match[2]),SRAM_command_blocked_samples=int(match[3]),response_consumer_blocked_samples=int(match[4]),bank_command_counts=[int(n) for n in re.findall(r'BANK_COUNT bank=\d+ commands=(\d+)',log)],scope='actual 8-ingress/8-bank fixture; fixed-latency SRAM with optional response consumer stall; no Rocket/MAC/AXI integration; 1GHz is testbench timebase only')
  to_vcd(d/'fabric_trace.jsonl',d/'fabric_trace.vcd.gz');analyze(d/'fabric_trace.jsonl',d/'analysis');rows.append(row);print(row,flush=True)
(ROOT/'architecture/v2/bank_fabric_tests.json').write_text(json.dumps(rows,indent=2)+'\n')
