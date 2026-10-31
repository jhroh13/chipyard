#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""P0 sustained >=10 TOPS candidate, not an end-to-end RTL achievement."""
import argparse,csv,json,math
from pathlib import Path
from spec_model import profile as legacy_profile, simulate
ROOT=Path(__file__).resolve().parent

def profile(scale):
    assert scale in (1,2,4)
    p=legacy_profile(1);s=scale;ports=2 if s==4 else 1
    m={1:1024,2:1536,4:2048}[s]
    p.update(SCALE=s,ARRAY_COUNT=10*s,FP32_ACC_LANES=320*s,
        SRAM_TOTAL_BYTES=8*1024**2*s,OPERAND_BYTES=2*1024**2*s,
        C_BYTES=5*1024**2*s,PARTIAL_BYTES=512*1024*s,META_BYTES=512*1024*s,
        OPERAND_BANKS=32*s,C_BANKS=40*s,PARTIAL_BANKS=64*s,META_BANKS=32*s,
        OPERAND_BANK_DEPTH=2048,C_BANK_DEPTH=4096,PARTIAL_BANK_DEPTH=256,META_BANK_DEPTH=1024,
        AXI_DATA_BITS=512 if s==1 else 1024,AXI_PORTS=ports,
        AXI_ID_BITS=7 if s==1 else 8,DMA_MAX_BURST_BYTES=4096,
        DMA_READ_MO=64*s,DMA_WRITE_MO=32*s,
        DMA_READ_BUFFER_BYTES=128*1024*s,DMA_WRITE_BUFFER_BYTES=64*1024*s,
        DMA_PAYLOAD_TARGET_GBS=20*s,MACRO_M=m,MACRO_N=m,
        TASK_QUEUE_DEPTH=16*s,CDC_AR_DEPTH=16*s,CDC_AW_DEPTH=16*s,
        CDC_R_DEPTH=64*s,CDC_W_DEPTH=64*s,CDC_B_DEPTH=16*s,
        MACS_PER_CLOCK=10240*s,PEAK_TOPS=20.48*s,SUSTAINED_TOPS_TARGET=10*s,
        PROFILE_NAME='P0_SUSTAINED',PROFILE_STATUS='candidate_model_not_system_RTL')
    p['AXI_RAW_GBS']=p['AXI_PORTS']*p['AXI_DATA_BITS']/8*p['AXI_CLOCK_HZ']/1e9
    p['AXI_AFTER_EFFICIENCY_GBS']=p['AXI_RAW_GBS']*.60
    p['MIN_RAW_GBS']=p['DMA_PAYLOAD_TARGET_GBS']/.60
    p['FULL_BURST_MIN_READ_MO']=math.ceil(1+p['DMA_PAYLOAD_TARGET_GBS']*1e9*700e-9/4096)
    assert p['AXI_AFTER_EFFICIENCY_GBS']>=p['DMA_PAYLOAD_TARGET_GBS']
    assert (p['DMA_READ_MO']+p['DMA_WRITE_MO'])//ports<=2**p['AXI_ID_BITS']
    assert sum(p[k] for k in ('OPERAND_BYTES','C_BYTES','PARTIAL_BYTES','META_BYTES'))==p['SRAM_TOTAL_BYTES']
    for region,width in [('OPERAND',256),('C',256),('PARTIAL',256),('META',128)]:
        assert p[region+'_BANKS']*p[region+'_BANK_DEPTH']*width//8==p[region+'_BYTES']
    assert p['C_BANKS']*32>=p['FP32_ACC_LANES']*4
    assert p['PARTIAL_BANKS']*32>=p['FP32_ACC_LANES']*4
    return p

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--scale',type=int,choices=(1,2,4));a=ap.parse_args()
    profiles={str(s):profile(s) for s in ([a.scale] if a.scale else [1,2,4])}
    rows=[]
    for p in profiles.values():
        for shape in dict.fromkeys([(32,32,32),(608,320,4096),(1024,1024,4096),(p['MACRO_M'],p['MACRO_N'],4096)]):
            r=simulate(*shape,p)
            r['target_TOPS']=p['SUSTAINED_TOPS_TARGET']
            r['reference_acceptance_workload']=shape==(p['MACRO_M'],p['MACRO_N'],4096)
            r['target_pass']=r['model_TOPS']>=r['target_TOPS']
            if r['reference_acceptance_workload']:assert r['target_pass'],r
            rows.append(r)
            print(f"x{p['SCALE']} {shape}: model={r['model_TOPS']:.4f} TOPS, target={r['target_TOPS']}, reference={r['reference_acceptance_workload']}, time={r['model_us']:.3f}us")
    (ROOT/'p0_profiles.json').write_text(json.dumps(profiles,indent=2))
    (ROOT/'p0_results.json').write_text(json.dumps(rows,indent=2))
    with (ROOT/'p0_results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    print('P0 model/reference-workload checks: PASS (not RTL sustained-performance proof)')
if __name__=='__main__':main()
