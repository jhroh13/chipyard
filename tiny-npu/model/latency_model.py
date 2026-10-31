#!/usr/bin/env python3
"""Deterministic burst/ID event model. Not RTL/DRAM timing simulation."""
from pathlib import Path
from dataclasses import replace
import csv, heapq, json, math
from model import Config

class Memory:
    def __init__(self, bw, latency_ns, read_mo, write_mo, burst):
        self.bw=bw; self.lat=latency_ns*1e-9
        self.mo={'R':read_mo,'W':write_mo}; self.ids={'R':[],'W':[]}
        self.issue={'R':0.,'W':0.}; self.bus=0.
        self.burst=burst; self.bytes={'R':0,'W':0}; self.requests={'R':0,'W':0}
    def transfer(self, size, ready, kind):
        """Aligned contiguous stream; 4KiB splits. R latency precedes data;
        W data may start immediately, B completion follows data by latency.
        Shared payload bus, 1ns issue interval per direction, in-order service.
        IDs are held until final R beat / B completion. No response reorder.
        """
        address=0; completed=ready
        while address<size:
            length=min(self.burst,size-address,4096-address%4096)
            issue=max(ready,self.issue[kind]); active=self.ids[kind]
            while active and active[0]<=issue: heapq.heappop(active)
            if len(active)>=self.mo[kind]:
                issue=max(issue,heapq.heappop(active))
                while active and active[0]<=issue: heapq.heappop(active)
            available=issue+(self.lat if kind=='R' else 0.)
            data_end=max(self.bus,available)+length/self.bw
            self.bus=data_end
            end=data_end+(self.lat if kind=='W' else 0.)
            heapq.heappush(active,end)
            self.issue[kind]=issue+1e-9
            completed=max(completed,end)
            self.bytes[kind]+=length; self.requests[kind]+=1
            address+=length
        return completed

def simulate(m,n,k,mo=32,write_mo=16,burst=2048,latency_ns=700,
             nominal_bw=10e9,efficiency=.60,cfg=Config()):
    assert all(v>0 and v%32==0 for v in (m,n,k))
    memory=Memory(nominal_bw*efficiency,latency_ns,mo,write_mo,burst)
    now=0.; jobs=0
    for mi in range(0,m,cfg.macro_m):
        for ni in range(0,n,cfg.macro_n):
            mm=min(cfg.macro_m,m-mi);nn=min(cfg.macro_n,n-ni)
            assert 4*mm*nn<=cfg.c_bytes
            tile_count=mm//32*(nn//32)
            compute=math.ceil(tile_count/cfg.arrays)*32/cfg.clock_hz
            finishes=[]; compute_end=now
            for block in range(k//32):
                ready=now if block<2 else finishes[block-2]
                # Four separately aligned streams: A, B, A-scale, B-scale.
                ends=[memory.transfer(size,ready,'R') for size in (mm*16,nn*32,mm,nn)]
                compute_end=max(compute_end,*ends)+compute
                finishes.append(compute_end)
            now=memory.transfer(mm*nn*4,compute_end,'W')
            jobs+=1
    ops=2*m*n*k; traffic=sum(memory.bytes.values())
    bound=min(cfg.peak,memory.bw*ops/traffic)
    assert ops/now<=bound*(1+1e-9)
    return dict(M=m,N=n,K=k,read_MO=mo,write_MO=write_mo,burst_bytes=burst,
                read_latency_ns=latency_ns,write_response_tail_ns=latency_ns,
                nominal_GBs=nominal_bw/1e9,efficiency=efficiency,effective_GBs=memory.bw/1e9,
                read_bytes=memory.bytes['R'],write_bytes=memory.bytes['W'],
                read_requests=memory.requests['R'],write_requests=memory.requests['W'],
                time_us=now*1e6,TOPS=ops/now/1e12,peak_utilization=ops/(now*cfg.peak),
                achieved_payload_GBs=traffic/now/1e9,roofline_TOPS=bound/1e12)

def main():
    root=Path(__file__).resolve().parent
    workloads=[(32,32,32),(256,256,1024),(512,384,4096),(608,320,4096),(608,320,65536),(1024,1024,4096)]
    rows=[simulate(*s) for s in workloads]
    sweep=[simulate(608,320,4096,mo=mo,write_mo=min(mo,16)) for mo in (1,2,3,4,8,16,32,64)]
    stream=[]
    for mo in (1,2,3,4,8,16,32,64):
        mem=Memory(6e9,700,mo,min(mo,16),2048)
        t=mem.transfer(16*1024*1024,0.,'R')
        stream.append(dict(MO=mo,sustained_read_GBs=16*1024*1024/t/1e9,
                           full_burst_occupancy_bound_GBs=min(6.,mo*2048/(700e-9+2048/6e9)/1e9)))
    for name,data in [('latency_results',rows),('mo_sweep',sweep),('stream_bw',stream)]:
        with (root/(name+'.csv')).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=data[0].keys());w.writeheader();w.writerows(data)
    # Verify one-tile traffic incl. two scale streams, and finite-MO serialization.
    assert rows[0]['read_bytes']==1600 and rows[0]['write_bytes']==4096
    assert stream[0]['sustained_read_GBs']<2.0
    assert stream[-1]['sustained_read_GBs']>5.99
    assert all(sweep[i]['time_us']>=sweep[i+1]['time_us']-1e-8 for i in range(len(sweep)-1))
    (root/'latency_results.json').write_text(json.dumps(dict(workloads=rows,mo_sweep=sweep,stream=stream),indent=2))
    print('DEFAULT: 10 GB/s nominal x 60% = 6 GB/s payload; R latency 700ns; W response tail 700ns; read/write MO 32/16; max burst 2048B')
    for r in rows:
        print(f"{r['M']}x{r['N']}x{r['K']}: {r['TOPS']:.4f} TOPS, {r['time_us']:.3f} us, peak-util {r['peak_utilization']:.1%}, effective-payload {r['achieved_payload_GBs']:.3f} GB/s")
    print('MO sweep: MO, long-read GB/s, matmul TOPS')
    for s,r in zip(stream,sweep): print(s['MO'],round(s['sustained_read_GBs'],4),round(r['TOPS'],4))
    print('Full-burst MO for 6GB/s:')
    for size in (64,128,256,512,1024,2048,4096):
        print(size,math.ceil(1+6e9*700e-9/size))
    print('Consistency checks: PASS')

if __name__=='__main__': main()
