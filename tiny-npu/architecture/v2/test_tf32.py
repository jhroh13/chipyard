#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
import random,subprocess,shutil,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def tf32_bits(x):
 e=(x>>23)&255;m=x&0x7fffff
 if e==255:return 0x7fc00000 if m else x
 # Independent quotient/remainder ties-to-even, not the RTL bias-add formula.
 q=x>>13;r=x&8191
 if r>4096 or (r==4096 and q&1):q+=1
 return (q<<13)&0xffffffff

def main():
 b=ROOT/'build/tf32-format';b.mkdir(parents=True,exist_ok=True)
 rng=random.Random(20261104)
 values=[0,0x80000000,1,0x80000001,0x007fffff,0x00800000,0x3f801000,0x3f803000,0xbf801000,0xbf803000,0x7f7fffff,0xff7fffff,0x7f800000,0xff800000,0x7fc00001,0x7fa00000]
 values += [rng.getrandbits(32) for _ in range(20000-len(values))]
 (b/'input.hex').write_text(''.join(f'{v:08x}\n' for v in values))
 (b/'expected.hex').write_text(''.join(f'{tf32_bits(v):08x}\n' for v in values))
 v=shutil.which('verilator');assert v
 cmd=[v,'--binary','--timing','-j','4','--top-module','tb_tf32_format','--Mdir',str(b/'obj'),'-o','Vtest',str(ROOT/'rtl/tiny_npu_tf32_format.sv'),str(ROOT/'sim/tb_tf32_format.sv')]
 with (b/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 with (b/'simulation.log').open('w') as f:subprocess.run([str(b/'obj/Vtest')],cwd=b,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=60)
 log=(b/'simulation.log').read_text();assert 'TF32_FORMAT_PASS' in log
 result=dict(status='PASS',inputs=20000,seed=20261104,format='TF32 32-bit container, 10 fraction bits',scope='standalone format primitive, not integrated TARGETR/vector RTL')
 (Path(__file__).parent/'tf32_test.json').write_text(json.dumps(result,indent=2));print(log)
if __name__=='__main__':main()
