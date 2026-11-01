"""Null verification values inherit canonical hardware settings; non-null are explicit stress overrides."""
import copy,math

def resolve(cfg,p):
 cfg=copy.deepcopy(cfg);a=cfg['axi'];local=cfg['local']
 inherit={'ar_to_rlast_ns':p['DRAM_READ_LATENCY_NS'],'aw_to_first_wvalid_ns':p['DRAM_AW_TO_WVALID_NS'],'b_response_ns':p['DRAM_B_RESPONSE_NS'],'effective_shared_GBs':p['DMA_PAYLOAD_TARGET_GBS'],'raw_shared_GBs':p['MIN_RAW_GBS'],'efficiency':p['MEM_EFFICIENCY'],'ports':p['AXI_PORTS']}
 for k,v in inherit.items():
  if a.get(k) is None:a[k]=v
 for k,field in [('read_mo','DMA_READ_MO'),('write_mo','DMA_WRITE_MO')]:
  if a.get(k) is None:a[k]=math.ceil(p[field]/a['ports'])
 if local.get('path_latency_cycles') is None:
  local['path_latency_cycles']=p['L0_REG_PATH_LATENCY_CYCLES']
  local.setdefault('per_path_latency',{x:p['PATH_LATENCIES_CYCLES'][y] for x,y in [('A','SRCA'),('B','SRCB'),('C','SRCC'),('T','TARGETR')]})
 if local.get('register_slots') is None:local['register_slots']=min(p[x+'_SLOTS'] for x in ('SRCA','SRCB','SRCC','TARGETR'))
 if local.get('subbanks') is None:local['subbanks']=p['C_SUBBANKS']
 return cfg
