#!/usr/bin/env python3
from gate_depth import audit

def chain(n,enable=False,cut=None):
 cells={};last=1
 for i in range(n):
  if cut==i:
   cells['reg']={'type':'$_DFF_P_','port_directions':{'D':'input','C':'input','Q':'output'},'connections':{'D':[last],'C':[0],'Q':[1000]}};last=1000
  out=i+3;cells[str(i)]={'type':'$_AND_','port_directions':{'A':'input','B':'input','Y':'output'},'connections':{'A':[last],'B':[2],'Y':[out]}};last=out
 if enable:
  cells['reg']={'type':'$_DFF_P_','port_directions':{'D':'input','C':'input','Q':'output'},'connections':{'D':[last],'C':[0],'Q':[1000]}};last=1000
 return {'cells':cells,'ports':{'out':{'direction':'output','bits':[last]}},'netnames':{}}
assert audit(chain(40))['status']=='PASS'
assert audit(chain(41))['status']=='FAIL'
assert audit(chain(40,cut=20))['max_depth']==20
assert audit(chain(41,enable=True))['status']=='FAIL'
cycle=chain(1);cycle['cells']['0']['connections']['A']=[3]
try:audit(cycle)
except ValueError:pass
else:raise AssertionError('self-cycle accepted')
unknown=chain(1);unknown['cells']['0']['type']='$_XOR_'
try:audit(unknown)
except ValueError:pass
else:raise AssertionError('unexpanded XOR accepted')
print('Gate-depth tests PASS:40/41 boundary, register cut, enable path, cycle, unknown gate')

hidden=chain(1,enable=True);hidden['cells']['reg']['type']='$_DFFE_PP_'
try:audit(hidden)
except ValueError:pass
else:raise AssertionError('hidden enabled flop accepted')
import json,subprocess,sys,tempfile
from pathlib import Path
with tempfile.TemporaryDirectory() as tmp:
 net=Path(tmp)/'bad.json';net.write_text(json.dumps({'modules':{'test':chain(41)}}))
 r=subprocess.run([sys.executable,str(Path(__file__).with_name('gate_depth.py')),str(net),'--top','test'],capture_output=True,text=True)
 assert r.returncode==1 and '"status": "FAIL"' in r.stdout
print('CLI hard-failure and hidden-flop rejection PASS')
