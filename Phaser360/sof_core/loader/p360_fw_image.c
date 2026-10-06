/* SPDX-License-Identifier: BSD-3-Clause */
#include "p360_loader.h"

static uint32_t le32(const uint8_t *p)
{
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 |
        (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}
static uint32_t ror(uint32_t x, unsigned n) { return x >> n | x << (32u - n); }
static void sha_block(uint32_t state[8], const uint8_t block[64])
{
    static const uint32_t k[64] = {
        0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,
        0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,
        0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,
        0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,
        0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,
        0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,
        0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,
        0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u
    };
    uint32_t w[64], a,b,c,d,e,f,g,h;
    unsigned i;
    for (i=0;i<16;++i) w[i]=(uint32_t)block[i*4]<<24 |
        (uint32_t)block[i*4+1]<<16 | (uint32_t)block[i*4+2]<<8 | block[i*4+3];
    for (i=16;i<64;++i) {
        uint32_t s0=ror(w[i-15],7)^ror(w[i-15],18)^(w[i-15]>>3);
        uint32_t s1=ror(w[i-2],17)^ror(w[i-2],19)^(w[i-2]>>10);
        w[i]=w[i-16]+s0+w[i-7]+s1;
    }
    a=state[0];b=state[1];c=state[2];d=state[3];
    e=state[4];f=state[5];g=state[6];h=state[7];
    for (i=0;i<64;++i) {
        uint32_t t1=h+(ror(e,6)^ror(e,11)^ror(e,25))+((e&f)^(~e&g))+k[i]+w[i];
        uint32_t t2=(ror(a,2)^ror(a,13)^ror(a,22))+((a&b)^(a&c)^(b&c));
        h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
    }
    state[0]+=a;state[1]+=b;state[2]+=c;state[3]+=d;
    state[4]+=e;state[5]+=f;state[6]+=g;state[7]+=h;
}

int p360_fw_validate(const uint8_t *image, size_t bytes, struct p360_fw_view *view)
{
    static const uint32_t expected[8] = {0xf68694b6u,0x19725001u,0x6a9c5ffbu,0x46fa8adau,
        0xa599a32du,0xb95aa19au,0x0ecf5bd4u,0xed1c62abu};
    uint32_t s[8]={0x6a09e667u,0xbb67ae85u,0x3c6ef372u,0xa54ff53au,
        0x510e527fu,0x9b05688cu,0x1f83d9abu,0x5be0cd19u};
    uint8_t tail[64]={0};
    uint64_t bits=(uint64_t)P360_FW_FILE_BYTES*8u;
    size_t i, pos;
    uint32_t diff=0;
    if (!view) return P360_L_ARGUMENT;
    view->payload=0;view->bytes=0;
    if (!image || bytes!=P360_FW_FILE_BYTES) return P360_L_IMAGE;
    if (le32(image)!=0x6e614d58u || le32(image+4)!=P360_FW_MANIFEST_BYTES ||
        le32(image+8)!=16u || le32(image+12)!=0x01000000u) return P360_L_IMAGE;
    /* Do not send unsigned host metadata to the DSP ROM DMA loader. */
    for (pos=16;pos<P360_FW_MANIFEST_BYTES;) {
        uint32_t size=le32(image+pos+4);
        if (size<16u || (size&15u) || size>P360_FW_MANIFEST_BYTES-pos) return P360_L_IMAGE;
        pos+=size;
    }
    /* This pinned image is exactly a multiple of SHA256's 64-byte block. */
    for (i=0;i<bytes;i+=64u) sha_block(s,image+i);
    tail[0]=0x80;
    for (i=0;i<8;++i) tail[63u-i]=(uint8_t)(bits>>(i*8u));
    sha_block(s,tail);
    for (i=0;i<8;++i) diff|=s[i]^expected[i];
    if (diff) return P360_L_IMAGE;
    view->payload=image+P360_FW_MANIFEST_BYTES;
    view->bytes=P360_FW_PAYLOAD_BYTES;
    return P360_L_OK;
}

/* Actual .fw_ready section extracted from the already-built diagnostic v2 ELF.
 * SOF 1.9.3, IPC3 ABI 3.20, tag a9780, reproducible strings, flags 0x10.
 * src_hash=0 in this build, so version fields alone do NOT authenticate firmware.
 */
static const uint8_t expected_ready[P360_FW_READY_BYTES] = {
    0x6c,0x00,0x00,0x00,0x00,0x00,0x00,0x70,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
    0x3c,0x00,0x00,0x00,0x01,0x00,0x09,0x00,0x03,0x00,0xff,0xff,
    0x64,0x74,0x65,0x72,0x6d,0x69,0x6e,0x2e,0x00,0x00,0x00,0x00,
    0x66,0x77,0x72,0x65,0x61,0x64,0x79,0x2e,0x00,0x00,0x61,0x39,
    0x37,0x38,0x30,0x00,0x00,0x40,0x01,0x03,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
    0x10,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
};
int p360_fw_ready_validate(const uint8_t *first, const uint8_t *second, size_t bytes)
{
    size_t i;
    uint32_t diff=0;
    if (!first || !second || bytes!=P360_FW_READY_BYTES) return P360_L_READY;
    for (i=0;i<bytes;++i) diff|=(uint32_t)(first[i]^second[i]) |
        (uint32_t)(first[i]^expected_ready[i]);
    return diff ? P360_L_READY : P360_L_OK;
}

static void put32(uint8_t *p,uint32_t v)
{
    p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);p[2]=(uint8_t)(v>>16);p[3]=(uint8_t)(v>>24);
}
int p360_bdl_build(const struct p360_dma_span *spans, size_t span_count,
    uint64_t bdl_address, uint32_t payload_bytes, int dma64,
    uint8_t *bdl, size_t bdl_bytes, uint16_t *entry_count)
{
    size_t i,j,count=0;
    uint64_t total=0,bdl_end;
    if (!entry_count) return P360_L_ARGUMENT;
    *entry_count=0;
    if (!spans || !bdl || !span_count || span_count>P360_BDL_MAX ||
        payload_bytes!=P360_FW_PAYLOAD_BYTES || !bdl_address || (bdl_address&127u) ||
        bdl_bytes!=P360_BDL_MAX*16u || bdl_address>UINT64_MAX-bdl_bytes ||
        (dma64!=0 && dma64!=1)) return P360_L_ARGUMENT;
    bdl_end=bdl_address+bdl_bytes;
    if (!dma64 && bdl_end>UINT64_C(0x100000000)) return P360_L_ARGUMENT;
    /* Validate all spans before publishing a usable BDL count. */
    for (i=0;i<span_count;++i) {
        uint64_t a=spans[i].address,end;
        uint32_t n=spans[i].bytes;
        if (!a || (a&127u) || !n || (n&127u) || a>UINT64_MAX-n) return P360_L_ARGUMENT;
        end=a+n;
        if (!dma64 && end>UINT64_C(0x100000000)) return P360_L_ARGUMENT;
        if (a<bdl_end && bdl_address<end) return P360_L_ARGUMENT;
        for (j=0;j<i;++j)
            if (a<spans[j].address+spans[j].bytes && spans[j].address<end)
                return P360_L_ARGUMENT;
        total+=n;
        if (total>payload_bytes) return P360_L_ARGUMENT;
        while (n) {
            uint32_t chunk=4096u-(uint32_t)(a&4095u);
            if (chunk>n) chunk=n;
            if (++count>P360_BDL_MAX) return P360_L_ARGUMENT;
            a+=chunk;n-=chunk;
        }
    }
    if (total!=payload_bytes) return P360_L_ARGUMENT;
    count=0;
    for (i=0;i<bdl_bytes;++i) bdl[i]=0;
    for (i=0;i<span_count;++i) {
        uint64_t a=spans[i].address;
        uint32_t n=spans[i].bytes;
        while (n) {
            uint32_t chunk=4096u-(uint32_t)(a&4095u);
            uint8_t *p=bdl+count++*16u;
            if (chunk>n) chunk=n;
            put32(p,(uint32_t)a);put32(p+4,(uint32_t)(a>>32));put32(p+8,chunk);
            /* IOC=0: the boot engine polls ROM, not audio period interrupts. */
            a+=chunk;n-=chunk;
        }
    }
    *entry_count=(uint16_t)count;
    return P360_L_OK;
}
