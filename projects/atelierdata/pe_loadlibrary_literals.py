"""Read-only PE32 static triage of literal LoadLibrary call arguments.

Requires an independently known SHA256. Only exact PUSH imm32; CALL [IAT]
byte patterns are candidates; no execution, CFG reachability, IDF decoding or
license handling. Original binaries and detailed reports stay private.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

MAX_PE = 64 * 1024 * 1024
MAX_IMPORTS = 4096
MAX_CANDIDATES = 20000
MAX_STRING = 160
DLL = re.compile(r'^[A-Za-z0-9_.+ -]{1,128}\.dll$', re.I)


def u16(data, at):
    if at < 0 or at + 2 > len(data): raise ValueError('Truncated PE')
    return struct.unpack_from('<H', data, at)[0]


def u32(data, at):
    if at < 0 or at + 4 > len(data): raise ValueError('Truncated PE')
    return struct.unpack_from('<I', data, at)[0]


def parse_pe(data):
    if not (64 <= len(data) <= MAX_PE) or data[:2] != b'MZ':
        raise ValueError('Not a bounded MZ file')
    pe = u32(data, 0x3c)
    if pe + 24 > len(data) or data[pe:pe+4] != b'PE\0\0':
        raise ValueError('Invalid PE signature')
    sections_count = u16(data, pe+6)
    optional_size = u16(data, pe+20)
    opt = pe + 24
    if not 1 <= sections_count <= 96 or opt+optional_size > len(data) or optional_size < 112:
        raise ValueError('Invalid section/optional header')
    if u16(data, opt) != 0x10b:
        raise ValueError('Only PE32 x86 supported')
    image_base = u32(data, opt+28)
    if u32(data, opt+92) < 2:
        raise ValueError('Import directory absent')
    import_rva, import_size = u32(data, opt+104), u32(data, opt+108)
    sections = []
    for i in range(sections_count):
        p = opt+optional_size+40*i
        if p+40 > len(data): raise ValueError('Truncated section table')
        name = data[p:p+8].split(b'\0')[0].decode('ascii','replace')
        virtual_size, rva, raw_size, raw_at = struct.unpack_from('<IIII',data,p+8)
        flags = u32(data,p+36)
        if raw_size and (raw_at > len(data) or raw_size > len(data)-raw_at):
            raise ValueError('Section exceeds file')
        sections.append(dict(name=name,virtual_size=virtual_size,rva=rva,
                             raw_size=raw_size,raw_at=raw_at,
                             executable=bool(flags & 0x20000000)))
    def rva_to_file(rva, length=1):
        for sec in sections:
            offset = rva-sec['rva']
            if offset >= 0 and length >= 0 and offset+length <= sec['raw_size']:
                return sec['raw_at']+offset
        raise ValueError('RVA outside raw section')
    def cstr(rva, max_size=MAX_STRING):
        start = rva_to_file(rva)
        end = data.find(b'\0', start, min(len(data),start+max_size))
        if end < 0 or end == start:
            raise ValueError('Missing bounded ASCII string')
        raw = data[start:end]
        if any(c < 32 or c > 126 for c in raw):
            raise ValueError('Nonprintable ASCII string')
        return raw.decode('ascii')
    imports = {}
    if import_rva:
        if import_size < 20 or import_size > 65536:
            raise ValueError('Import directory size invalid')
        for i in range(min(MAX_IMPORTS,import_size//20)):
            p = rva_to_file(import_rva+i*20,20)
            original, timestamp, chain, name_rva, thunk_rva = struct.unpack_from('<IIIII',data,p)
            if not (original or timestamp or chain or name_rva or thunk_rva):
                break
            if not name_rva or not thunk_rva:
                raise ValueError('Malformed import descriptor')
            dll_name = cstr(name_rva)
            thunk_source = original or thunk_rva
            for j in range(MAX_IMPORTS):
                thunk = u32(data,rva_to_file(thunk_source+4*j,4))
                if not thunk: break
                if thunk & 0x80000000: continue
                func_name = cstr(thunk+2)
                imports[image_base+thunk_rva+4*j] = (dll_name,func_name)
            else:
                raise ValueError('Too many imports')
        else:
            raise ValueError('Unterminated import directory')
    return dict(image_base=image_base,sections=sections,imports=imports,
                rva_to_file=rva_to_file,cstr=cstr)


def analyze(data, expected_sha256):
    if not isinstance(expected_sha256,str) or not re.fullmatch('[a-fA-F0-9]{64}',expected_sha256):
        raise ValueError('Expected SHA256 required')
    sha = hashlib.sha256(data).hexdigest()
    if sha != expected_sha256.lower():
        raise ValueError('Original SHA256 mismatch')
    pe = parse_pe(data)
    relevant = {va: symbol for va, (dll, symbol) in pe['imports'].items()
                if dll.lower() == 'kernel32.dll' and symbol in ('LoadLibraryA','LoadLibraryW')}
    candidates = []
    for sec in pe['sections']:
        if not sec['executable'] or not sec['raw_size']:
            continue
        raw = data[sec['raw_at']:sec['raw_at']+sec['raw_size']]
        at = raw.find(b'\x68')
        while at >= 0:
            if at+11 <= len(raw) and raw[at+5:at+7] == b'\xff\x15':
                iat = u32(raw,at+7)
                if iat in relevant:
                    string_va = u32(raw,at+1)
                    dll_literal = None
                    try:
                        if string_va >= pe['image_base']:
                            candidate = pe['cstr'](string_va-pe['image_base'])
                            if DLL.fullmatch(candidate): dll_literal = candidate
                    except ValueError:
                        pass
                    candidates.append(dict(call_va=pe['image_base']+sec['rva']+at+5,
                                           push_va=pe['image_base']+sec['rva']+at,
                                           pointer_va=string_va,iat_va=iat,
                                           import_symbol=relevant[iat],
                                           literal=dll_literal))
                    if len(candidates)>MAX_CANDIDATES:
                        raise ValueError('Too many candidate callsites')
            at = raw.find(b'\x68',at+1)
    valid = [c for c in candidates if c['literal'] is not None]
    public = dict(schema='atelierdata-loadlibrary-literal-aggregate-v1',
                  sha256=sha, import_loadlibrary_symbols=sorted(set(relevant.values())),
                  adjacent_push_call_candidates=len(candidates),
                  resolved_dll_literal_candidates=len(valid),
                  distinct_dll_literals=len({c['literal'].lower() for c in valid}),
                  unresolved_candidates=len(candidates)-len(valid),
                  target_executed=False, cfg_reachability_proven=False,
                  idf_decoder_proven=False,
                  note='Byte patterns and literal pointers only; Ghidra must verify instructions and reachability.')
    private = dict(schema='atelierdata-loadlibrary-literal-private-v1',sha256=sha,
                   md5=hashlib.md5(data).hexdigest(),candidates=candidates)
    return public, private


def run(pe_path, expected_sha256, public_output, private_output=None):
    pe_path=Path(pe_path)
    with pe_path.open('rb') as stream:
        data=stream.read(MAX_PE+1)
    if len(data)>MAX_PE: raise ValueError('PE exceeds size bound')
    if private_output and Path(public_output).resolve()==Path(private_output).resolve():
        raise ValueError('Private and public outputs must differ')
    public, private = analyze(data,expected_sha256)
    Path(public_output).write_text(json.dumps(public,indent=2)+'\n',encoding='utf-8')
    if private_output:
        Path(private_output).write_text(json.dumps(private,indent=2)+'\n',encoding='utf-8')
    return public


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pe',type=Path,required=True)
    parser.add_argument('--expected-sha256',required=True)
    parser.add_argument('--public-output',type=Path,required=True)
    parser.add_argument('--private-output',type=Path)
    args=parser.parse_args()
    result=run(args.pe,args.expected_sha256,args.public_output,args.private_output)
    print('PE_LOADLIBRARY_STATIC=PASS candidates='+str(result['adjacent_push_call_candidates']))

if __name__=='__main__':
    main()
