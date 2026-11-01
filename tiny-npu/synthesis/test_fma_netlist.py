#!/usr/bin/env python3
"""Regression on the exact gate netlists whose depth is reported; not formal proof."""
import json,random,sys
from pathlib import Path
from collections import deque
from netlist_sim import Netlist
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'architecture/v2'))
from precision import fma
rows=[]
for latency in (11,13):
 path=ROOT/f'build/synthesis-pipe/latency-{latency}/netlist.json';m=json.loads(path.read_text())['modules']['tiny_npu_lq16_fma_pipe'];sim=Netlist(m);rng=random.Random(201);pending=deque();checked=0;flushed=0
 sim.tick(reset=1);sim.tick(reset=1)
 edge=[0,0x8000,1,0x8001,0xff,0x100,0x3f00,0x3f01,0xbf00,0x7eff,0xfeff,0x7f00,0x7f80]
 for cycle in range(4500):
  reset=int(cycle==2000);ready=int(rng.random()<.7);valid=int(cycle<4300 and rng.random()<.8)
  a,b,c=[rng.choice(edge) if cycle%2 else rng.randrange(65536) for _ in range(3)]
  out=sim.tick(reset=reset,in_valid=valid,out_ready=ready,a=a,b=b,c=c)
  if reset:flushed+=len(pending);pending.clear();continue
  if out['out_valid']:
   assert pending and out['result']==pending[0],(latency,cycle,out,pending)
   if ready:pending.popleft();checked+=1
  if valid and out['in_ready']:pending.append(fma(a,b,c,7,8))
 assert not pending and checked>2000
 rows.append(dict(latency=latency,status='PASS',checked=checked,reset_flushed=flushed));print(rows[-1],flush=True)
(ROOT/'architecture/v2/fma_netlist_tests.json').write_text(json.dumps(rows,indent=2)+'\n')
