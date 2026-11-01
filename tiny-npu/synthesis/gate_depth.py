"""Structural gate-depth audit: AND2/OR2/NOT only; all flop input/control pins.
Sequential cells cut paths. Unknown combinational cells fail rather than count
as a convenient single gate. Physical delay/wire/fanout are not inferred.
"""
import collections,json
ALLOWED={'$_AND_','$_OR_','$_NOT_'}
def audit(module,limit=40,allow_async_reset=False):
 cells=module['cells'];ff={n:c for n,c in cells.items() if 'DFF' in c['type'].upper()};comb={n:c for n,c in cells.items() if n not in ff}
 unknown={c['type'] for c in comb.values()}-ALLOWED
 if unknown:raise ValueError(f'Unmapped/unsupported combinational cells: {unknown}')
 for c in comb.values():
  widths=[len(bits) for port,bits in c['connections'].items() if c['port_directions'][port]=='input']
  if sum(widths)!=(1 if c['type']=='$_NOT_' else 2) or any(len(bits)!=1 for bits in c['connections'].values()):raise ValueError('Expected scalar basic gates')
 for c in ff.values():
  if c['type'] not in (('$_DFF_P_','$_DFF_N_','$_DFF_PP0_') if allow_async_reset else ('$_DFF_P_','$_DFF_N_')):raise ValueError('Run dffunmap: enable/reset muxes must be explicit gates')
  if len(c['connections'].get('Q',[]))!=1:raise ValueError('Expected bit-level register cells')
 drivers={b:n for n,c in comb.items() for port,bits in c['connections'].items() if c['port_directions'][port]=='output' for b in bits if isinstance(b,int)}
 dependencies={n:{drivers[b] for port,bits in c['connections'].items() if c['port_directions'][port]=='input' for b in bits if b in drivers} for n,c in comb.items()}
 users=collections.defaultdict(list)
 for n,parents in dependencies.items():
  for p in parents:users[p].append(n)
 degree={n:len(p) for n,p in dependencies.items()};queue=collections.deque(n for n,d in degree.items() if not d);depth={n:1 for n in queue};previous={}
 processed=0
 while queue:
  n=queue.popleft();processed+=1
  for child in users[n]:
   if depth.get(child,0)<depth[n]+1:depth[child]=depth[n]+1;previous[child]=n
   degree[child]-=1
   if degree[child]==0:queue.append(child)
 if processed!=len(comb):raise ValueError('Combinational cycle')
 qlabels={}
 for name,net in module['netnames'].items():
  if name in [f's{i}' for i in range(0,15)] or name in ('sn','an') or name.startswith('output_pipe[') or name=='valid_pipe':
   for b in net['bits']:qlabels.setdefault(b,[]).append(name)
 endpoints=[]
 for n,c in ff.items():
  q=c['connections'].get('Q',[]);stage=next((label for b in q for label in qlabels.get(b,[]) if label!='valid_pipe'),'valid/control')
  for port,bits in c['connections'].items():
   if c['port_directions'][port]!='input':continue
   for bit in bits:
    source=drivers.get(bit);endpoints.append(dict(stage=stage,cell=n,pin=port,depth=depth.get(source,0),driver=source))
 for name,port in module['ports'].items():
  if port['direction']=='output':
   for bit in port['bits']:
    source=drivers.get(bit);endpoints.append(dict(stage='module_outputs',cell=name,pin='output',depth=depth.get(source,0),driver=source))
 worst=max(endpoints,key=lambda x:x['depth']);path=[];node=worst['driver']
 while node:
  path.append(dict(cell=node,type=comb[node]['type'],depth=depth[node]));node=previous.get(node)
 groups={}
 for e in endpoints:
  if e['depth']>groups.get(e['stage'],{}).get('depth',-1):groups[e['stage']]=e
 return dict(status='PASS' if worst['depth']<=limit else 'FAIL',limit=limit,gate_basis='two-input AND/OR and NOT; XOR/MUX decomposed',max_depth=worst['depth'],stage_maxima=groups,worst_path=list(reversed(path)),bit_cells=len(cells),combinational_gates=len(comb),register_bits=len(ff),coverage='DFF input/control pins plus primary outputs; enable/reset muxes decomposed; wire/fanout/physical delays excluded')
if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('netlist');ap.add_argument('--top',required=True);ap.add_argument('--limit',type=int,default=40);a=ap.parse_args();r=audit(json.load(open(a.netlist))['modules'][a.top],a.limit);print(json.dumps({k:v for k,v in r.items() if k!='worst_path'},indent=2));raise SystemExit(0 if r['status']=='PASS' else 1)
