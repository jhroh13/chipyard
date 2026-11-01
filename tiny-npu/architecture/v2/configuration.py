#!/usr/bin/env python3
"""Authoritative RevB configuration resolver; no legacy-profile inheritance."""
import copy,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DEFAULT_CONFIG=ROOT/'configs/revb/default.json'

class ConfigError(ValueError): pass

def require(condition,message):
 if not condition:raise ConfigError(message)

def same_shape(value,template,path):
 if isinstance(template,float):ok=type(value) in (int,float) and math.isfinite(value)
 else:ok=type(value) is type(template)
 require(ok,f'{path}: expected {type(template).__name__}')
 if isinstance(template,dict):
  require(set(value)==set(template),f'{path}: unknown or missing nested keys')
  for k in template:same_shape(value[k],template[k],f'{path}.{k}')
 if isinstance(template,list) and path=='L0_REGIONS':
  require(len(value)==5,'L0_REGIONS: five ordered regions required')
  for i,(v,t) in enumerate(zip(value,template)):same_shape(v,t,f'{path}[{i}]')

def validate_schema(value,schema,path='config'):
 typ=schema.get('type')
 matches={'object':dict,'array':list,'boolean':bool,'integer':int,'string':str}
 if typ=='number':require(type(value) in (int,float) and math.isfinite(value),f'{path}: expected finite number')
 elif typ:require(type(value) is matches[typ],f'{path}: expected {typ}')
 if typ=='object':
  props=schema.get('properties',{})
  require(set(schema.get('required',[]))<=set(value),f'{path}: missing required keys')
  if schema.get('additionalProperties') is False:require(set(value)<=set(props),f'{path}: unknown keys')
  for k,v in value.items():
   if k in props:validate_schema(v,props[k],f'{path}.{k}')
 if typ=='array':
  for i,v in enumerate(value):validate_schema(v,schema.get('items',{}),f'{path}[{i}]')

def merge_known(base,changes,path=''):
 require(isinstance(changes,dict),f'{path}: object required')
 for k,v in changes.items():
  label=f'{path}.{k}'.strip('.')
  require(k in base,f'{label}: unknown, obsolete, or derived parameter; edit its source instead')
  if isinstance(base[k],dict):merge_known(base[k],v,label)
  else:same_shape(v,base[k],label);base[k]=copy.deepcopy(v)

