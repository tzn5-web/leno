#!/usr/bin/env python3
"""Disable ad SDK loading/display entry points in one APK without rebuilding DEX string pools.
Patch only definitions inside SDK/SHAREit ad packages, never core file-transfer code.
Requires resigning result after patch; preserves ZIP members/resources/native binaries.
"""
import argparse, hashlib, io, json, re, struct, zipfile, zlib
from pathlib import Path

ALLOWED_PREFIXES=(
 "Lcom/adexchange/", "Lcom/ushareit/ads/", "Lcom/san/ads/",
 "Lcom/sunit/mediation/", "Lcom/google/android/gms/ads/",
 "Lcom/applovin/mediation/ads/", "Lcom/ironsource/mediationsdk/",
 "Lcom/facebook/ads/", "Lcom/bytedance/sdk/openadsdk/",
 "Lcom/yandex/mobile/ads/", "Lcom/monetization/ads/",
)
# Prevent exposure of advertisements from ad providers, not general content and transfer routines.
VOID_ACTIONS={
 "loadAd", "loadAds", "loadInterstitial", "loadRewardedVideo",
 "loadRewardedAd", "loadBanner", "loadNativeAd", "loadSplashAd",
 "loadAppOpenAd", "loadInterstitialAd", "loadReward", "preloadAd",
 "showAd", "showAds", "showInterstitial", "showRewardedVideo", "showBanner",
 "showSplash", "showAppOpenAd", "showInterstitialAd", "showRewardedAd",
 "showReward", "showFullScreenAd",
}
FALSE_ACTIONS={"isAdReady","hasAd","hasAds","isAdLoaded","isLoaded","isAdAvailable"}
# These explicit internal entry points are named 'load'/'show' rather than an ad-specific identifier.
EXPLICIT={
 ("Lcom/adexchange/ads/core/RTBAd;", "load", "V"),
 ("Lcom/adexchange/ads/base/RTBBaseAd;", "load", "V"),
 ("Lcom/adexchange/ads/RTBFullScreenAd;", "show", "V"),
 ("Lcom/adexchange/internal/interstitial/InnerInterstitialAd;", "show", "V"),
 ("Lcom/adexchange/internal/interstitial/InterstitialAdLoader;", "show", "V"),
 ("Lcom/adexchange/internal/splash/InnerSplashAd;", "show", "V"),
 ("Lcom/adexchange/internal/splash/InnerSplashAdLoader;", "show", "V"),
 ("Lcom/adexchange/internal/reward/InnerRewardAdLoader;", "show", "V"),
 ("Lcom/ushareit/ads/loader/wrapper/AdsHInterstitialWrapper;", "show", "V"),
 ("Lcom/ushareit/ads/loader/wrapper/AdsHRewardWrapper;", "show", "V"),
 ("Lcom/ushareit/ads/loader/waterfall/AbsLayerCombinedAdLoader;", "isLoaderTypeMatchConfig", "Z"),
}
def uleb(data,pos):
    x=0
    for i in range(5):
        b=data[pos]
        pos+=1
        x|=(b&127)<<(7*i)
        if b<128:return x,pos
    raise ValueError("ULEB too long")
def read_strings(data):
    count,ofs=struct.unpack_from("<II",data,0x38)
    out=[]
    for i in range(count):
        item=struct.unpack_from("<I",data,ofs+i*4)[0]
        _,start=uleb(data,item)
        out.append(data[start:data.index(b"\0",start)].decode("utf8","replace"))
    return out
def patch_dex(contents):
    d=bytearray(contents)
    if not d.startswith(b"dex\n"):return contents,[]
    strings=read_strings(d)
    ntypes,to=struct.unpack_from("<II",d,0x40)
    types=[strings[struct.unpack_from("<I",d,to+4*i)[0]] for i in range(ntypes)]
    nproto,po=struct.unpack_from("<II",d,0x48)
    returns=[types[struct.unpack_from("<I",d,po+12*i+4)[0]] for i in range(nproto)]
    nmethods,mo=struct.unpack_from("<II",d,0x58)
    method_ids=[struct.unpack_from("<HHI",d,mo+8*i) for i in range(nmethods)]
    nclasses,co=struct.unpack_from("<II",d,0x60)
    patched=[]
    for i in range(nclasses):
        classid,_,_,_,_,_,dataoff,_=struct.unpack_from("<8I",d,co+i*32)
        cls=types[classid]
        if not cls.startswith(ALLOWED_PREFIXES) or not dataoff:continue
        off=dataoff
        counts=[]
        for k in range(4):
            n,off=uleb(d,off)
            counts.append(n)
        for k in range(counts[0]+counts[1]):
            _,off=uleb(d,off)
            _,off=uleb(d,off)
        for k in (2,3):
            index=0
            for j in range(counts[k]):
                delta,off=uleb(d,off)
                _,off=uleb(d,off)
                codeoff,off=uleb(d,off)
                index+=delta
                if not codeoff:continue
                _,proto,nameslot=method_ids[index]
                method=strings[nameslot]
                ret=returns[proto]
                match=(ret=="V" and method in VOID_ACTIONS) or (ret=="Z" and method in FALSE_ACTIONS) or ((cls,method,ret) in EXPLICIT)
                if not match:continue
                registers,ins,outs,tries,debug,size=struct.unpack_from("<HHHHII",d,codeoff)
                if ret=="Z" and registers==0:continue
                if ret=="V" and size<1:continue
                if ret=="Z" and size<2:continue
                start=codeoff+16
                data=(b"\x0e\x00" if ret=="V" else b"\x12\x00\x0f\x00")
                d[start:start+len(data)]=data
                patched.append({"class":cls,"method":method,"return":ret})
    if patched:
        d[12:32]=hashlib.sha1(d[32:]).digest()
        struct.pack_into("<I",d,8,zlib.adler32(d[12:])&0xffffffff)
    return bytes(d),patched

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--report",required=True)
    args=ap.parse_args()
    n=0
    with zipfile.ZipFile(args.input) as inp,zipfile.ZipFile(args.output,"w") as out:
        report={}
        for member in inp.infolist():
            body=inp.read(member.filename)
            if re.fullmatch(r"classes\d*\.dex",member.filename):
                body,methods=patch_dex(body)
                report[member.filename]=methods
                n+=len(methods)
            if member.filename.startswith("META-INF/") and member.filename.upper().endswith((".SF",".RSA",".DSA",".EC",".MF")):
                continue
            out.writestr(member,body)
    if n<12:
        raise SystemExit(f"ONLY_{n}_AD_METHODS_PATCHED: refusing to claim effective ad suppression")
    with zipfile.ZipFile(args.output) as z:
        assert z.testzip() is None
    data={"method_entrypoints_disabled":n,"by_dex":report,"limitations":"SDK ad-load/show suppression only; some remote content, offline upsell, custom ads may remain. Android runtime + visual checks still required."}
    Path(args.report).write_text(json.dumps(data,indent=2))
    print("SHAREIT_AD_SDK_LOAD_AND_SHOW_DISABLED",n)
if __name__=="__main__":
    main()
