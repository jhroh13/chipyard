"""Small deterministic simulator for the exact AND2/OR2/NOT/plain-DFF audit netlist.
Zero initial FF state is a simulator convenience; callers must exercise reset.
"""
import collections
from gate_depth import audit
class Netlist:
 def __init__(self,m):
  audit(m);self.ports=m['ports'];cells=m['cells'];self.ff=[];comb={}
  for name,c in cells.items():
   x={k:v[0] for k,v in c['connections'].items()}
   if c['type']=='$_DFF_P_':
    assert x['C']==self.ports['clk']['bits'][0];self.ff.append((x['Q'],x['D']))
   else:
    assert c['type'] in ('$_AND_','$_OR_','$_NOT_');comb[name]=(c['type'],x)
  drivers={x['Y']:n for n,(_,x) in comb.items()};users=collections.defaultdict(list);degree={}
  for n,(_,x) in comb.items():
   parents={drivers[b] for k,b in x.items() if k!='Y' and b in drivers};degree[n]=len(parents)
   for p in parents:users[p].append(n)
  ready=collections.deque(n for n,d in degree.items() if not d);order=[]
  while ready:
   n=ready.popleft();order.append(comb[n])
   for child in users[n]:
    degree[child]-=1
    if not degree[child]:ready.append(child)
  assert len(order)==len(comb)
  bits=[b for c in cells.values() for v in c['connections'].values() for b in v if isinstance(b,int)]
  self.values=[0]*(max(bits)+3);self.zero=len(self.values);self.one=self.zero+1;self.values.extend([0,1])
  def idx(b):
   if isinstance(b,int):return b
   assert b in ('0','1'),f'unknown bit {b}'
   return self.one if b=='1' else self.zero
  self.ops=[(t,idx(x['A']),idx(x.get('B','0')),idx(x['Y'])) for t,x in order];self.idx=idx
 def tick(self,**inputs):
  v=self.values
  for name,p in self.ports.items():
   if p['direction']=='input':
    value=inputs.get(name,0)
    for i,b in enumerate(p['bits']):v[self.idx(b)]=(value>>i)&1
  for t,a,b,y in self.ops:v[y]=(v[a]&v[b]) if t=='$_AND_' else ((v[a]|v[b]) if t=='$_OR_' else 1-v[a])
  out={n:sum(v[self.idx(b)]<<i for i,b in enumerate(p['bits'])) for n,p in self.ports.items() if p['direction']=='output'}
  update=[v[self.idx(d)] for q,d in self.ff]
  for (q,d),value in zip(self.ff,update):v[q]=value
  return out
