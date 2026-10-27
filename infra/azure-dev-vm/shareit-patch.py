#!/usr/bin/env python3
"""Personal-use SHAREit 6.27.58 static ad endpoint neutralization, from an original signed APK.
The modified APK will require new signing and runtime testing. Never publish input/output in Git.
"""
import argparse, hashlib, json, pathlib, re, struct, sys, zipfile, zlib

DOMAINS = [
 "2118c602-ads-access-f681-1832569655.ap-southeast-1.elb.amazonaws.com",
 "api-test.hellay.net","api.rqmob.com","cfg.dalyfeds.com",
 "midas-api-stress.hellay.net","plutus-pre.lacunads.com",
 "plutus-test.lacunads.com","test.midas-access.ads.sg3.api",
 "plutus.lacunads.com","app.adjust.cn","app.adjust.com",
 "app.adjust.net.in","app.adjust.world","app.eu.adjust.com",
 "app.tr.adjust.com","app.us.adjust.com",
 "pagead2.googlesyndication.com","plutus-track-pre.lacunads.com",
 "plutus-track-test.lacunads.com","plutus-track.lacunads.com",
 "www.googleadservices.com","ap-adcs-test.rqmob.com",
 "ap-adcs.rqmob.com","distribution-test.rqmob.com",
 "distribution.rqmob.com","test.midas-mediation.ads.sg3.api",
 "adcs.rqmob.com","appclick.rqmob.com","midas-api-test.hellay.net",
 "adconf.rqmob.com","midas-api.hellay.net","static.rqmob.com",
 "googleads.g.doubleclick.net", "adservice.google.com",
 "googleads4.g.doubleclick.net", "applovin.com"
]
def patch_dex(data):
    b = bytearray(data)
    counts = {}
    for dom in sorted(set(DOMAINS), key=len, reverse=True):
        needle = dom.encode("ascii")
        replacement = ("x" * (len(needle)-8) + ".invalid").encode("ascii")
        if len(replacement) != len(needle):
            raise ValueError("length mismatch "+dom)
        # Restrict to ASCII hostname occurrences. Equal-length replacement is
        # crucial for not changing dex string lengths/offsets.
        n = bytes(b).count(needle)
        if n:
            b = b.replace(needle, replacement)
            counts[dom] = n
    if counts:
        b[12:32] = hashlib.sha1(b[32:]).digest()
        struct.pack_into("<I", b, 8, zlib.adler32(b[12:]) & 0xffffffff)
    return bytes(b), counts
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True)
    p.add_argument("--output",required=True)
    p.add_argument("--report",required=True)
    args=p.parse_args()
    source=pathlib.Path(args.source)
    expected_md5="74c64f8ff3ac6507730cd6659315883d"
    md5=hashlib.md5(source.read_bytes()).hexdigest()
    if md5 != expected_md5:
        print("SOURCE_MD5_INVALID",md5,"expected",expected_md5,file=sys.stderr)
        raise SystemExit(8)
    total={}; modified=[]; count=0
    with zipfile.ZipFile(source) as z, zipfile.ZipFile(args.output,"w") as out:
        for entry in z.infolist():
            payload=z.read(entry.filename)
            if re.match(r"^META-INF/[^/]+\\.(RSA|DSA|EC|SF|MF)$",entry.filename,re.I):
                continue
            if re.fullmatch(r"classes\\d*\\.dex",entry.filename):
                payload,found=patch_dex(payload)
                for d,n in found.items(): total[d]=total.get(d,0)+n
                if found: modified.append(entry.filename);count+=sum(found.values())
            out.writestr(entry,payload)
    report={"input_md5":md5, "input_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
        "dex_files_modified":modified,"ad_host_occurrences_blocked":count,
        "per_host":total,"output_unsigned_sha256":hashlib.sha256(pathlib.Path(args.output).read_bytes()).hexdigest(),
        "notes":"Static DNS hostname neutralization only; dynamic ads, runtime and device behavior unverified. Requires signing by a new certificate."}
    pathlib.Path(args.report).write_text(json.dumps(report,indent=2))
    print("SHAREIT_STATIC_PATCH_PASS",json.dumps({"dex_files_modified":len(modified),"ad_hosts_blocked":count,"output":args.output}))
if __name__=="__main__": main()
