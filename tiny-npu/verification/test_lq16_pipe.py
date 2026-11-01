#!/usr/bin/env python3
"""Exact Fraction golden and old wide RTL versus native staged FMA."""
import itertools,json,math,random,re,shutil,sys
from pathlib import Path
from fractions import Fraction
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'architecture/v2'),str(ROOT/'sim')]
from precision import decode,encode,fma
from run_extended import compile_run
rng=random.Random(27121)
edge=[0,0x8000,1,0x8001,0xff,0x100,0x101,0x3f00,0xbf00,0x3e00,0x7eff,0xfeff,0x7f00,0xff00,0x7f80,0x3f01]
vectors=list(itertools.product(edge,repeat=3))
# Every encoding through multiply-by-one and add-to-zero, plus full mantissa grid.
vectors.extend((bits,0x3f00,0) for bits in range(65536))
vectors.extend((0,0,bits) for bits in range(65536))
vectors.extend((0x3f00|a,0x3f00|b,0) for a in range(256) for b in range(256))
for i in range(16000):
 a,b=rng.randrange(65536),rng.randrange(65536);aa,bb=decode(a,7,8),decode(b,7,8)
 if isinstance(aa,Fraction) and isinstance(bb,Fraction):
  cc=encode(-aa*bb,7,8)
  for delta in (-1,0,1):vectors.append((a,b,(cc+delta)&65535))
while len(vectors)<262144:vectors.append(tuple(rng.randrange(65536) for _ in range(3)))
golden=[fma(a,b,c,7,8) for a,b,c in vectors]
from analyze_trace import analyze
from trace import to_vcd
rows=[]
for latency,gaps,flush in [(11,0,0),(11,1,1),(13,1,0)]:
 d=ROOT/f'build/lq16-pipe-{latency}-g{gaps}-f{flush}';d.mkdir(parents=True,exist_ok=True)
 with (d/'vectors.hex').open('w') as out:
  for (a,b,c),expected in zip(vectors,golden):out.write(f'{a:04x}{b:04x}{c:04x}{expected:04x}\n')
 log=compile_run(d,'tb_lq16_pipe',['rtl/tiny_npu_lq16_fma_proto.sv','rtl/tiny_npu_lq16_fma_pipe.sv','sim/tb_lq16_pipe.sv'],{'COUNT':len(vectors),'LATENCY':latency,'GAPS':gaps,'FLUSH':flush},shutil.which('verilator'),run_args=['+PIPE_TRACE=pipe_trace.jsonl'])
 assert 'LQ16_PIPE_PASS' in log
 to_vcd(d/'pipe_trace.jsonl',d/'pipe_trace.vcd.gz');summary=analyze(d/'pipe_trace.jsonl',d/'analysis')
 assert len(summary['channels'])==latency+1
 count=int(re.search(r'comparisons=(\d+)',log).group(1));skipped=int(re.search(r'skipped=(\d+)',log).group(1));assert count+skipped==len(vectors)
 rows.append(dict(status='PASS',vectors=len(vectors),comparisons=count,reset_flushed=skipped,valid_gaps=bool(gaps),latency=latency,arithmetic_stages=11,golden='exact Fraction RNE plus wide RTL reference',scope='native staged FMA; 13cycle case includes2 explicit output transport stages'))
(ROOT/'architecture/v2/lq16_pipe_tests.json').write_text(json.dumps(rows,indent=2)+'\n')
