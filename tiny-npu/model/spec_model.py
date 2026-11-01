#!/usr/bin/env python3
"""HDD profile derivation and event-model validation. Standard library only.
10/20/40 GB/s are guaranteed payload targets AFTER 60% efficiency.
"""
import argparse, csv, heapq, json, math
from pathlib import Path
from latency_model import Memory
ROOT=Path(__file__).resolve().parent

def profile(scale):
    assert scale in (1,2,4)
    m,n={1:(608,320),2:(864,448),4:(1216,640)}[scale]
    width=256*scale; clock=625e6; target=10e9*scale; efficiency=.60
    burst=min(64*width//8,4096)
    p=dict(SCALE=scale,ARRAY_COUNT=5*scale,ARRAY_ROWS=32,ARRAY_COLS=32,
        ACCEL_CLOCK_HZ=1_000_000_000,FP32_ACC_LANES=160*scale,
        SRAM_TOTAL_BYTES=2*1024**2*scale,OPERAND_BYTES=1024**2*scale,
        C_BYTES=768*1024*scale,PARTIAL_BYTES=128*1024*scale,META_BYTES=128*1024*scale,
        OPERAND_BANKS=16*scale,C_BANKS=24*scale,PARTIAL_BANKS=32*scale,META_BANKS=8*scale,
        MAIN_BANK_BITS=256,META_BANK_BITS=128,SRAM_PORT='1R1W',SRAM_READ_LATENCY=2,
        AXI_DATA_BITS=width,AXI_CLOCK_HZ=int(clock),AXI_ADDR_BITS=40,
        AXI_ID_BITS=6+int(math.log2(scale)),AXI_MAX_BURST_BEATS=64,
        DMA_MAX_BURST_BYTES=burst,DMA_READ_MO=32*scale,DMA_WRITE_MO=16*scale,
        DMA_READ_BUFFER_BYTES=65536*scale,DMA_WRITE_BUFFER_BYTES=32768*scale,
        DMA_PAYLOAD_TARGET_GBS=target/1e9,MEM_EFFICIENCY=efficiency,
        DRAM_READ_LATENCY_NS=700,WRITE_RESPONSE_TAIL_NS=700,
        MACRO_M=m,MACRO_N=n,TILE_K=32,TASK_QUEUE_DEPTH=8*scale,
        CDC_AR_DEPTH=8*scale,CDC_AW_DEPTH=8*scale,CDC_R_DEPTH=32*scale,
        CDC_W_DEPTH=32*scale,CDC_B_DEPTH=8*scale)
    p.update(MACS_PER_CLOCK=1024*p['ARRAY_COUNT'],PEAK_TOPS=2*1024*p['ARRAY_COUNT']/1000,
        AXI_RAW_GBS=width/8*clock/1e9,AXI_AFTER_EFFICIENCY_GBS=width/8*clock*efficiency/1e9,
        MIN_RAW_GBS=target/efficiency/1e9,
        FULL_BURST_MIN_READ_MO=math.ceil(1+target*700e-9/burst))
    assert p['AXI_AFTER_EFFICIENCY_GBS']>=p['DMA_PAYLOAD_TARGET_GBS']
    assert 4*m*n<=p['C_BYTES']
    assert p['DMA_READ_MO']+p['DMA_WRITE_MO']<=2**p['AXI_ID_BITS']
    assert sum(p[k] for k in ('OPERAND_BYTES','C_BYTES','PARTIAL_BYTES','META_BYTES'))==p['SRAM_TOTAL_BYTES']
    # Per-clock read/write bank capacity must support all five/ten/twenty arrays.
    assert p['OPERAND_BANKS']*32>=p['ARRAY_COUNT']*48
    assert p['C_BANKS']*32>=p['FP32_ACC_LANES']*4
    assert p['PARTIAL_BANKS']*32>=p['FP32_ACC_LANES']*4
    assert p['META_BANKS']*16>=p['ARRAY_COUNT']*2
    return p

def simulate(m,n,k,p,read_mo=None,write_mo=None):
    assert all(x>0 and x%32==0 for x in (m,n,k))
    # Model at the guaranteed target, not at the 20% spare interface capacity.
    mem=Memory(p['DMA_PAYLOAD_TARGET_GBS']*1e9,p['DRAM_READ_LATENCY_NS'],
        read_mo or p['DMA_READ_MO'],write_mo or p['DMA_WRITE_MO'],p['DMA_MAX_BURST_BYTES'])
    now=0.; macros=0
    for mi in range(0,m,p['MACRO_M']):
        for ni in range(0,n,p['MACRO_N']):
            mm=min(p['MACRO_M'],m-mi);nn=min(p['MACRO_N'],n-ni)
            assert 4*mm*nn<=p['C_BYTES']
            assert 2*(17*mm+33*nn)<=p['OPERAND_BYTES']
            contexts=p.get('MAC_ACC_CONTEXTS',1)
            groups=math.ceil((mm//32)*(nn//32)/p['ARRAY_COUNT'])
            compute=(math.ceil(groups/contexts)*contexts*32*p.get('ARCH_LOCAL_SLOWDOWN',1.)
                     +p.get('PANEL_PIPELINE_OVERHEAD_CYCLES',0))/p['ACCEL_CLOCK_HZ']
            finishes=[];end=now
            for block in range(k//32):
                ready=now if block<2 else finishes[block-2]
                arrivals=[mem.transfer(size,ready,'R') for size in (mm*16,nn*32,mm,nn)]
                end=max(end,*arrivals)+compute
                finishes.append(end)
            now=mem.transfer(mm*nn*4,end,'W');macros+=1
    ops=2*m*n*k;traffic=sum(mem.bytes.values());peak=p['PEAK_TOPS']*1e12
    assert ops/now<=min(peak,ops/traffic*mem.bw)*(1+1e-9)
    return dict(scale=p['SCALE'],M=m,N=n,K=k,macro_count=macros,
        read_MO=mem.mo['R'],write_MO=mem.mo['W'],burst_bytes=mem.burst,
        peak_TOPS=p['PEAK_TOPS'],payload_target_GBs=p['DMA_PAYLOAD_TARGET_GBS'],
        read_bytes=mem.bytes['R'],write_bytes=mem.bytes['W'],ops_per_byte=ops/traffic,
        model_us=now*1e6,model_TOPS=ops/now/1e12,MAC_utilization=ops/(now*peak),
        achieved_payload_GBs=traffic/now/1e9,
        roofline_TOPS=min(peak,ops/traffic*mem.bw)/1e12)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--scale',type=int,choices=(1,2,4));args=ap.parse_args()
    scales=[args.scale] if args.scale else [1,2,4]
    profiles={str(s):profile(s) for s in scales};rows=[];streams=[];mos=[]
    for p in profiles.values():
        fixed=[(32,32,32),(256,256,1024),(608,320,4096),(608,320,65536),(1024,1024,4096)]
        for shape in fixed: rows.append(dict(case='fixed_workload',**simulate(*shape,p)))
        rows.append(dict(case='profile_macro',**simulate(p['MACRO_M'],p['MACRO_N'],4096,p)))
        for mo in (1,2,4,5,8,16,32,64,128):
            mos.append(simulate(608,320,4096,p,read_mo=mo,write_mo=min(mo,p['DMA_WRITE_MO'])))
        for kind in ('R','W'):
            mem=Memory(p['DMA_PAYLOAD_TARGET_GBS']*1e9,700,p['DMA_READ_MO'],p['DMA_WRITE_MO'],p['DMA_MAX_BURST_BYTES'])
            size=16*1024**2;t=mem.transfer(size,0.,kind)
            streams.append(dict(scale=p['SCALE'],direction=kind,MO=mem.mo[kind],
                                payload_target_GBs=p['DMA_PAYLOAD_TARGET_GBS'],modeled_GBs=size/t/1e9))
            assert size/t/1e9>=p['DMA_PAYLOAD_TARGET_GBS']*.995
    for name,data in [('spec_results',rows),('spec_mo_sweep',mos),('spec_streams',streams)]:
        with (ROOT/(name+'.csv')).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=data[0].keys(),lineterminator="\n");w.writeheader();w.writerows(data)
    (ROOT/'profiles.json').write_text(json.dumps(profiles,indent=2))
    (ROOT/'spec_results.json').write_text(json.dumps(dict(profiles=profiles,workloads=rows,streams=streams,mo_sweep=mos),indent=2))
    for p in profiles.values():
        print(f"x{p['SCALE']}: {p['PEAK_TOPS']:.2f} TOPS, AXI {p['AXI_DATA_BITS']}b @ 625MHz: raw {p['AXI_RAW_GBS']:.1f}, after 60% {p['AXI_AFTER_EFFICIENCY_GBS']:.1f}, guaranteed-model {p['DMA_PAYLOAD_TARGET_GBS']:.1f} GB/s; min full-burst MO {p['FULL_BURST_MIN_READ_MO']}")
    for r in rows:
        print(f"x{r['scale']} {r['case']} {r['M']}x{r['N']}x{r['K']}: {r['model_TOPS']:.4f} TOPS, {r['model_us']:.3f}us, MAC util {r['MAC_utilization']:.1%}")
    print('All capacity, ID, local bandwidth, roofline, streaming checks: PASS')
if __name__=='__main__':main()
