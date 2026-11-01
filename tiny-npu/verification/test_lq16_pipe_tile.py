#!/usr/bin/env python3
import json,random,shutil,sys
from pathlib import Path
from fractions import Fraction as F
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'architecture/v2'),str(ROOT/'sim')]
from precision import encode,decode,fma,pow2,target_tf32
from run_extended import compile_run
COEFF=(0,1,2,3,4,6,8,12)
rng=random.Random(27011);rows=[];contexts=12;groups=(1024+contexts-1)//contexts
for name,K,contexts,latency in [('zero',32,12,11),('identity',32,12,11),('random',32,12,11),('random_scales_K64',64,12,11),('random_K64_L13',64,16,13)]:
 groups=(1024+contexts-1)//contexts
 A=[[rng.randrange(16) for k in range(K)] for r in range(32)];B=[[rng.randrange(-128,128) for col in range(32)] for k in range(K)]
 AS=[[rng.randrange(125,130) for kt in range(K//32)] for r in range(32)];BS=[[rng.randrange(125,130) for kt in range(K//32)] for c in range(32)]
 if name=='zero':A=[[0]*K for r in range(32)]
 if name=='identity':A=[[2 if r==k else 0 for k in range(K)] for r in range(32)];AS=[[127] for r in range(32)];BS=[[134] for c in range(32)]
 acc=[0]*1024;operands=[];expected=[]
 for batch in range(groups):
  for k in range(K):
   for ctx in range(contexts):
    pixel=batch*contexts+ctx;
    if pixel>=1024:operands.append(0);expected.append(0);continue
    r,col=divmod(pixel,32);code=A[r][k]
    av=F(COEFF[code&7]*(-1 if code&8 else 1),2)*pow2(AS[r][k//32]-127)
    bv=F(B[k][col],128)*pow2(BS[col][k//32]-127)
    aa=encode(av,7,8);bb=encode(bv,7,8);acc[pixel]=fma(aa,bb,acc[pixel],7,8)
    operands.append((aa<<16)|bb);expected.append(acc[pixel])
 if name=='identity':assert all(decode(acc[r*32+c],7,8)==B[r][c] for r in range(32) for c in range(32))
 d=ROOT/f'build/lq16-pipe-tile-{name}';d.mkdir(parents=True,exist_ok=True)
 (d/'operands.hex').write_text(''.join(f'{x:08x}\n' for x in operands));(d/'expected.hex').write_text(''.join(f'{x:04x}\n' for x in expected))
 (d/'final_tf32_reference.hex').write_text(''.join(f'{target_tf32(decode(x,7,8)):08x}\n' for x in acc))
 log=compile_run(d,'tb_lq16_pipe_tile',['rtl/tiny_npu_lq16_fma_pipe.sv','sim/tb_lq16_pipe_tile.sv'],{'K':K,'CONTEXTS':contexts,'LATENCY':latency},shutil.which('verilator'));assert 'LQ16_PIPE_TILE_PASS' in log
 rows.append(dict(case=name,M=32,N=32,K=K,FMA_comparisons=len(expected),useful_FMA_comparisons=1024*K,masked_contexts=groups*contexts-1024,contexts=contexts,latency=latency,status='PASS',scope='native11-stage LQ16 FMA with configured latency/context feedback and masked tails; MX decode/scales performed by testbench host; no MAC array/TF32 store integration'))
(ROOT/'architecture/v2/lq16_pipe_tile_tests.json').write_text(json.dumps(rows,indent=2)+'\n')
