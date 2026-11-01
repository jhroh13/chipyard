#!/usr/bin/env python3
"""Exact rational rounding reference for proposed LQ16 and TF32 arithmetic.
No host FP32 accumulator is used for the reduced-precision FMA reference.
"""
from fractions import Fraction as F
from pathlib import Path
import json,math,random
OUT=Path(__file__).resolve().parent

def pow2(e):return F(1<<e) if e>=0 else F(1,1<<(-e))
def rne(x):
 q,r=divmod(x.numerator,x.denominator)
 return q+int(2*r>x.denominator or (2*r==x.denominator and q&1))
def decode(bits,e,m):
 sign=-1 if bits>>(e+m) else 1;ex=(bits>>m)&((1<<e)-1);fr=bits&((1<<m)-1);bias=(1<<(e-1))-1
 if ex==(1<<e)-1:return math.nan if fr else sign*math.inf
 if ex==0:return sign*F(fr)*pow2(1-bias-m)
 return sign*F((1<<m)+fr)*pow2(ex-bias-m)
def encode(x,e,m,negative_zero=False):
 bias=(1<<(e-1))-1;all_exp=(1<<e)-1
 if isinstance(x,float) and not math.isfinite(x):
  if math.isnan(x):return (all_exp<<m)|(1<<(m-1))
  return (int(x<0)<<(e+m))|(all_exp<<m)
 x=F(x);sign=int(x<0 or (x==0 and negative_zero));x=abs(x)
 if x==0:return sign<<(e+m)
 exponent=x.numerator.bit_length()-x.denominator.bit_length()
 if x<pow2(exponent):exponent-=1
 min_exp=1-bias;max_exp=all_exp-1-bias
 if exponent<min_exp:
  q=rne(x/pow2(min_exp-m))
  return (sign<<(e+m))|q
 q=rne(x/pow2(exponent-m))
 if q==(1<<(m+1)):q>>=1;exponent+=1
 if exponent>max_exp:return (sign<<(e+m))|(all_exp<<m)
 return (sign<<(e+m))|((exponent+bias)<<m)|(q-(1<<m))
def fma(a,b,c,e,m):
 aa=decode(a,e,m);bb=decode(b,e,m);cc=decode(c,e,m)
 # Test vectors are finite; special-value hardware policy is separately specified.
 if not all(isinstance(x,F) for x in (aa,bb,cc)):return encode(float(aa)*float(bb)+float(cc),e,m)
 return encode(aa*bb+cc,e,m)
def target_tf32(value):return encode(value,8,10)<<13

def main():
 for bits in range(65536):
  value=decode(bits,7,8);expected=0x7f80 if isinstance(value,float) and math.isnan(value) else bits
  assert encode(value,7,8,negative_zero=bits==0x8000)==expected
  # Every finite LQ16 value widens exactly to TF32.
  if isinstance(value,F):assert decode(target_tf32(value)>>13,8,10)==value
 rng=random.Random(20261105);rows=[]
 for k in (32,128,4096):
  for case in range(4):
   values=[(F(rng.choice([0,1,-1,2,-2,3,-3,4,-4,6,-6]),2),F(rng.randrange(-128,128),128)) for _ in range(k)]
   ref=sum((a*b for a,b in values),F(0))
   for name,e,m in [('LQ16_S1_E7_M8',7,8),('TF32_S1_E8_M10',8,10)]:
    acc=encode(0,e,m)
    for a,b in values:acc=fma(encode(a,e,m),encode(b,e,m),acc,e,m)
    value=decode(acc,e,m)
    rows.append(dict(K=k,case=case,mode=name,exact_reference=float(ref),result=float(value),absolute_error=float(abs(value-ref)),target_tf32_hex=f'{target_tf32(value):08x}'))
 result=dict(status='PASS',LQ16_exhaustive_roundtrips=65536,finite_LQ16_to_TF32_exact=True,synthetic_FMA_sequences=len(rows),seed=20261105,results=rows,scope='software numerical reference; not MAC RTL/PPA or model accuracy validation')
 (OUT/'precision_results.json').write_text(json.dumps(result,indent=2));print('LQ16 exhaustive format roundtrips=65536 PASS; exact TF32 widening PASS; FMA sequences=',len(rows))
if __name__=='__main__':main()
