#!/usr/bin/env python3
from pathlib import Path
import sys,shutil,json,re
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'sim'))
from run_extended import compile_run
rows=[]
for latency in (10,16,32,64):
 folder=ROOT/f'build/singleport-{latency}'
 log=compile_run(folder,'tb_singleport_latency',['rtl/tiny_npu_sram_1rw_subbank.sv','sim/tb_singleport_latency.sv'],{'LATENCY':latency},shutil.which('verilator'))
 assert 'SINGLEPORT_PASS' in log
 rows.append(dict(status='PASS',latency_cycles=latency,commands=144,read_results=int(re.search(r'read_results=(\d+)',log).group(1)),scope='one single-port subbank plus elastic multicycle path, not full L0 fabric'))
(Path(__file__).parent/'singleport_tests.json').write_text(json.dumps(rows,indent=2))
