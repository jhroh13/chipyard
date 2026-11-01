#!/usr/bin/env python3
import json,re,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'sim'))
from run_extended import compile_run
rows=[]
for banks in (8,160):
 for hashing in (0,1):
  d=ROOT/f'build/hash-unit-b{banks}-h{hashing}';d.mkdir(parents=True,exist_ok=True)
  log=compile_run(d,'tb_bank_hash',['rtl/tiny_npu_bank_hash.sv','sim/tb_bank_hash.sv'],dict(BANKS=banks,HASH=hashing),shutil.which('verilator'))
  match=re.search(r'BANK_HASH_PASS banks=(\d+) hash=(\d+) checked=(\d+)',log);assert match
  rows.append(dict(banks=banks,hashing=bool(hashing),checked=int(match[3]),status='PASS',scope='all1024 rows x each bank, metadata preservation and backpressure; independent integer golden'))
(ROOT/'architecture/v2/bank_hash_tests.json').write_text(json.dumps(rows,indent=2)+'\n')
