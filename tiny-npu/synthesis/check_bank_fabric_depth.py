#!/usr/bin/env python3
"""Audit mapper and representative 8-bank fabric; full-region PPA remains separate."""
import hashlib,json,os,re,shutil,subprocess
from pathlib import Path
from gate_depth import audit
ROOT=Path(__file__).resolve().parents[1]
tool=shutil.which('yosys') or str(ROOT/'build/synth-tools/bin/yowasp-yosys');env=os.environ.copy();env.update(PYTHONPATH=str(ROOT/'build/synth-tools'),XDG_CACHE_HOME=str(ROOT/'build/synth-cache'))
rows=[]
for name,top,sources,settings in [
 ('mapper160','tiny_npu_bank_hash',['tiny_npu_bank_hash.sv'],dict(BANKS=160,ROW_BITS=10,PAYLOAD_BITS=305)),
 ('fabric8','tiny_npu_hashed_bank_fabric',['tiny_npu_bank_hash.sv','tiny_npu_bank_voq.sv','tiny_npu_hashed_bank_fabric.sv'],dict(PORTS=8,BANKS=8,DATA_BITS=32,ROW_BITS=10,TAG_BITS=16)),
 ('fabric8_full256','tiny_npu_hashed_bank_fabric',['tiny_npu_bank_hash.sv','tiny_npu_bank_voq.sv','tiny_npu_hashed_bank_fabric.sv'],dict(PORTS=8,BANKS=8,DATA_BITS=256,ROW_BITS=12,TAG_BITS=16))]:
 d=ROOT/f'build/bank-depth-{name}';d.mkdir(parents=True,exist_ok=True);rel=d.relative_to(ROOT)
 frontend='rtl/'+sources[0]
 if len(sources)>1:
  sv2v=shutil.which('sv2v') or str(ROOT/'build/synth-tools/bin/sv2v')
  with (d/'converted.v').open('w') as converted:subprocess.run([sv2v,'--top='+top,*[str(ROOT/'rtl'/f) for f in sources]],stdout=converted,check=True)
  converted=(d/'converted.v').read_text();start=converted.index('module '+top);prefix,body=converted[:start],converted[start:]
  for key,value in settings.items():
   body,n=re.subn(r'(parameter integer '+key+r'\s*=)[^;]+;',r'\g<1> '+str(value)+';',body,count=1);assert n==1,key
  (d/'converted.v').write_text(prefix+body);frontend=str(rel/'converted.v')
 script='read_verilog -sv '+frontend+('\nchparam '+' '.join(f'-set {k} {v}' for k,v in settings.items())+' '+top if len(sources)==1 else '')+'\nhierarchy -top '+top+'\nsynth -flatten -top '+top+' -noabc\ndelete t:$scopeinfo\ncheck -assert\ndffunmap\nabc -g AND,OR\nopt_clean\nwrite_json '+str(rel/'netlist.json')+'\n'
 (d/'synth.ys').write_text(script)
 with (d/'synth.log').open('w') as log:subprocess.run([tool,'-s',str(rel/'synth.ys')],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
 m=json.loads((d/'netlist.json').read_text())['modules'][top];r=audit(m,40);r.update(name=name,parameters=settings,netlist_sha256=hashlib.sha256((d/'netlist.json').read_bytes()).hexdigest(),converted_sha256=hashlib.sha256((d/'converted.v').read_bytes()).hexdigest() if (d/'converted.v').exists() else None,source_sha256={s:hashlib.sha256((ROOT/'rtl'/s).read_bytes()).hexdigest() for s in sources},scope='mapper at160 banks; representative fabric at8 ingress/8 banks with32-bit payload; full256-bit/12-bit-row8-bank fabric also audited; full160-bank fabric gate proof pending');rows.append(r);print(name,r['max_depth'],r['status'],flush=True)
 (ROOT/'architecture/v2/bank_fabric_gate_depth.json').write_text(json.dumps(rows,indent=2)+'\n')
 if r['status']!='PASS':raise SystemExit(1)
