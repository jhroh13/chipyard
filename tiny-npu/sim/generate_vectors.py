#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independent integer-dot + host IEEE FP32 packing reference. No numpy dependency."""
import argparse,json,math,random,struct
from pathlib import Path
COEFF=(0,1,2,3,4,6,8,12)
def fp4(code): return COEFF[code&7]*(-1 if code&8 else 1)
def ieee(value,sa,sb):
    if sa==255 or sb==255:return 0x7fc00000
    if value==0:return 0
    real=math.ldexp(float(value),sa+sb-262)
    try:return struct.unpack('<I',struct.pack('<f',real))[0]
    except OverflowError:return 0xff800000 if real<0 else 0x7f800000

def generate(dest,arrays,cases=12):
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=True);rng=random.Random(20261101)
    names=['zero','identity','max_product','all_fp4_encodings','random_normal',
           'inactive_arrays','signed_cancellation','invalid_scale_nan',
           'gradual_underflow','overflow','random_scale_range','mixed_extremes']
    streams={n:[] for n in ('a','b','sa','sb','mask','expected')}
    meta=[]
    for case in range(cases):
        active=(1<<arrays)-1
        if case==5:active=sum(1<<a for a in range(arrays) if a%2==0)
        matrices=[];sa_vec=[];sb_vec=[]
        for ar in range(arrays):
            a=[[rng.randrange(16) for k in range(32)] for i in range(32)]
            b=[[rng.randrange(-128,128) for j in range(32)] for k in range(32)]
            sa=[127]*32;sb=[127]*32
            if case==0:a=[[0]*32 for _ in range(32)]
            if case==1:a=[[2 if i==k else 0 for k in range(32)] for i in range(32)];sb=[134]*32
            if case==2:a=[[15]*32 for _ in range(32)];b=[[-128]*32 for _ in range(32)]
            if case==3:a=[[(i+k)%16 for k in range(32)] for i in range(32)]
            if case==6:
                a=[[2 if k%2==0 else 10 for k in range(32)] for i in range(32)]
                b=[[j-16 for j in range(32)] for k in range(32)]
            if case==7:sa=[255 if i%3==0 else 127 for i in range(32)];sb=[255 if j%5==0 else 127 for j in range(32)]
            if case==8:sa=[24+i%8 for i in range(32)];sb=[80+j%16 for j in range(32)]
            if case==9:sa=[240]*32;sb=[240]*32
            if case==10:sa=[rng.randrange(100,150) for _ in range(32)];sb=[rng.randrange(100,150) for _ in range(32)]
            if case==11:sa=[(0,1,64,127,190,254,255,30)[i%8] for i in range(32)];sb=[(0,254,127,255,90,200,128,60)[j%8] for j in range(32)]
            matrices.append((a,b,sa,sb));sa_vec.extend(sa);sb_vec.extend(sb)
            for i in range(32):
                for j in range(32):
                    value=sum(fp4(a[i][k])*b[k][j] for k in range(32))
                    streams['expected'].append(ieee(value,sa[i],sb[j]) if active&(1<<ar) else 0)
        for k in range(32):
            avec=[];bvec=[]
            for a,b,_,_ in matrices:
                avec.extend(a[i][k] for i in range(32));bvec.extend(b[k][j]&255 for j in range(32))
            streams['a'].append(sum(x<<(4*i) for i,x in enumerate(avec)))
            streams['b'].append(sum(x<<(8*i) for i,x in enumerate(bvec)))
        streams['sa'].append(sum(x<<(8*i) for i,x in enumerate(sa_vec)))
        streams['sb'].append(sum(x<<(8*i) for i,x in enumerate(sb_vec)))
        streams['mask'].append(active);meta.append(dict(case=case,name=names[case],active_mask=active))
    widths=dict(a=arrays*32,b=arrays*64,sa=arrays*64,sb=arrays*64,mask=(arrays+3)//4,expected=8)
    for key,values in streams.items():
        (dest/(key+'.hex')).write_text(''.join(f'{v:0{widths[key]}x}\n' for v in values))
    (dest/'vectors.json').write_text(json.dumps(dict(seed=20261101,arrays=arrays,cases=meta,checked_elements=arrays*1024*cases),indent=2))
    return meta
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--arrays',type=int,default=5);a=ap.parse_args();generate(a.out,a.arrays)
