#!/usr/bin/env python3
"""Export resolved profiles; authoring metadata lives only in canonical JSON."""
import csv,json
from pathlib import Path
from configuration import load_profile,DEFAULT_CONFIG
D=Path(__file__).parent
metadata=json.loads(DEFAULT_CONFIG.read_text())['metadata']
ps=[load_profile(s) for s in (1,2,4)]
with (D/'parameters.csv').open('w',newline='') as f:
 w=csv.writer(f,lineterminator='\n');w.writerow(['parameter','group','default','x2','x4','allowed_or_rule','description'])
 for key in ps[0]:
  meta=metadata.get(key,{})
  group=next((g for g in ('AXI','DMA','TC','OIC','L0','VECTOR','MAC') if key.startswith(g)),'System / derived')
  w.writerow([key,group,*[json.dumps(p[key],ensure_ascii=False) if isinstance(p[key],(dict,list,bool)) else p[key] for p in ps],meta.get('allowed_or_rule','derived / validated contract'),meta.get('description','파생값. configuration.py 수식 참조.')])
print('Resolved parameters:',len(ps[0]))
