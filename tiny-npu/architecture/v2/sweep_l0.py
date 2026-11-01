#!/usr/bin/env python3
"""Single-port L0 capacity/subbank/latency/credit/AXI sensitivity.
Planning event model; not an integrated RTL throughput result.
"""
from pathlib import Path
import argparse,csv,json,math,sys
from analyze import profile
from local_paths import path_budget
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'model'))
from spec_model import simulate
OUT=Path(__file__).resolve().parent

def power2floor(v):return 1<<(int(v).bit_length()-1) if v>=1 else 0

def evaluate(mib=None,bank_factor=1.,bw=None,latency=None,slots_policy=None,axi_ports=None,
             subbank_ii=None,conflict_efficiency=None,tc_vector_ii=None,
             m=None,n=None,k=None,per_path=None,mac_hz=None,l0_hz=None,axi_hz=None,vector_hz=None,config=None):
 p=profile() if config is None else dict(config)
 mib=p['L0_BYTES']/1024**2 if mib is None else mib
 bw=p['DMA_PAYLOAD_TARGET_GBS'] if bw is None else bw
 slots_policy=p['SLOT_SIZING_POLICY'] if slots_policy is None else slots_policy
 axi_ports=p['AXI_PORTS'] if axi_ports is None else axi_ports
 subbank_ii=p['SUBBANK_ISSUE_II_CYCLES'] if subbank_ii is None else subbank_ii
 conflict_efficiency=p['L0_CONFLICT_EFFICIENCY'] if conflict_efficiency is None else conflict_efficiency
 tc_vector_ii=p['TC_ISSUE_II_CYCLES'] if tc_vector_ii is None else tc_vector_ii
 m=p['REFERENCE_M'] if m is None else m;n=p['REFERENCE_N'] if n is None else n;k=p['REFERENCE_K'] if k is None else k
 mac_hz=mac_hz or p['ACCEL_CLOCK_HZ'];l0_hz=l0_hz or p.get('L0_CLOCK_HZ',1e9)
 axi_hz=axi_hz or p['AXI_CLOCK_HZ'];vector_hz=vector_hz or p['VECTOR_CLOCK_HZ']
 p['ACCEL_CLOCK_HZ']=mac_hz;p['PEAK_TOPS']=2*p['ARRAY_COUNT']*1024*mac_hz/1e12
 total=int(mib*1024**2);regions=[]
 lat=dict(p['PATH_LATENCIES_CYCLES'])
 if latency is not None:
  for key in ('SRCA','SRCB','SRCC','TARGETR','L0_AXI_READ','VECTOR_READ','VECTOR_WRITE'):lat[key]=latency
 if per_path:lat.update(per_path)
 assert all(v>=0 for v in lat.values())
 assert all(v>0 for v in (mac_hz,l0_hz,axi_hz,vector_hz,subbank_ii))
 assert 0<conflict_efficiency<=1
 for old in p['L0_REGIONS']:
  ratio=old['bytes']/(p['L0_BYTES']-p['L0_BOOT_BYTES']) if old['name']!='boot' else 0
  r=dict(old);r['banks']=old['banks'] if old['name']=='boot' else max(1,int(old['banks']*bank_factor))
  unit=r['banks']*r['subbanks']*r['width']//8
  r['depth']=(int((total-p['L0_BOOT_BYTES'])*ratio)//unit) if old['name']!='boot' else old['depth'];r['bytes']=r['depth']*unit
  assert r['depth']>=1
  regions.append(r)
 a,b,c,scratch,meta,boot=regions
 # Conservative shared R+W service contract, distinct from duplex AXI channels.
 raw_axi=axi_ports*p['AXI_DATA_BITS']/8*axi_hz/1e9;available=raw_axi*p['MEM_EFFICIENCY']
 effective=min(bw,available)
 p.update(L0_BYTES=sum(r['bytes'] for r in regions),C_BYTES=c['bytes'],
          OPERAND_BYTES=a['bytes']+b['bytes'],DMA_PAYLOAD_TARGET_GBS=effective)
 best=None
 for mm in range(32,m+1,32):
  for nn in range(32,n+1,32):
   padded_c=math.ceil((mm//32)*(nn//32)/p['ARRAY_COUNT'])*p['ARRAY_COUNT']*4096
   if padded_c>c['bytes'] or 2*mm*16>a['bytes'] or 2*nn*32>b['bytes']:continue
   traffic=17*m*k//32*math.ceil(n/nn)+33*n*k//32*math.ceil(m/mm)+4*m*n
   key=(traffic,-mm*nn)
   if best is None or key<best[0]:best=(key,mm,nn)
 if best is None:raise ValueError('Cannot hold a legal padded macro/panel')
 p['MACRO_M']=best[1];p['MACRO_N']=best[2]
 # Each subbank has ONE shared R/W port; never count separate R and W capacities.
 def shared_bw(r):return r['banks']*r['subbanks']*r['width']/8*(l0_hz/1e9)/subbank_ii*conflict_efficiency
 array_scale=p['ARRAY_COUNT']/10
 raw_slow=max(1.,(160*array_scale+1)*(mac_hz/1e9)/shared_bw(a),(320*array_scale+1)*(mac_hz/1e9)/shared_bw(b),
              (1280+1280)*array_scale*(mac_hz/1e9)/shared_bw(c),20*array_scale*(mac_hz/1e9)/shared_bw(meta),float(tc_vector_ii)*mac_hz/l0_hz,(lat['FMA']+p.get('MAC_FEEDBACK_EXTRA_CYCLES',0))/p['MAC_ACC_CONTEXTS'])
 bounds={name:max(p.get('L0_REG_LATENCY_MAX_CYCLES',32),lat[name]) for name in ('SRCA','SRCB','SRCC','TARGETR')}
 budgets={name:path_budget(bounds[name],contexts=p['MAC_ACC_CONTEXTS'],group_ii=32*l0_hz/mac_hz,oic_latency=lat['OIC']) for name in bounds}
 slots_by_path={name:(max(p[name+'_SLOTS'],budgets[name]['configured_slots']) if slots_policy=='AUTO' else 32) for name in bounds}
 rtts={name:2*lat[name]+lat['OIC'] for name in bounds}
 slots=max(slots_by_path.values());bound=max(bounds.values());actual_rtt=max(rtts.values())
 credit_group_ii=max(rtts[name]*mac_hz/l0_hz/max(1,slots_by_path[name]-p['MAC_ACC_CONTEXTS']) for name in bounds)
 oic_group_ii=p['OIC_OPERATION_BUDGET_PER_GROUP']/(p['OIC_REQUEST_PORTS']*.8)*mac_hz/l0_hz
 effective_group_ii=max(32*raw_slow,credit_group_ii,oic_group_ii)
 p['ARCH_LOCAL_SLOWDOWN']=effective_group_ii/32
 # Explicit variable fill/drain stages, all expressed in L0-clock cycles.
 cdc_ns=lat['AXI_CDC']/axi_hz*1e9
 # Explicit cold-prefill of all interleaved contexts; do not assume RF data arrives in one cycle.
 context_prefill_ns=p['MAC_ACC_CONTEXTS']*effective_group_ii/mac_hz*1e9
 pre_ns=context_prefill_ns+p['MAC_OPERAND_READ_CYCLES']/mac_hz*1e9+(max(lat['SRCA'],lat['SRCB'],lat['SRCC'])+lat['TC']+lat['OIC']+lat['DMA_L0_COMMIT'])/l0_hz*1e9+2*cdc_ns
 drain_ns=(lat['TARGETR']+lat['OIC'])/l0_hz*1e9+(lat['FMA']+p['MAC_ACC_CONTEXTS']*32+p['MAC_TARGETR_STORE_CYCLES'])/mac_hz*1e9
 p['PANEL_PIPELINE_OVERHEAD_CYCLES']=math.ceil((pre_ns+drain_ns)*mac_hz/1e9)
 r=simulate(m,n,k,p)
 setup_ns=p['JOB_DISPATCH_CYCLES']/mac_hz*1e9;output_l0_axi_ns=lat['L0_AXI_READ']/l0_hz*1e9+cdc_ns
 rows_per_strip=min(p['FINAL_FP32_STRIP_ROWS'],power2floor(scratch['bytes']//(p['FINAL_FP32_STRIP_SLOTS']*n*4)))
 if rows_per_strip<1:raise ValueError('FP32 scratch cannot hold two output rows')
 vector_pipe_ns=(lat['VECTOR_READ']+lat['VECTOR_WRITE'])/l0_hz*1e9+(lat['LUT']+lat['FORMAT'])/vector_hz*1e9  # vector read/write + LUT + format stages.
 vector_full_ns=math.ceil(m*n/p['VECTOR_LANES'])*p['VECTOR_ISSUE_II_CYCLES']/vector_hz*1e9+vector_pipe_ns
 first_strip_ns=math.ceil(rows_per_strip*n/p['VECTOR_LANES'])*p['VECTOR_ISSUE_II_CYCLES']/vector_hz*1e9+vector_pipe_ns
 base_ns=r['model_us']*1000+setup_ns+output_l0_axi_ns
 ops=2*m*n*k
 return dict(L0_requested_MiB=mib,L0_actual_bytes=p['L0_BYTES'],L0_boot_reserved_bytes=boot['bytes'],logical_bank_factor=bank_factor,
   physical_C_subbanks=c['banks']*c['subbanks'],subbank_shared_port_II=subbank_ii,
   bank_conflict_efficiency=conflict_efficiency,path_latency_cycles=max(lat[x] for x in bounds) if latency is None else latency,
   latency_sizing_bound_cycles=bound,slot_policy=slots_policy,register_slots=slots,
   per_path_latencies=lat,register_slots_by_path=slots_by_path,
   credit_RTT_cycles=actual_rtt,MAC_group_II_cycles=effective_group_ii,
   context_prefill_ns=context_prefill_ns,panel_fill_drain_cycles=p['PANEL_PIPELINE_OVERHEAD_CYCLES'],
   AXI_ports=axi_ports,AXI_bits=p['AXI_DATA_BITS'],MAC_MHz=mac_hz/1e6,L0_MHz=l0_hz/1e6,AXI_MHz=axi_hz/1e6,VECTOR_MHz=vector_hz/1e6,AXI_raw_total_GBs=raw_axi,
   AXI_available_shared_GBs=available,requested_payload_GBs=bw,effective_payload_GBs=effective,
   macro_M=best[1],macro_N=best[2],C_capacity=c['bytes'],C_shared_RW_GBs=shared_bw(c),
   local_slowdown=p['ARCH_LOCAL_SLOWDOWN'],external_bytes=r['read_bytes']+r['write_bytes'],
   event_TOPS_without_vector=ops/(base_ns*1e-9)/1e12,event_us_without_vector=base_ns/1000,
   FP32_strip_rows=rows_per_strip,serialized_vector_TOPS=ops/((base_ns+vector_full_ns)*1e-9)/1e12,
   ideal_overlap_vector_TOPS=ops/((base_ns+first_strip_ns)*1e-9)/1e12,
   context='LQ16 arithmetic assumed capable of II1 per interleaved PE; new TC/OIC/physical subbank scheduler not RTL-validated')

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--l0-mib',type=float,nargs='+',default=[2,4,6,8,10,12,16])
 ap.add_argument('--bank-factor',type=float,nargs='+',default=[.25,.5,1,2])
 ap.add_argument('--path-cycles',type=int,nargs='+',default=[10,16,32,64,128])
 ap.add_argument('--axi-ports',type=int,nargs='+',default=[1,2])
 ap.add_argument('--slots-policy',nargs='+',choices=['AUTO','FIXED32'],default=['AUTO','FIXED32'])
 ap.add_argument('--bw-gbs',type=float,default=20)
 ap.add_argument('--subbank-ii',type=int,default=1)
 a=ap.parse_args()
 rows=[evaluate(m,b,a.bw_gbs,l,sp,ports,a.subbank_ii) for m in a.l0_mib for b in a.bank_factor
       for l in a.path_cycles for sp in a.slots_policy for ports in a.axi_ports]
 with (OUT/'l0_sweep.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=rows[0].keys(),lineterminator='\n');w.writeheader();w.writerows(rows)
 (OUT/'l0_sweep.json').write_text(json.dumps(rows,indent=2))
 for r in rows:
  if r['L0_requested_MiB']==10 and r['logical_bank_factor']==1 and r['AXI_ports']==2:
   print({k:r[k] for k in ('path_latency_cycles','slot_policy','register_slots','MAC_group_II_cycles','event_TOPS_without_vector','serialized_vector_TOPS')})
 # Credit and physical port consistency checks with opposite scenarios.
 from configuration import load_profile
 long_cfg=load_profile(overrides={'PATH_LATENCIES_CYCLES':{n:512 for n in ('SRCA','SRCB','SRCC','TARGETR')},'LOCAL_MAX_INFLIGHT_VECTORS':512,'LOCAL_VECTOR_ID_BITS':9})
 fast=evaluate(config=long_cfg,slots_policy='AUTO');fixed=evaluate(config=long_cfg,slots_policy='FIXED32')
 assert fast['register_slots']>fixed['register_slots'] and fast['serialized_vector_TOPS']>fixed['serialized_vector_TOPS']
 assert evaluate(10,bank_factor=.25)['local_slowdown']>1
 assert evaluate(10,axi_ports=1)['effective_payload_GBs']==12
 print('Configurations:',len(rows),'capacity/credit/shared-port/AXI checks PASS; planning model only')
if __name__=='__main__':main()
