#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Emit self-contained SV source trees and profile wrappers; optional elaboration lint."""
import argparse,hashlib,importlib.util,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location('spec_model',ROOT/'model/p0_model.py')
# The analytical model imports the event engine from its own directory.
import sys
sys.path.insert(0,str(ROOT/'model'));mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
def generate(scale,lint,verilator):
    p=mod.profile(scale);dest=ROOT/'build/generated'/f'x{scale}';dest.mkdir(parents=True,exist_ok=True)
    names=['tiny_npu_fp32_from_scaled_int.sv','tiny_npu_mxfp4_matmul.sv','tiny_npu_sram_bank.sv']
    for name in names:shutil.copyfile(ROOT/'rtl'/name,dest/name)
    a=p['ARRAY_COUNT'];lanes=p['FP32_ACC_LANES']
    wrapper=f'''// Generated profile x{scale}; K=32 compute core only, no DMA integration.
`timescale 1ns/1ps
module tiny_npu_x{scale} (
 input logic clk, reset, in_valid, output logic in_ready,
 input logic [{a*128-1}:0] in_a,
 input logic [{a*256-1}:0] in_b, in_scale_a, in_scale_b,
 input logic [{a-1}:0] in_active,
 input logic [31:0] in_tile_id,
 output logic out_valid, input logic out_ready,
 output logic [{lanes*32-1}:0] out_data,
 output logic [31:0] out_tile_id, output logic [4:0] out_chunk,
 output logic out_last
);
 tiny_npu_mxfp4_matmul #(.ARRAYS({a}),.OUT_LANES({lanes})) core(.*);
endmodule
'''
    (dest/f'tiny_npu_x{scale}.sv').write_text(wrapper)
    p.update(RTL_STATUS='R1_K32_COMPUTE_ONLY',DMA_IMPLEMENTED=False,FP32_K_ACCUM_IMPLEMENTED=False)
    (dest/'parameters.json').write_text(json.dumps(p,indent=2))
    (dest/'rtl.f').write_text('\n'.join(names+[f'tiny_npu_x{scale}.sv'])+'\n')
    if lint:
        cmd=[verilator,'--lint-only','--top-module',f'tiny_npu_x{scale}']+names+[f'tiny_npu_x{scale}.sv']
        with (dest/'lint.log').open('w') as f:subprocess.run(cmd,cwd=dest,stdout=f,stderr=subprocess.STDOUT,check=True)
    (dest/'manifest.json').write_text(json.dumps({n:hashlib.sha256((dest/n).read_bytes()).hexdigest() for n in names+[f'tiny_npu_x{scale}.sv']},indent=2))
    print(f'Generated x{scale}: arrays={a}, MAC/cycle={1024*a}, FP32 lanes={lanes}; lint={lint}')
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--scale',type=int,nargs='+',default=[1,2,4],choices=[1,2,4]);ap.add_argument('--lint',action='store_true');ap.add_argument('--verilator',default=shutil.which('verilator') or 'verilator');args=ap.parse_args()
    for s in args.scale:generate(s,args.lint,args.verilator)
