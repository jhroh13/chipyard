#!/usr/bin/env python3
"""Functional regression on the audited 8x8/32-bit gate netlist, no SRAM model."""
import hashlib,json,random
from pathlib import Path
from netlist_sim import Netlist
ROOT=Path(__file__).resolve().parents[1];path=ROOT/'build/bank-depth-fabric8/netlist.json';module=json.loads(path.read_text())['modules']['tiny_npu_hashed_bank_fabric'];rows=[]
def pack(values,width):return sum(v<<((7-p)*width) for p,v in enumerate(values))
def field(out,name,index,width):return (out[name]>>((7-index)*width))&((1<<width)-1)
for hashing in (False,True):
 sim=Netlist(module);rng=random.Random(822);sim.tick(reset=1);sim.tick(reset=1)
 if not hashing:
  out=sim.tick(sfr_valid=1,sfr_write=1,sfr_addr=0,sfr_wdata=0x200,layout_change_safe=1,returns_idle=1);assert out['sfr_ready'] and not out['sfr_error']
 sent=[0]*8;ledger={};checked=0;held={}
 for cycle in range(2000):
  tags=[sent[p]*8+p for p in range(8)];row=[tag*4 for tag in tags];data=[((0xcafe0000+r)^((t*2654435761)&0xffffffff)) for r,t in zip(row,tags)];masks=[((t*3)^10)&15 for t in tags];ready=sum(int(rng.random()<.75)<<b for b in range(8))
  out=sim.tick(req_valid=sum(int(n<16)<<p for p,n in enumerate(sent)),req_write=170,req_bank=0,req_row=pack(row,10),req_data=pack(data,32),req_mask=pack(masks,4),req_tag=pack(tags,16),bank_ready=ready,returns_idle=1,layout_change_safe=0)
  assert out['cfg_hash_enable']==hashing and out['cfg_monitor_enable']==1
  for p in range(8):
   if sent[p]<16 and (out['req_ready']>>p)&1:
    ledger[tags[p]]=(row[p],data[p],((row[p]>>2)&7) if hashing else 0,masks[p]);sent[p]+=1
  for b in range(8):
   valid=(out['bank_valid']>>b)&1;packet=(field(out,'bank_row',b,10),field(out,'bank_data',b,32),field(out,'bank_tag',b,16),field(out,'bank_mask',b,4),(out['bank_write']>>b)&1)
   if b in held:assert valid and packet==held[b]
   if valid and not ((ready>>b)&1):held[b]=packet
   else:held.pop(b,None)
   if valid and (ready>>b)&1:
    r,d,t,m,w=packet;assert t in ledger and (r,d,b,m)==ledger.pop(t) and w==((t%8)%2);checked+=1
  if all(n==16 for n in sent) and not ledger and out['idle']:break
 else:raise AssertionError('gate-netlist deadlock')
 assert checked==128
 rows.append(dict(hashing=hashing,checked=checked,status='PASS',cycles=cycle+1));print(rows[-1],flush=True)
(ROOT/'architecture/v2/bank_netlist_tests.json').write_text(json.dumps(dict(scope='audited 8x8/32-bit netlist; randomized command stalls, exact tags/data/bank routing, stable output, default monitor/hash and SFR linear selection; not formal equivalence or full256-bit post-synth test',netlist_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),cases=rows),indent=2)+'\n')
