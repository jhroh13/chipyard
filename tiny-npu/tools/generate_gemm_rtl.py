#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Emit R2 stream-GEMM wrappers; full SRAM/AXI/RoCC integration remains pending."""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'model'))
from p0_model import profile
SOURCES=['tiny_npu_fp32_from_scaled_int.sv','tiny_npu_mxfp4_matmul.sv',
         'tiny_npu_fp32_add_pipe.sv','tiny_npu_sram_bank.sv',
         'tiny_npu_k_accumulator.sv','tiny_npu_gemm_stream.sv']
def generate(scale,lint,v):
 p=profile(scale);a=p['ARRAY_COUNT'];lanes=a*32
 d=ROOT/f'build/generated-gemm/x{scale}';d.mkdir(parents=True,exist_ok=True)
 for n in SOURCES:shutil.copyfile(ROOT/'rtl'/n,d/n)
 name=f'tiny_npu_gemm_x{scale}'
 s=f'''// Generated R2 stream-GEMM; no AXI DMA or RoCC wrapper.
`timescale 1ns/1ps
module {name}(
 input logic clk,reset,job_valid, output logic job_ready,
 input logic [15:0] job_k_blocks,input logic [31:0] job_id,
 input logic in_valid,output logic in_ready,
 input logic [{a*128-1}:0] in_a,
 input logic [{a*256-1}:0] in_b,in_scale_a,in_scale_b,
 input logic [{a-1}:0] in_active,
 output logic out_valid,input logic out_ready,
 output logic [{lanes*32-1}:0] out_data,
 output logic [31:0] out_tile_id,output logic [4:0] out_chunk,output logic out_last
);
 tiny_npu_gemm_stream #(.ARRAYS({a})) core(.*);
endmodule
'''
 (d/(name+'.sv')).write_text(s)
 p.update(RTL_STAGE='R2_STREAM_GEMM',FP32_K_ACCUM_IMPLEMENTED=True,
          C_SRAM_SLICE_IMPLEMENTED=True,FULL_SRAM_SUBSYSTEM_IMPLEMENTED=False,
          DMA_IMPLEMENTED=False,ROCC_IMPLEMENTED=False,
          IMPLEMENTED_C_READ_LATENCY_CYCLES=1,IMPLEMENTED_FP32_ADD_LATENCY_CYCLES=4)
 (d/'parameters.json').write_text(json.dumps(p,indent=2))
 files=SOURCES+[name+'.sv'];(d/'rtl.f').write_text('\n'.join(files)+'\n')
 (d/'manifest.json').write_text(json.dumps({n:hashlib.sha256((d/n).read_bytes()).hexdigest() for n in files},indent=2))
 if lint:
  with (d/'lint.log').open('w') as f:subprocess.run([v,'--lint-only','--top-module',name]+files,cwd=d,stdout=f,stderr=subprocess.STDOUT,check=True)
 print(f'Generated R2 x{scale}, arrays={a}, K-block FP32 accumulation, lint={lint}',flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--scale',type=int,nargs='+',choices=[1,2,4],default=[1,2,4]);ap.add_argument('--lint',action='store_true');ap.add_argument('--verilator',default=shutil.which('verilator') or 'verilator');a=ap.parse_args()
 for s in a.scale:generate(s,a.lint,a.verilator)
