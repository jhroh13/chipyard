#!/usr/bin/env python3
"""Regression for independent path latencies and clock-domain conversion."""
import json
from pathlib import Path
from sweep_l0 import evaluate
from analyze import profile
D=Path(__file__).parent
base=evaluate(10);rows=[]
for name,value in base['per_path_latencies'].items():
 changed=evaluate(10,per_path={name:value+64})
 assert changed['serialized_vector_TOPS'] < base['serialized_vector_TOPS'], name
 rows.append(dict(path=name,base_cycles=value,changed_cycles=value+64,
                  base_TOPS=base['serialized_vector_TOPS'],changed_TOPS=changed['serialized_vector_TOPS']))
for name in ('mac_hz','l0_hz','axi_hz','vector_hz'):
 kwargs={name:{'mac_hz':1e9,'l0_hz':1e9,'axi_hz':625e6,'vector_hz':1e9}[name]/2}
 changed=evaluate(10,**kwargs)
 assert changed['serialized_vector_TOPS'] < base['serialized_vector_TOPS'], name
 rows.append(dict(clock=name,changed_TOPS=changed['serialized_vector_TOPS']))
for ii in (2,4,8):
 changed=evaluate(10,subbank_ii=ii)
 assert changed['serialized_vector_TOPS'] <= base['serialized_vector_TOPS']
 rows.append(dict(subbank_II=ii,changed_TOPS=changed['serialized_vector_TOPS']))
assert evaluate(10,latency=8)['serialized_vector_TOPS']>base['serialized_vector_TOPS']
result=dict(status='PASS',scope='planning-model sensitivity only; not hardware timing closure',cases=rows)
(D/'path_sensitivity.json').write_text(json.dumps(result,indent=2));print('Independent latency/clock/II sensitivity PASS:',len(rows),'cases plus decreased-latency case')
