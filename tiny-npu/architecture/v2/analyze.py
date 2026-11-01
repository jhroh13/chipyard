#!/usr/bin/env python3
"""Architecture RevB planning model; no new RTL/core-count validation implied."""
from pathlib import Path
import csv,json,math,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'model'))
from spec_model import simulate
OUT=Path(__file__).resolve().parent

from configuration import load_profile

def profile(scale=1,cores=None):
 return load_profile(scale=scale,cores=cores)

def main():
 ps={str(s):profile(s) for s in (1,2,4)};results=[]
 for s,p in ps.items():
  for bw in (10*int(s),20*int(s)):
   pp=dict(p,DMA_PAYLOAD_TARGET_GBS=bw)
   for c_mode in ('ZERO','LOAD_EXISTING'):
    # Base engine supports C=0 traffic only; LOAD_EXISTING is a lower-bound roofline.
    m=p['REFERENCE_M'];n=p['REFERENCE_N'];k=p['REFERENCE_K']
    ops=2*m*n*k;ab=(17*m+33*n)*k/32;c=4*m*n
    traffic=ab+c+(c if c_mode=='LOAD_EXISTING' else 0)
    row=dict(scale=int(s),M=m,N=n,K=k,C_init=c_mode,payload_target_GBs=bw,
      peak_TOPS=p['PEAK_TOPS'],external_bytes=int(traffic),AI_ops_byte=ops/traffic,
      roofline_TOPS=min(p['PEAK_TOPS'],ops/traffic*bw/1000),
      bandwidth_only_time_us=traffic/(bw*1e9)*1e6)
    row.update(event_model_TOPS=None,event_model_us=None,timing_model='Use sweep_l0.py for multicycle single-port timing; this table is roofline only')
    results.append(row)
 # Same default workload, aggregate DDR20GB/s, final FP32 result vector pass.
 p=ps['1'];m=n=1024;k=4096;ops=2*m*n*k
 vector_pass_ns=math.ceil(m*n/p['VECTOR_LANES'])*p['VECTOR_ISSUE_II_CYCLES']+p['PATH_LATENCIES_CYCLES']['VECTOR_READ']+p['PATH_LATENCIES_CYCLES']['VECTOR_WRITE']+p['PATH_LATENCIES_CYCLES']['LUT']+p['PATH_LATENCIES_CYCLES']['FORMAT']
 rate_at_10T=10e12/(2*k)
 aux=dict(default_vector_pass_ns=vector_pass_ns,
   vector_required_elements_per_second_at_10TOPS=rate_at_10T,
   vector_peak_elements_per_second=p['VECTOR_PEAK_ELEMENTS_PER_SECOND'],
   peak_MAC_input_vector_bytes_per_clock=10*(16+32+2),
   peak_C_bytes_per_clock_each_direction=10*128,
   target_10TOPS_min_AI_at_10GBs=1000,target_10TOPS_min_AI_at_20GBs=500,
   minimal_full_burst_MO_at_20GBs_700ns=math.ceil(20e9*700e-9/4096))
 (OUT/'profiles.json').write_text(json.dumps(ps,indent=2));(OUT/'analysis.json').write_text(json.dumps(dict(results=results,auxiliary=aux),indent=2))
 with (OUT/'performance.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=results[0].keys(),lineterminator='\n');w.writeheader();w.writerows(results)
 print('Base L0:',p['L0_BYTES'],'near-register bytes:',p['NEAR_MAC_REGFILE_TOTAL_BYTES'],'PE accumulator contexts:',p['PE_ACC_CONTEXT_BYTES'])
 for r in results:
  if r['scale']==1:print(r)
 print('Vector:',aux)
 print('L0 capacity/profile accounting: PASS; new architecture RTL not implemented')
if __name__=='__main__':main()
