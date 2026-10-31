#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
import argparse,json,os,re,shutil,subprocess,time
from pathlib import Path
from generate_vectors import generate
ROOT=Path(__file__).resolve().parents[1]
def run(arrays,verilator):
    build=ROOT/'build'/f'arrays-{arrays}';build.mkdir(parents=True,exist_ok=True)
    generate(build,arrays)
    cmd=[verilator,'--binary','--timing','-j','4','-Wno-fatal','--top-module','tb_matmul',
         f'-GARRAYS={arrays}','--Mdir',str(build/'obj'),'-o','Vtiny_npu_tb',
         str(ROOT/'rtl/tiny_npu_fp32_from_scaled_int.sv'),str(ROOT/'rtl/tiny_npu_mxfp4_matmul.sv'),str(ROOT/'sim/tb_matmul.sv')]
    start=time.monotonic()
    with (build/'compile.log').open('w') as f:
        subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True)
    with (build/'simulation.log').open('w') as f:
        subprocess.run([str(build/'obj/Vtiny_npu_tb')],cwd=build,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
    log=(build/'simulation.log').read_text();match=re.search(r'SIM_PASS arrays=(\d+) cases=(\d+) checked=(\d+) cycles=(\d+) input_II=(\d+) output_II=(\d+) input_stalls=(\d+) output_stalls=(\d+)',log)
    if not match:raise RuntimeError('Simulation did not execute all checks')
    keys=['arrays','cases','checked','cycles','input_II','output_II','input_stalls','output_stalls']
    summary=dict(zip(keys,map(int,match.groups())))
    summary.update(status='PASS',seed=20261101,wall_seconds=round(time.monotonic()-start,3),
                   simulator=subprocess.check_output([verilator,'--version'],text=True).strip(),
                   comparison='bit-exact FP32 against independent Python integer-dot/IEEE-pack model',
                   scope='K=32 tile engine only; no DMA/RoCC/LLM/SDF')
    (build/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
    return summary
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--arrays',type=int,nargs='+',default=[1,5,10]);p.add_argument('--verilator',default=shutil.which('verilator'));args=p.parse_args()
    if not args.verilator:raise SystemExit('Verilator required: activate the environment or install Verilator 5.x')
    summaries=[run(a,args.verilator) for a in args.arrays]
    (ROOT/'build/summary.json').write_text(json.dumps(summaries,indent=2))
