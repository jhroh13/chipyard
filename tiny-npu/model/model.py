#!/usr/bin/env python3
"""Analytical roofline + deterministic DMA/compute event model; NOT RTL simulation."""
from dataclasses import dataclass, replace, asdict
from pathlib import Path
import csv, json, math

@dataclass(frozen=True)
class Config:
    arrays: int = 5
    clock_hz: float = 1e9
    dram_bytes_s: float = 10e9  # shared read+write payload bandwidth
    tile: int = 32
    macro_m: int = 608
    macro_n: int = 320
    c_bytes: int = 768*1024
    operand_bytes: int = 1024*1024
    fp32_lanes: int = 160
    operand_read_bytes_cycle: int = 512
    scale_read_bytes_cycle: int = 128
    partial_read_bytes_cycle: int = 1024
    partial_write_bytes_cycle: int = 1024
    c_read_bytes_cycle: int = 768
    c_write_bytes_cycle: int = 768
    output_element_bytes: int = 4

    @property
    def macs_cycle(self): return self.arrays*self.tile*self.tile
    @property
    def peak(self): return 2*self.macs_cycle*self.clock_hz


def run(m, n, k, cfg=Config()):
    assert all(x > 0 and x % 32 == 0 for x in (m,n,k))
    total_time=0.; input_bytes=0; output_bytes=0; active_compute=0.; groups=0
    peak_elements=cfg.arrays*cfg.tile  # block results per cycle, averaged
    limiting_ratio=max(1., peak_elements/cfg.fp32_lanes,
        cfg.arrays*48/cfg.operand_read_bytes_cycle,
        cfg.arrays*2/cfg.scale_read_bytes_cycle,
        peak_elements*4/cfg.partial_read_bytes_cycle,
        peak_elements*4/cfg.partial_write_bytes_cycle,
        peak_elements*4/cfg.c_read_bytes_cycle,
        peak_elements*4/cfg.c_write_bytes_cycle)
    for mi in range(0,m,cfg.macro_m):
        for ni in range(0,n,cfg.macro_n):
            mm=min(cfg.macro_m,m-mi); nn=min(cfg.macro_n,n-ni)
            assert 4*mm*nn <= cfg.c_bytes
            # A: .5B + 1/32B scale; B: 1B + 1/32B scale.
            panel_bytes=17*mm+33*nn  # K=32
            assert 2*panel_bytes <= cfg.operand_bytes
            tiles=(mm//32)*(nn//32)
            compute_seconds=math.ceil(tiles/cfg.arrays)*32/cfg.clock_hz*limiting_ratio
            read_seconds=panel_bytes/cfg.dram_bytes_s
            dma_free=0.; compute_free=0.; finish=[]
            for block in range(k//32):
                # Two operand slots. A slot is released after its panel completes.
                slot_free=finish[block-2] if block>=2 else 0.
                start_read=max(dma_free,slot_free)
                dma_free=start_read+read_seconds
                compute_free=max(compute_free,dma_free)+compute_seconds
                finish.append(compute_free)
            out=cfg.output_element_bytes*mm*nn
            # Full C retained; store after final K block. No overlap across macros.
            total_time+=max(dma_free,compute_free)+out/cfg.dram_bytes_s
            input_bytes+=panel_bytes*(k//32); output_bytes+=out
            active_compute+=compute_seconds*(k//32); groups+=1
    ops=2*m*n*k
    traffic=input_bytes+output_bytes
    lower=max(ops/cfg.peak,traffic/cfg.dram_bytes_s)
    assert total_time+1e-12 >= lower
    return dict(M=m,N=n,K=k,arrays=cfg.arrays,bw_GBs=cfg.dram_bytes_s/1e9,
        macro_count=groups,input_bytes=input_bytes,output_bytes=output_bytes,
        operations=ops,ops_per_byte=ops/traffic,peak_TOPS=cfg.peak/1e12,
        roofline_TOPS=min(cfg.peak,cfg.dram_bytes_s*ops/traffic)/1e12,
        model_TOPS=ops/total_time/1e12,model_us=total_time*1e6,
        ideal_compute_us=ops/cfg.peak*1e6,dram_payload_us=traffic/cfg.dram_bytes_s*1e6,
        peak_utilization=ops/(total_time*cfg.peak),local_slowdown=limiting_ratio)


def main():
    root=Path(__file__).resolve().parent
    cfg=Config()
    cases=[(32,32,32),(256,256,1024),(512,384,4096),
           (608,320,4096),(608,320,65536),(1024,1024,4096)]
    rows=[run(*case,cfg) for case in cases]
    # Traffic accounting: isolated tile includes both block scales and FP32 C.
    assert rows[0]['input_bytes']==1600 and rows[0]['output_bytes']==4096
    assert cfg.macs_cycle==5120 and cfg.peak==10.24e12
    # Isolated one-panel job cannot overlap its input, computation and output.
    assert math.isclose(rows[0]['model_us'], (5696/10e9+32/1e9)*1e6)
    # A slower FP32 stage must throttle the design even with unlimited DRAM BW.
    slow=run(608,320,4096,replace(cfg,dram_bytes_s=1e15,fp32_lanes=64))
    assert slow['local_slowdown']==2.5 and slow['model_TOPS']<=4.096
    sweep=[run(608,320,4096,replace(cfg,arrays=a,dram_bytes_s=bw*1e9))
           for a in (1,2,5) for bw in (5,10,20,40,80,160)]
    with (root/'results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    with (root/'sweep.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=sweep[0].keys());w.writeheader();w.writerows(sweep)
    cap_outputs=cfg.c_bytes/4
    ai_limit=math.sqrt(cap_outputs/((17/32)*(33/32)))
    payload={'config':asdict(cfg),'cases':rows,'sweep':sweep,
             'resident_C_asymptotic_AI_limit':ai_limit,
             'resident_C_asymptotic_TOPS_at_10GBs':ai_limit*10e9/1e12}
    (root/'results.json').write_text(json.dumps(payload,indent=2))
    print('M N K | peak TOPS | roofline TOPS | model TOPS | model us | peak utilization')
    for r in rows:
        print(f"{r['M']} {r['N']} {r['K']} | {r['peak_TOPS']:.3f} | {r['roofline_TOPS']:.3f} | {r['model_TOPS']:.3f} | {r['model_us']:.3f} | {r['peak_utilization']:.1%}")
    print(f'768 KiB resident-C continuous-shape AI upper limit: {ai_limit:.3f} ops/B; {ai_limit*.01:.3f} TOPS at 10 GB/s (schedule-specific).')
    print('Model consistency checks: PASS')

if __name__=='__main__': main()
