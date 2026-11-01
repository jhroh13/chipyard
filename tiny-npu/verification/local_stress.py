"""Reduced bank/credit/control fixture. Not full 40-bank C transport or real MAC.
Three source requests and one destination request per synthetic token expose
control/credit/return-order issues; its ops tags are scheduling capacity only.
"""
import collections,heapq,random

def run_local(trace,cfg,p,seed=2):
 rng=random.Random(seed);cycles=cfg['cycles'];period=round(1e12/p['L0_CLOCK_HZ']);slots=cfg['register_slots'];banks=cfg['subbanks']
 if min(cycles,slots,banks,cfg['path_latency_cycles'])<=0:raise ValueError('positive local fixture geometry required')
 jobs={};requests={x:collections.deque() for x in 'ABCT'};returns=[];sequence=0;next_mac=0;mac=None;remaining=0;target_used=0;retired=0;pending_consumer=[];miss=[0]*8;conflicts=0;oic=0;max_slots=0;completion_order=[];accepted=[];max_outstanding=0
 per_path=cfg.get('per_path_latency',{})
 def sample(t,ch,v,r,**kw):trace.sample(t,ch,v,r,period_ps=period,**kw)
 def can_control(h,need):
  # A control traffic agent with a configurable service clock and explicit I-cache miss stall.
  edge=((cycle+1)*cfg.get('rocket_clock_hz',p['ROCKET_CLOCK_HZ'])//p['L0_CLOCK_HZ'])!=(cycle*cfg.get('rocket_clock_hz',p['ROCKET_CLOCK_HZ'])//p['L0_CLOCK_HZ'])
  if miss[h]>0:
   if edge:miss[h]-=1
  elif need and edge and rng.random()<cfg['icache_miss_probability']:miss[h]=cfg['icache_miss_cycles']
  return edge and miss[h]==0
 def bank(j,path):return (j+('ABCT'.index(path)))%banks if cfg.get('bank_mapping','linear')=='skew' else (j*32)%banks
 for cycle in range(cycles):
  t=cycle*period
  while returns and returns[0][0]<=cycle:
   _,_,j,path=heapq.heappop(returns);completion_order.append((j,path));trace.event(t,'LOCAL_COMMIT',token=j,path=path)
   if path=='T':jobs[j]['retired']=True;target_used-=1;retired+=1
   else:jobs[j]['ready'].add(path)
  live=sum(not j.get('retired') for j in jobs.values());max_slots=max(max_slots,live)
  control=[False]*8;need=[False]*8;cmask=[0]*8
  need[0]=True;control[0]=can_control(0,True) and live<slots
  if control[0]:
   jobs[sequence]={'ready':set(),'start':cycle};
   for path in 'ABC':requests[path].append(sequence)
   trace.event(t,'TOKEN_ALLOCATE',token=sequence);sequence+=1
  cmask[0]=2 if live>=slots else 64 if miss[0] else 32
  used=set();order='ABCT' if cycle%2==0 else 'TCBA'
  for path in order:
   h={'A':2,'B':3,'C':4,'T':5}[path];q=requests[path];need[h]=bool(q);ctrl=can_control(h,bool(q));candidate=q[0] if q else 0
   b=bank(candidate,path);eligible=bool(q) and ctrl;ready=eligible and b not in used
   mask=(4 if eligible and b in used else 64 if miss[h] else 32 if q and not ctrl else 0)
   if mask&4:conflicts+=1
   control[h]=ready;cmask[h]=mask
   sample(t,'l0.'+path,bool(q),ready,active=int(bool(q)),stall_mask=mask,id=candidate,bank=b,bytes=32)
   if ready:
    q.popleft();used.add(b);accepted.append((candidate,path))
    delay=per_path.get(path,cfg['path_latency_cycles'])+rng.randrange(cfg['request_jitter_cycles']+1)
    heapq.heappush(returns,(cycle+delay,len(accepted),candidate,path));max_outstanding=max(max_outstanding,len(returns))
  if mac is not None:
   stall=rng.random()<cfg['consumer_stall_probability'];valid=True;ready=not stall;mask=16 if stall else 0
   if ready:
    remaining-=1
    if remaining==0:
     jobs[mac]['done']=True;pending_consumer.append(mac);trace.event(t,'MAC_TOKEN_DONE',token=mac);mac=None
  else:
   j=jobs.get(next_mac);need[6]=j is not None;data=j is not None and j['ready']==set('ABC');credit=target_used<slots
   counter_conflict=data and credit and rng.random()<cfg['oic_conflict_probability'];ctrl=can_control(6,data)
   mask=1 if not data else 2 if not credit else 8 if counter_conflict else 64 if miss[6] else 32 if not ctrl else 0
   valid=bool(data and credit and not counter_conflict and ctrl);ready=True;control[6]=valid;cmask[6]=mask;oic+=int(counter_conflict)
   if valid:mac=next_mac;next_mac+=1;remaining=31;target_used+=1;trace.event(t,'MAC_TOKEN_START',token=mac)
  sample(t,'mac.issue',valid,ready,active=1,stall_mask=mask,ops=0,capacity_ops=p['MACS_PER_CLOCK']*2,ops_semantics='synthetic_scheduling_capacity_not_verified_matmul')
  need[7]=bool(pending_consumer);control[7]=can_control(7,need[7]) and need[7] and rng.random()>=cfg['consumer_stall_probability']
  if control[7]:
   j=pending_consumer.pop(0);requests['T'].append(j);trace.event(t,'VECTOR_TOKEN_RELEASE',token=j)
  need[1]=retired>0;control[1]=can_control(1,need[1]) and need[1]
  for h in range(8):
   if h not in (0,2,3,4,5,6):cmask[h]=64 if miss[h] else 16 if need[h] and not control[h] else 0
   sample(t,f'rocket.h{h}.control',need[h],control[h],active=int(need[h]),stall_mask=cmask[h],bytes=0)
   sample(t,f'rocket.h{h}.icache',need[h],not bool(miss[h]),active=int(need[h]),stall_mask=64 if miss[h] else 0,bytes=4,cache_miss=int(bool(miss[h])))
   sample(t,f'rocket.h{h}.descriptor',control[h],True,active=int(need[h]),bytes=8)
  assert 0<=target_used<=slots and live<=slots
 # Drain only the abstract responses to verify exactly-once commit tags, not to count extra MAC work.
 for _,_,j,path in sorted(returns):completion_order.append((j,path))
 assert len(accepted)==len(set(accepted)) and sorted(accepted)==sorted(completion_order)
 return dict(scope='reduced behavioral bank/control scheduler; not real Rocket, full L0, or arithmetic',allocated=sequence,retired=retired,bank_conflicts=conflicts,OIC_conflicts=oic,max_register_occupancy=max_slots,max_outstanding_returns=max_outstanding,accepted_requests=len(accepted),exactly_once_return_tags=True,clock_hz=cfg.get('rocket_clock_hz',p['ROCKET_CLOCK_HZ']),cycles=cycles)
