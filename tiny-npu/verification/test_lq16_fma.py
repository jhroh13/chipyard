#!/usr/bin/env python3
import itertools,json,random,sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'architecture/v2'),str(ROOT/'sim')]
from precision import fma
from run_extended import compile_run
rng=random.Random(27011)
edge=[0,0x8000,1,0x8001,0xff,0x100,0x3f00,0xbf00,0x3e00,0x7eff,0xfeff,0x7f00,0xff00,0x7f80]
vectors=list(itertools.product(edge,repeat=3))
while len(vectors)<6000:vectors.append(tuple(rng.randrange(65536) for _ in range(3)))
rows=[]
for latency in (4,6):
 d=ROOT/f'build/lq16-fma-{latency}';d.mkdir(parents=True,exist_ok=True)
 with (d/'vectors.hex').open('w') as out:
  for a,b,c in vectors:out.write(f'{a:04x}{b:04x}{c:04x}{fma(a,b,c,7,8):04x}\n')
 log=compile_run(d,'tb_lq16_fma',['rtl/tiny_npu_lq16_fma_proto.sv','sim/tb_lq16_fma.sv'],{'COUNT':len(vectors),'LATENCY':latency},shutil.which('verilator'))
 assert 'LQ16_FMA_PASS' in log;rows.append(dict(status='PASS',vectors=len(vectors),latency=latency,scope='exact arithmetic plus transport pipeline; not timing-balanced arithmetic stages'))
(ROOT/'architecture/v2/lq16_fma_tests.json').write_text(json.dumps(rows,indent=2)+'\n')
