#!/usr/bin/env python3
"""Read APK Signing Block v2/v3 X.509 certificate SHA-256 without keystore.

This is for identity comparison, NOT a cryptographic signature verification.
Android SDK apksigner verify must also pass before a release. Never attempt
to derive or recover a PRIVATE signing key from public certificate bytes.
"""
import argparse
import hashlib
import struct
from pathlib import Path

SIG_BLOCK_MAGIC=b"APK Sig Block 42"
V2=0x7109871a
V3=0xf05368c0

def u32(buf,pos):
    if pos+4>len(buf):raise ValueError("Truncated uint32")
    return struct.unpack_from("<I",buf,pos)[0]

def u64(buf,pos):
    if pos+8>len(buf):raise ValueError("Truncated uint64")
    return struct.unpack_from("<Q",buf,pos)[0]

def lp(buf,pos):
    n=u32(buf,pos)
    end=pos+4+n
    if end>len(buf):raise ValueError("Truncated length-prefixed field")
    return buf[pos+4:end],end

def fingerprints(apk:Path):
    data=apk.read_bytes()
    eocd=data.rfind(b"PK\x05\x06",max(0,len(data)-66000))
    if eocd<0:raise ValueError("No ZIP End Of Central Directory")
    central=u32(data,eocd+16)
    if data[central-16:central] != SIG_BLOCK_MAGIC:
        raise ValueError("No APK Signing Block v2/v3 (possibly unsigned or v1 only)")
    size=u64(data,central-24)
    start=central-size-8
    if start<0 or u64(data,start)!=size:
        raise ValueError("Corrupted APK Signing Block sizes")
    p=start+8
    result=set()
    while p<central-24:
        length=u64(data,p)
        if length<4 or p+8+length>central-24:
            raise ValueError("Malformed APK Signing Block pair")
        kind=u32(data,p+8)
        payload=data[p+12:p+8+length]
        p+=8+length
        if kind not in (V2,V3):continue
        signers,_=lp(payload,0)
        cursor=0
        while cursor<len(signers):
            signer,cursor=lp(signers,cursor)
            signed,_=lp(signer,0)
            digests,ptr=lp(signed,0)
            certs,_=lp(signed,ptr)
            certptr=0
            while certptr<len(certs):
                cert,certptr=lp(certs,certptr)
                if not cert or cert[0]!=0x30:
                    raise ValueError("Signer certificate is not X.509 DER")
                result.add(hashlib.sha256(cert).hexdigest().lower())
    if not result:raise ValueError("No v2/v3 signing certificates")
    return sorted(result)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("apk",type=Path)
    p.add_argument("--baseline",type=Path,help="Require the same signing certificate as this working APK")
    p.add_argument("--expected-sha256",help="Require this 64-character X.509 SHA256 digest")
    args=p.parse_args()
    current=fingerprints(args.apk)
    if len(current)!=1:raise RuntimeError("Refusing unexpected multiple signers")
    print("APK:",args.apk,"Signer certificate SHA256:",current[0])
    if args.baseline:
        known=fingerprints(args.baseline)
        if known!=current:
            raise RuntimeError("BLOCKED: installed and candidate APK certificates differ")
        print("PASS: exactly the same signing certificate as the working APK")
    if args.expected_sha256:
        expected=args.expected_sha256.lower().replace(":","")
        if len(expected)!=64 or current[0]!=expected:
            raise RuntimeError("BLOCKED: unexpected signing certificate SHA256")
        print("PASS: matches pinned expected certificate SHA256")
    print("NOTE: certificate comparison only — run apksigner verify too")

if __name__=="__main__":
    main()
