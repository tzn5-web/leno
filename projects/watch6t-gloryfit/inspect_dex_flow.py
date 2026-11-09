#!/usr/bin/env python3
"""Read-only DEX method bodies and call sites for owned Android-app audit.
This displays symbolic targets and tiny instruction numbers, never raw proprietary source.
"""
import re,struct,zipfile,argparse,json
from dex_methods import dex_strings,uleb

def type_and_methods(b):
 ss=dex_strings(b)
 tn,to=struct.unpack_from('<II',b,0x40)
 types=[ss[struct.unpack_from('<I',b,to+i*4)[0]] for i in range(tn)]
 mn,mo=struct.unpack_from('<II',b,0x58)
 methods=[]
 for i in range(mn):
  cls,proto,name=struct.unpack_from('<HHI',b,mo+i*8)
  methods.append({'name':ss[name],'class':types[cls], 'idx':i})
 return ss,types,methods

def class_data(b,types,methods):
 cn,co=struct.unpack_from('<II',b,0x60)
 out={}
 for i in range(cn):
  class_idx,access,super_idx,ifoff,src,anoff,data_off,static=struct.unpack_from('<IIIIIIII',b,co+i*32)
  if not data_off: continue
  pos=data_off
  counts=[]
  for _ in range(4):
   c,pos=uleb(b,pos);counts.append(c)
  for amount in counts[:2]:
   for _ in range(amount):
    _,pos=uleb(b,pos);_,pos=uleb(b,pos)
  midx=0
  for amount in counts[2:]:
   midx=0
   for _ in range(amount):
    delta,pos=uleb(b,pos);acc,pos=uleb(b,pos);code_off,pos=uleb(b,pos)
    midx+=delta
    if midx>=len(methods):break
    if code_off:out[midx]=code_off
 return out

# Width of standard Dalvik opcodes in 16-bit code units. For unknown opcodes use 1.
WIDTH={}
for op in range(0x00,0x100): WIDTH[op]=1
for op in [0x02,0x05,0x08,0x13,0x15,0x16,0x19,0x1a,0x1c,0x1f,0x20,0x22,0x23,0x29,0x2d,0x2e,0x2f,0x30,0x31,0x32,0x33,0x34,0x35,0x36,0x37,0x38,0x39,0x3a,0x3b,0x3c,0x3d,0x44,0x45,0x46,0x47,0x48,0x49,0x4a,0x4b,0x4c,0x4d,0x4e,0x4f,0x50,0x51,0x52,0x53,0x54,0x55,0x56,0x57,0x58,0x59,0x5a,0x5b,0x5c,0x5d,0x5e,0x5f,0x60,0x61,0x62,0x63,0x64,0x65,0x66,0x67,0x68,0x69,0x6a,0x6b,0x6c,0x6d,0x90,0x91,0x92,0x93,0x94,0x95,0x96,0x97,0x98,0x99,0x9a,0x9b,0x9c,0x9d,0x9e,0x9f,0xa0,0xa1,0xa2,0xa3,0xa4,0xa5,0xa6,0xa7,0xa8,0xa9,0xaa,0xab,0xac,0xad,0xae,0xaf,0xd0,0xd1,0xd2,0xd3,0xd4,0xd5,0xd6,0xd7,0xd8,0xd9,0xda,0xdb,0xdc,0xdd,0xde,0xdf,0xe0,0xe1,0xe2]:WIDTH[op]=2
for op in [0x03,0x06,0x09,0x14,0x17,0x1b,0x24,0x25,0x26,0x2a,0x2b,0x2c,0x6e,0x6f,0x70,0x71,0x72,0x74,0x75,0x76,0x77,0x78]: WIDTH[op]=3
WIDTH[0x18]=5
for op in [0xfa,0xfb]:WIDTH[op]=4
for op in [0xfc,0xfd]:WIDTH[op]=3

def method_evidence(b,offset,strings,methods,limit=120):
 # Ignore try catch/debug metadata: inspect instructions only.
 registers,ins,outs,tries,dbg,n=struct.unpack_from('<HHHHII',b,offset)
 start=offset+16
 words=struct.unpack_from('<'+str(n)+'H',b,start) if n else []
 refs=[];i=0
 while i<len(words):
  word=words[i];op=word&255
  # method ref in 35c/3rc
  if op in [0x6e,0x6f,0x70,0x71,0x72,0x74,0x75,0x76,0x77,0x78] and i+1<len(words):
   mid=words[i+1]
   if mid<len(methods):
    m=methods[mid]
    refs.append({'at':i,'invoke':op,'method':m['class']+'->'+m['name']})
  elif op==0x1a and i+1<len(words):
   sid=words[i+1]
   if sid<len(strings) and re.search('dial|face|http|upload|ble|crc|status|data',strings[sid],re.I):
    refs.append({'at':i,'const_string':strings[sid][:150]})
  elif op==0x1b and i+2<len(words):
   sid=words[i+1]|(words[i+2]<<16)
   if sid<len(strings) and re.search('dial|face|http|upload|ble|crc|status|data',strings[sid],re.I):
    refs.append({'at':i,'const_string':strings[sid][:150]})
  width=WIDTH[op]
  # Special packed switch / fill-array payload follows pseudo nop; skip with guard.
  i+=max(1,width)
 return {'instructions':n,'registers':registers,'calls':refs[:limit]}

def run(apk):
 with zipfile.ZipFile(apk) as z:
  b=z.read('classes6.dex')
 ss,types,methods=type_and_methods(b)
 codes=class_data(b,types,methods)
 targets=['ActsDialCommandUtil;->uploadWatchFace','ActsDialCommandUtil;->applyWatchFace','ActsDialCommandUtil;->getWatchFaceParams','ActsDialCommandUtil;->setImageWatchFace',
          'ActsDialCommandUtil;->prepareSendWatchFaceData','ActsDialCommandUtil;->startSendDataSegments','ActsDialCommandUtil;->setWatchFaceType','ActsDialCommandUtil;->getSetImageWatchFaceCmd','ActsDialUtil;->uploadWatchFace','ActsDialUtil;->applyWatchFace','WriteCommandToBLE;->setImageWatchFaceConfigRk']
 found=[]
 for m in methods:
  key=m['class']+'->'+m['name']
  if m['idx'] in codes and any(t in key for t in targets):
   found.append({'class':m['class'],'method':m['name'],**method_evidence(b,codes[m['idx']],ss,methods)})
 return found

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('apk');a.add_argument('--output');args=a.parse_args()
 data=run(args.apk)
 if args.output:open(args.output,'w').write(json.dumps(data,ensure_ascii=False,indent=2))
 for d in data:
  print(d['class']+'->'+d['method'],'code-units',d['instructions'])
  for x in d['calls'][:26]:print(' ',x)