def load_profile(scale=1,cores=None,overrides=None,config_path=None):
 source=json.loads(Path(config_path or DEFAULT_CONFIG).read_text())
 validate_schema(source,json.loads((DEFAULT_CONFIG.parent/'schema.json').read_text()))
 require(set(source)=={'schema_version','defaults','scale_overrides','metadata'},'Invalid configuration root keys')
 require(source['schema_version']==1,'Unsupported schema_version')
 require(str(scale) in source['scale_overrides'],'Unsupported scale')
 # Canonical contract defines known key/types; external configs may change values, not silently add controls.
 contract=json.loads(DEFAULT_CONFIG.read_text())['defaults']
 require(set(source['defaults'])==set(contract),'Unknown or missing default parameter')
 p=copy.deepcopy(source['defaults'])
 merge_known(p,source['scale_overrides'][str(scale)])
 merge_known(p,overrides or {})
 if cores is not None:merge_known(p,{'ROCKET_CORES':cores})
 for k in contract:same_shape(p[k],contract[k],k)
 p['SCALE']=scale
 for k,v in p.items():
  if type(v) is int:require(v>=0,f'{k}: must be nonnegative')
 for k in ('ACCEL_CLOCK_HZ','L0_CLOCK_HZ','AXI_CLOCK_HZ','VECTOR_CLOCK_HZ','ARRAY_COUNT','ROCKET_CORES','MAC_ACC_CONTEXTS','SUBBANK_ISSUE_II_CYCLES','VECTOR_ISSUE_II_CYCLES','TC_ISSUE_II_CYCLES','AXI_PORTS','OIC_REQUEST_PORTS','OIC_BANKS','VECTOR_LANES','LOCAL_MAX_INFLIGHT_VECTORS','ROCKET_CLOCK_HZ','SUSTAINED_TOPS_TARGET','OIC_COUNT','COMMAND_QUEUE_DEPTH','TC_CONTEXTS_PER_ENGINE','VECTOR_LUT_ENTRIES','FINAL_FP32_STRIP_ROWS','FINAL_FP32_STRIP_SLOTS'):
  require(p[k]>0,f'{k}: must be positive')
 for key in ('ROCKET_ICACHE_BYTES','ROCKET_DCACHE_BYTES','ROCKET_L2_BYTES'):
  require(p[key]>=1024 and p[key]&(p[key]-1)==0,f'{key}: power-of-two capacity >=1KiB required')
 require(p['DRAM_LATENCY_MODE']=='AR_RLAST_AW_WVALID','Unsupported DRAM latency contract')
 p['WRITE_RESPONSE_TAIL_NS']=p['DRAM_B_RESPONSE_NS']
 require(p['ARRAY_ROWS']==p['ARRAY_COLS']==p['TILE_K']==32,'Only 32x32x32 tiles currently supported')
 require(p['SRAM_PORT']=='1RW' and p['L0_PORTS_PER_SUBBANK']==1 and not p['L0_SIMULTANEOUS_RW_SAME_SUBBANK'],'L0 must be single-port R OR W')
 require(p['INTERNAL_ACC_FORMAT'] in ('LQ16_S1_E7_M8','TF32_S1_E8_M10'),'Unsupported internal numeric format')
 require(p['C_RESIDENCY_MODE']=='L0_KBLOCK_TF32_SPILL' and p['FINAL_TARGETR_ROUTE']=='FINAL_VIA_L0','Unsupported residency/final route for current model')
 require(p['ROUND_MODE']==p['TF32_STORE_ROUNDING']=='RNE' and p['MAC_ARITHMETIC']=='FMA_RNE_PER_MAC','Unsupported rounding/arithmetic contract')
 require(p['TF32_CONTAINER_BITS']==32 and not p['TARGETR_PACKED19_SUPPORTED'],'Packed TF32 is not supported')
 for key,bits in [('AXI_ARCACHE',4),('AXI_AWCACHE',4),('AXI_ARPROT',3),('AXI_AWPROT',3),('AXI_QOS',4)]:
  require(0<=p[key]<2**bits,f'{key}: field width overflow')
 require(p['SRCC_FORMAT']==p['TARGETR_FORMAT']=='TF32_CONTAINER32' and p['FINAL_L0_FORMAT']=='FP32','Invalid result format contract')
 require(p['SRCA_DATA_BITS']==4 and p['SRCB_DATA_BITS']==8 and p['SRCC_DATA_BITS']==p['TARGETR_DATA_BITS']==32,'Unsupported operand/storage widths')
 require(p['SLOT_SIZING_POLICY'] in ('AUTO','FIXED8'),'Unsupported slot policy')
 require(0<p['MEM_EFFICIENCY']<=1 and 0<p['L0_CONFLICT_EFFICIENCY']<=1,'Efficiencies must be in (0,1]')
 require(1<=p['TC_DIMENSIONS']<=6 and p['TC_ADDRESS_BITS']>=p['AXI_ADDR_BITS'],'Invalid tensor counter geometry')
 require(p['OIC_BITS']==64 and p['OIC_EPOCH_BITS']==64,'OIC sequence/epoch must be 64 bits')
 require(p['OIC_COUNT']>=p['OIC_BANKS'],'Too few OIC counters for bank count')
 for key in ('REFERENCE_M','REFERENCE_N','REFERENCE_K','MACRO_M','MACRO_N'):
  require(p[key]>0 and p[key]%32==0,f'{key}: positive multiple of 32 required')
 require(p['FINAL_FP32_STRIP_SLOTS']>=2,'Final FP32 staging requires double buffering')
 require(all(0<=p[key]<=4 for key in ('OIC_MAX_WAIT_CONDITIONS','OIC_MAX_CREDIT_CONDITIONS','OIC_MAX_SIGNALS')),'Descriptor ABI allows at most four wait/credit/signal conditions')
 require(p['ROLE_COUNT']==8 and set(p['ROLE_TO_HART'])==set(map(str,range(1,9))),'Eight role mappings required')
 require(all(type(h) is int and 0<=h<p['ROCKET_CORES'] for h in p['ROLE_TO_HART'].values()),'Role mapped outside configured Rocket harts')
 p['FLOAT_VECTOR_OWNER_HART']=p['ROLE_TO_HART']['8']
 require(p['AXI_DATA_BITS']==256,'Current RevB model/primitive generator supports 256-bit AXI only')
 require(1<=p['AXI_MAX_BURST_BEATS']<=256,'AXI4 burst beats must be 1..256')
 require(1<=p['DMA_MAX_BURST_BYTES']<=min(4096,p['AXI_MAX_BURST_BEATS']*p['AXI_DATA_BITS']//8),'DMA burst exceeds AXI beat or 4KiB limit')
 require(p['DMA_MAX_BURST_BYTES']%(p['AXI_DATA_BITS']//8)==0,'DMA burst must be beat aligned')
 require(p['AXI_ID_BITS']<=16,'AXI ID width unsupported')
 require(math.ceil(p['DMA_READ_MO']/p['AXI_PORTS'])+math.ceil(p['DMA_WRITE_MO']/p['AXI_PORTS'])<=2**p['AXI_ID_BITS'],'Insufficient AXI IDs for conservative shared read/write MO partition')
 for direction in ('READ','WRITE'):
  require(p[f'DMA_{direction}_MO']>0,f'DMA_{direction}_MO must be positive')
  require(p[f'DMA_{direction}_BUFFER_BYTES']>=p['DMA_MAX_BURST_BYTES'],f'DMA {direction} buffer cannot reserve one full burst')
 lat=p['PATH_LATENCIES_CYCLES']
 require(all(type(v) is int and v>=0 for v in lat.values()),'Path latencies must be nonnegative integer cycles')
 require(lat['SRCA']>=1,'SRCA primitive read latency must be >=1')
 p['MAC_FMA_PIPE_CYCLES']=lat['FMA'];p['OIC_RESPONSE_LATENCY_CYCLES']=lat['OIC']
 require(p['MAC_ACC_CONTEXTS']>=max(1,lat['FMA']),'FMA feedback latency exceeds interleaved contexts for II1')
 p['L0_REG_PATH_LATENCY_CYCLES']=max(lat[k] for k in ('SRCA','SRCB','SRCC','TARGETR'))
 p['L0_REG_CREDIT_RTT_CYCLES']=2*p['L0_REG_PATH_LATENCY_CYCLES']+lat['OIC']
 # Compare credit RTT in seconds, not cycles from different domains.
 group_seconds=32/p['ACCEL_CLOCK_HZ'];contexts=p['MAC_ACC_CONTEXTS']
 for name in ('SRCA','SRCB','SRCC','TARGETR'):
  bound=max(lat[name],p['L0_REG_LATENCY_MAX_CYCLES'])
  minimum=contexts+math.ceil(((2*bound+lat['OIC'])/p['L0_CLOCK_HZ'])/group_seconds)
  needed=1<<(max(2*contexts,minimum)-1).bit_length()
  requested=p[name+'_SLOTS']
  if requested==0:
   p[name+'_SLOTS']=needed if p['SLOT_SIZING_POLICY']=='AUTO' else 8
  require(p[name+'_SLOTS']>=2*contexts,f'{name}: insufficient slots for context double buffering')
  require(p['SLOT_SIZING_POLICY']=='FIXED8' or p[name+'_SLOTS']>=minimum,f'{name}: slots cannot hide configured credit RTT')
 require(p['LOCAL_MAX_INFLIGHT_VECTORS']<=2**p['LOCAL_VECTOR_ID_BITS'],'Local vector ID space smaller than in-flight limit')
 require(p['LOCAL_MAX_INFLIGHT_VECTORS']>=max(lat[k] for k in ('SRCA','SRCB','SRCC','TARGETR')),'In-flight vectors cannot cover II1 path latency; increase limit and ID width')
 regions=p['L0_REGIONS'];expected=['A','B','C','scratch','scale_metadata']
 for r,name in zip(regions,expected):
  require(r['name']==name,'L0 regions must be A,B,C,scratch,scale_metadata in order')
  require(all(type(r[k]) is int and r[k]>0 for k in ('banks','subbanks','width','depth')),f'{name}: invalid SRAM geometry')
  require(r['width']==(128 if name=='scale_metadata' else 256),f'{name}: unsupported SRAM width')
  r['bytes']=r['banks']*r['subbanks']*r['width']//8*r['depth']
  r['physical_macros']=r['banks']*r['subbanks']
  r['combined_RW_GBs_at_1GHz']=r['physical_macros']*r['width']/8
 a,b,c,s,meta=regions
 p.update(L0_BYTES=sum(r['bytes'] for r in regions),OPERAND_BYTES=a['bytes']+b['bytes'],C_BYTES=c['bytes'],PARTIAL_BYTES=s['bytes'],META_BYTES=meta['bytes'],OPERAND_BANKS=a['banks']+b['banks'],C_BANKS=c['banks'],PARTIAL_BANKS=s['banks'],META_BANKS=meta['banks'],MAIN_BANK_BITS=256,META_BANK_BITS=128,OPERAND_BANK_DEPTH=a['depth'],C_BANK_DEPTH=c['depth'],PARTIAL_BANK_DEPTH=s['depth'],META_BANK_DEPTH=meta['depth'])
 for name,r in zip(('A','B','C','SCRATCH','META'),regions):p[name+'_SUBBANKS']=r['subbanks']
 p['SRAM_TOTAL_BYTES']=p['L0_BYTES'];p['L0_ADDRESS_BITS']=max(1,(p['L0_BYTES']-1).bit_length())
 require(p['L0_BYTES']<=2**p['AXI_ADDR_BITS'],'L0 exceeds address space')
 p['L0_TOTAL_SUBBANKS']=sum(r['physical_macros'] for r in regions);p['L0_TOTAL_BANKS']=sum(r['banks'] for r in regions)
 p['SRAM_READ_LATENCY']=p['L0_SRAM_MACRO_READ_CYCLES']
 arrays=p['ARRAY_COUNT'];hz=p['ACCEL_CLOCK_HZ'];p['MACS_PER_CLOCK']=arrays*1024;p['PEAK_TOPS']=2*p['MACS_PER_CLOCK']*hz/1e12
 p['INTERNAL_EXP_BIAS'],p['INTERNAL_EXP_BITS'],p['INTERNAL_MANTISSA_BITS']=(63,7,8) if p['INTERNAL_ACC_FORMAT'].startswith('LQ16') else (127,8,10)
 sizes={'SRCA':544,'SRCB':1056,'SRCC':4096,'TARGETR':4096}
 p['NEAR_MAC_REGFILE_BYTES']={k:arrays*p[k+'_SLOTS']*v for k,v in sizes.items()};p['NEAR_MAC_REGFILE_TOTAL_BYTES']=sum(p['NEAR_MAC_REGFILE_BYTES'].values())
 p['PE_ACC_CONTEXT_BYTES']=arrays*1024*contexts*(2 if p['INTERNAL_EXP_BITS']==7 else 4)
 p['SINGLE_CONTEXT_K32_LATENCY_CYCLES']=32*contexts+lat['FMA'];p['PANEL_PIPELINE_OVERHEAD_CYCLES']=32*contexts+8
 p['INTERNAL_ACC_LANES']=arrays*32;p['AXI_STRB_BITS']=p['AXI_DATA_BITS']//8
 p['AXI_RAW_GBS']=p['AXI_PORTS']*p['AXI_DATA_BITS']/8*p['AXI_CLOCK_HZ']/1e9
 p['AXI_AFTER_EFFICIENCY_GBS']=p['AXI_RAW_GBS']*p['MEM_EFFICIENCY'];p['MIN_RAW_GBS']=p['DMA_PAYLOAD_TARGET_GBS']/p['MEM_EFFICIENCY']
 require(p['DMA_PAYLOAD_TARGET_GBS']<=p['AXI_AFTER_EFFICIENCY_GBS'],'Requested payload exceeds conservative shared AXI service')
 p['FULL_BURST_MIN_READ_MO']=math.ceil(p['DMA_PAYLOAD_TARGET_GBS']*p['DRAM_READ_LATENCY_NS']/p['DMA_MAX_BURST_BYTES'])
 p['MAX_REFERENCE_LATENCY_NS']=2*p['REFERENCE_M']*p['REFERENCE_N']*p['REFERENCE_K']/p['SUSTAINED_TOPS_TARGET']/1e3
 p['PEAK_GROUP_RATE_PER_SECOND']=hz/32;p['L0_OPERAND_GBs_PEAK']=arrays*50*(hz/1e9)
 p['L0_C_READ_GBs_PEAK']=p['L0_C_WRITE_GBs_PEAK']=arrays*128*(hz/1e9)
 p['VECTOR_PEAK_ELEMENTS_PER_SECOND']=p['VECTOR_LANES']*p['VECTOR_CLOCK_HZ']
 require(p['SUSTAINED_TOPS_TARGET']<=p['PEAK_TOPS'],'Sustained target exceeds compute peak')
 return p
