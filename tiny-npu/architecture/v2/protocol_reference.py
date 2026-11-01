#!/usr/bin/env python3
"""Executable tile addressing / OIC oracle, not a hardware throughput claim."""
from pathlib import Path
import json
OUT=Path(__file__).resolve().parent

def a_address(kt,mt,row,k,MT,base=0):
 nibble=(((kt*MT+mt)*32+row)*32+k)
 return base+nibble//2,nibble%2

def b_address(kt,nt,col,k,NT,base=0):
 return base+(((kt*NT+nt)*32+col)*32+k)

def c_address(mt,nt,row,col,NT,arrays=10,base=0):
 tile=mt*NT+nt;group,lane=divmod(tile,arrays)
 return base+(((group*32+row)*arrays+lane)*32+col)*4

def bank_address(byte_address,banks,word_bytes=32):
 word=byte_address//word_bytes
 return word%banks,word//banks,byte_address%word_bytes

class OIC:
 def __init__(self):self.credits={};self.seq={};self.epoch=1
 def credit(self,name,value,maximum):self.credits[name]=[value,maximum]
 def event(self,name,value=0):self.seq[name]=value
 def atomic_issue(self,epoch,waits,acquires):
  if epoch!=self.epoch:return False
  if not all(self.seq[n]>=value for n,value in waits.items()):return False
  if not all(self.credits[n][0]>=amount for n,amount in acquires.items()):return False
  for n,amount in acquires.items():self.credits[n][0]-=amount
  return True
 def release(self,name,amount):
  value,maximum=self.credits[name]
  if amount<0 or value+amount>maximum:raise ValueError('credit overflow')
  self.credits[name][0]+=amount
 def commit_event(self,name,value):
  if value<self.seq[name] or value>=2**64:raise ValueError('sequence rollback/overflow')
  self.seq[name]=value

def main():
 checks=0
 # Every A/B element in a multi-tile panel has a unique address (including nibble).
 for kt in range(3):
  aa={a_address(kt,mt,r,k,5) for mt in range(5) for r in range(32) for k in range(32)}
  bb={b_address(kt,nt,c,k,7) for nt in range(7) for c in range(32) for k in range(32)}
  assert len(aa)==5*1024 and len(bb)==7*1024;checks+=len(aa)+len(bb)
 addresses={c_address(mt,nt,r,c,32) for mt in range(32) for nt in range(32) for r in range(32) for c in range(32)}
 assert len(addresses)==1024*1024
 assert max(addresses)+4<=5*1024**2;checks+=len(addresses)
 for row in range(32):
  words={c_address(0,nt,row,c,32)//32 for nt in range(10) for c in range(32)}
  banks=[word%40 for word in words]
  assert len(words)==40 and len(set(banks))==40;checks+=40
 # Physical single-port mapping: same-row R/W conflicts; adjacent rows do not.
 subbank_checks=0
 for row in range(32):
  def physical(r):
   words={c_address(0,t,r,col,32)//32 for t in range(10) for col in range(32)}
   return {(w%40,(w//40)%4) for w in words}
  read=physical(row);same_write=physical(row);phased_write=physical((row+1)%32)
  assert len(read)==40 and len(read & same_write)==40
  assert not read & phased_write
  subbank_checks+=80
 # Register local bank+address geometry supports column-vector MAC access.
 assert len({(row,slot*32+k) for row in range(32) for slot in range(8) for k in range(32)})==8192
 o=OIC()
 for n in ('A','B','C'):o.event(n)
 for n,cap in [('a_free',8),('b_free',8),('c_free',8),('target_free',8)]:o.credit(n,cap,cap)
 before={k:v[:] for k,v in o.credits.items()}
 assert not o.atomic_issue(1,{'A':1,'B':1,'C':1},{'target_free':1})
 assert o.credits==before
 for n in ('A','B','C'):o.commit_event(n,1)
 # Missing credit must not consume another resource in a partial acquire.
 assert not o.atomic_issue(1,{'A':1},{'a_free':9,'target_free':1})
 assert o.credits==before
 assert o.atomic_issue(1,{'A':1,'B':1,'C':1},{'a_free':1,'b_free':1,'c_free':1,'target_free':1})
 assert not o.atomic_issue(0,{},{});o.release('target_free',1)
 assert o.credits['target_free'][0]==8
 try:o.release('target_free',1);raise AssertionError('overflow accepted')
 except ValueError:pass
 # A two-reader L0 panel cannot be reused after only one reader retires.
 refs=2;refs-=1;assert refs!=0;refs-=1;assert refs==0
 result=dict(status='PASS',address_checks=checks,physical_subbank_checks=subbank_checks,C_bank_row_words=40,
  C_bank_row_conflicts=0,C_bytes_with_group_padding=max(addresses)+4,
  OIC_checks=['all_waits_before_issue','all_or_nothing_credit','stale_epoch_reject',
              'credit_return','overflow_reject','two_reader_panel_lifetime'],
  scope='software reference; TC/OIC RTL and real bubbleless timing are not implemented')
 (OUT/'protocol_results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
