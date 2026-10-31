#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
import argparse,json,math,random,struct,subprocess,time,shutil
from pathlib import Path
from generate_vectors import fp4,ieee
ROOT=Path(__file__).resolve().parents[1]
def bits(f):
 try:return struct.unpack('<I',struct.pack('<f',f))[0]
 except OverflowError:return 0xff800000 if f<0 else 0x7f800000
def val(b):return struct.unpack('<f',struct.pack('<I',b))[0]
def add(a,b):
 v=val(a)+val(b)
 return 0x7fc00000 if math.isnan(v) else bits(v)
def write(path,values,width=8):path.write_text(''.join(f'{x:0{width}x}\n' for x in values))
def compile_run(folder,top,sources,params,verilator):
 folder.mkdir(parents=True,exist_ok=True)
 cmd=[verilator,'--binary','--timing','-j','4','--top-module',top,'--Mdir',str(folder/'obj'),'-o','Vtest']
 cmd += [f'-G{k}={v}' for k,v in params.items()]+[str(ROOT/s) for s in sources]
 with (folder/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
 with (folder/'simulation.log').open('w') as f:subprocess.run([str(folder/'obj/Vtest')],cwd=folder,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
 log=(folder/'simulation.log').read_text();print(log,flush=True);return log

def adder(verilator):
 f=ROOT/'build/fp32-add';f.mkdir(parents=True,exist_ok=True);rng=random.Random(20261102)
 edge=[0,0x80000000,1,0x80000001,0x007fffff,0x00800000,0x3f800000,0xbf800000,0x7f7fffff,0xff7fffff,0x7f800000,0xff800000,0x7fc00000,0x7fa00000,0x33800000]
 pairs=[(a,b) for a in edge for b in edge]
 while len(pairs)<20000:pairs.append((rng.getrandbits(32),rng.getrandbits(32)))
 write(f/'add_a.hex',[a for a,b in pairs]);write(f/'add_b.hex',[b for a,b in pairs]);write(f/'add_expected.hex',[add(a,b) for a,b in pairs])
 log=compile_run(f,'tb_fp32_add',['rtl/tiny_npu_fp32_add_pipe.sv','sim/tb_fp32_add.sv'],{'COUNT':len(pairs)},verilator)
 assert 'FP32_ADD_PASS' in log
 return dict(test='fp32_add',comparisons=len(pairs),status='PASS',seed=20261102)

def hazard(verilator):
    f=ROOT/'build/c-hazard'
    log=compile_run(f,'tb_c_hazard',['rtl/tiny_npu_fp32_add_pipe.sv','rtl/tiny_npu_sram_bank.sv','rtl/tiny_npu_k_accumulator.sv','sim/tb_c_hazard.sv'],{},verilator)
    assert 'C_HAZARD_PASS' in log
    return dict(test='C_same_row_RMW_hazard',comparisons=3,status='PASS')

def dma_frontend(verilator):
    f=ROOT/'build/dma-frontend'
    log=compile_run(f,'tb_dma_frontend',['rtl/tiny_npu_dma_burst_planner.sv','rtl/tiny_npu_dma_read_credits.sv','sim/tb_dma_frontend.sv'],{},verilator)
    assert 'DMA_FRONTEND_PASS' in log
    return dict(test='DMA_request_planner_and_byte_credits',status='PASS',scope='Not an AXI master or full DMA engine')

def gemm_vectors(f,arrays):
 f.mkdir(parents=True,exist_ok=True);rng=random.Random(20261103)
 jobs=[1,2,4,128,2,2,2,2];names=['K32','K64_variable_scale','K128','K4096','cancellation','NaN','Inf_minus_Inf','subnormal']
 streams={n:[] for n in ('a','b','sa','sb','expected','ends','blocks')};offset=0
 for job,nblocks in enumerate(jobs):
  sums=[[0]*1024 for _ in range(arrays)]
  for block in range(nblocks):
   matrices=[];scales_a=[];scales_b=[]
   for ar in range(arrays):
    a=[[rng.randrange(16) for k in range(32)] for i in range(32)]
    b=[[rng.randrange(-128,128) for j in range(32)] for k in range(32)]
    sa=[126+(block%3)]*32;sb=[126+(block%5)]*32
    if job==4:
     a=[[2 if block==0 else 10]*32 for _ in range(32)];b=[[8]*32 for _ in range(32)];sa=[127]*32;sb=[127]*32
    if job==5 and block==1:sa=[255 if i%2 else 127 for i in range(32)]
    if job==6:
     a=[[7 if block==0 else 15]*32 for _ in range(32)];b=[[127]*32 for _ in range(32)];sa=[254]*32;sb=[254]*32
    if job==7:sa=[24+block+i%8 for i in range(32)];sb=[80+j%16 for j in range(32)]
    matrices.append((a,b));scales_a.extend(sa);scales_b.extend(sb)
    for i in range(32):
     for j in range(32):
      dot=sum(fp4(a[i][k])*b[k][j] for k in range(32))
      sums[ar][i*32+j]=add(sums[ar][i*32+j],ieee(dot,sa[i],sb[j]))
   for k in range(32):
    av=[];bv=[]
    for a,b in matrices:av.extend(a[i][k] for i in range(32));bv.extend(b[k][j]&255 for j in range(32))
    streams['a'].append(sum(x<<(4*i) for i,x in enumerate(av)));streams['b'].append(sum(x<<(8*i) for i,x in enumerate(bv)))
    streams['sa'].append(sum(x<<(8*i) for i,x in enumerate(scales_a)));streams['sb'].append(sum(x<<(8*i) for i,x in enumerate(scales_b)))
  offset+=32*nblocks;streams['ends'].append(offset);streams['blocks'].append(nblocks)
  for ar in range(arrays):streams['expected'].extend(sums[ar])
 widths=dict(a=arrays*32,b=arrays*64,sa=arrays*64,sb=arrays*64,expected=8,ends=8,blocks=4)
 for n,v in streams.items():write(f/(n+'.hex'),v,widths[n])
 (f/'vectors.json').write_text(json.dumps(dict(jobs=names,blocks=jobs,seed=20261103,arrays=arrays),indent=2))
 return len(jobs),offset,names

def gemm(arrays,verilator):
 f=ROOT/f'build/gemm-{arrays}';jobs,beats,names=gemm_vectors(f,arrays)
 src=['rtl/tiny_npu_fp32_from_scaled_int.sv','rtl/tiny_npu_mxfp4_matmul.sv','rtl/tiny_npu_fp32_add_pipe.sv','rtl/tiny_npu_sram_bank.sv','rtl/tiny_npu_k_accumulator.sv','rtl/tiny_npu_gemm_stream.sv','sim/tb_gemm.sv']
 log=compile_run(f,'tb_gemm',src,{'ARRAYS':arrays,'JOBS':jobs,'BEATS':beats},verilator)
 assert 'GEMM_PASS' in log
 return dict(test='gemm_stream',arrays=arrays,jobs=names,K_values=[32,64,128,4096,64,64,64,64],comparisons=jobs*arrays*1024,status='PASS',seed=20261103,scope='Stream-fed compute + C SRAM; no AXI DMA/RoCC or sustained TOPS proof')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--arrays',type=int,nargs='+',default=[1,2]);ap.add_argument('--only-adder',action='store_true');a=ap.parse_args();v=shutil.which('verilator')
 if not v:raise SystemExit('Activate Verilator first')
 results=[adder(v)]
 if not a.only_adder:results += [hazard(v),dma_frontend(v)]+[gemm(n,v) for n in a.arrays]
 (ROOT/'build/extended-summary.json').write_text(json.dumps(results,indent=2))
 print(json.dumps(results,indent=2))
