/* SPDX-License-Identifier: BSD-3-Clause */
#include "p360_loader.h"
#include <string.h>

/* Full-file SHA256 of the reconstructed diagnostic-v2 / tone-fixed image.
 * The SHA implementation is intentionally tiny and local to this verifier.
 */
struct sha256_ctx { uint32_t h[8]; uint64_t bits; uint8_t block[64]; size_t used; };
static const uint32_t k256[64]={
0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,
0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,
0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,
0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,
0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,
0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,
0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,
0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u};
static uint32_t rr(uint32_t x,unsigned n){return (x>>n)|(x<<(32u-n));}
static uint32_t be32(const uint8_t *p){return ((uint32_t)p[0]<<24)|((uint32_t)p[1]<<16)|((uint32_t)p[2]<<8)|p[3];}
static void sha_block(struct sha256_ctx *c,const uint8_t *b)
{
    uint32_t w[64],a,bv,d,e,f,g,h,t1,t2,cc;unsigned i;
    for(i=0;i<16;i++)w[i]=be32(b+4*i);
    for(;i<64;i++){uint32_t s0=rr(w[i-15],7)^rr(w[i-15],18)^(w[i-15]>>3);uint32_t s1=rr(w[i-2],17)^rr(w[i-2],19)^(w[i-2]>>10);w[i]=w[i-16]+s0+w[i-7]+s1;}
    a=c->h[0];bv=c->h[1];cc=c->h[2];d=c->h[3];e=c->h[4];f=c->h[5];g=c->h[6];h=c->h[7];
    for(i=0;i<64;i++){uint32_t s1=rr(e,6)^rr(e,11)^rr(e,25);uint32_t ch=(e&f)^((~e)&g);t1=h+s1+ch+k256[i]+w[i];uint32_t s0=rr(a,2)^rr(a,13)^rr(a,22);uint32_t maj=(a&bv)^(a&cc)^(bv&cc);t2=s0+maj;h=g;g=f;f=e;e=d+t1;d=cc;cc=bv;bv=a;a=t1+t2;}
    c->h[0]+=a;c->h[1]+=bv;c->h[2]+=cc;c->h[3]+=d;c->h[4]+=e;c->h[5]+=f;c->h[6]+=g;c->h[7]+=h;
}
static void sha_init(struct sha256_ctx *c){static const uint32_t h[8]={0x6a09e667u,0xbb67ae85u,0x3c6ef372u,0xa54ff53au,0x510e527fu,0x9b05688cu,0x1f83d9abu,0x5be0cd19u};memcpy(c->h,h,sizeof(h));c->bits=0;c->used=0;}
static void sha_add(struct sha256_ctx *c,const uint8_t *p,size_t n){while(n){size_t x=64-c->used;if(x>n)x=n;memcpy(c->block+c->used,p,x);c->used+=x;p+=x;n-=x;c->bits+=(uint64_t)x*8u;if(c->used==64){sha_block(c,c->block);c->used=0;}}}
static void sha_done(struct sha256_ctx *c,uint8_t out[32]){uint64_t bits=c->bits;unsigned i;c->block[c->used++]=0x80;while(c->used!=56){if(c->used==64){sha_block(c,c->block);c->used=0;}c->block[c->used++]=0;}for(i=0;i<8;i++)c->block[63-i]=(uint8_t)(bits>>(8*i));sha_block(c,c->block);for(i=0;i<8;i++){out[4*i]=(uint8_t)(c->h[i]>>24);out[4*i+1]=(uint8_t)(c->h[i]>>16);out[4*i+2]=(uint8_t)(c->h[i]>>8);out[4*i+3]=(uint8_t)c->h[i];}}

int p360_fw_validate(const uint8_t *image,size_t bytes,struct p360_fw_view *view)
{
    static const uint8_t expected[32]={0xf6,0x86,0x94,0xb6,0x19,0x72,0x50,0x01,0x6a,0x9c,0x5f,0xfb,0x46,0xfa,0x8a,0xda,0xa5,0x99,0xa3,0x2d,0xb9,0x5a,0xa1,0x9a,0x0e,0xcf,0x5b,0xd4,0xed,0x1c,0x62,0xab};
    struct sha256_ctx c;uint8_t digest[32];
    if(!image||!view||bytes!=P360_FW_FILE_BYTES)return P360_L_IMAGE;
    if(memcmp(image,"XMan",4)!=0)return P360_L_IMAGE;
    sha_init(&c);sha_add(&c,image,bytes);sha_done(&c,digest);
    if(memcmp(digest,expected,sizeof(expected))!=0)return P360_L_IMAGE;
    view->payload=image+P360_FW_MANIFEST_BYTES;view->bytes=P360_FW_PAYLOAD_BYTES;return 0;
}
int p360_fw_ready_validate(const uint8_t *a,const uint8_t *b,size_t bytes)
{
    uint32_t sz;
    if(!a||!b||bytes!=P360_FW_READY_BYTES||memcmp(a,b,bytes)!=0)return P360_L_READY;
    sz=(uint32_t)a[0]|((uint32_t)a[1]<<8)|((uint32_t)a[2]<<16)|((uint32_t)a[3]<<24);
    if(sz!=P360_FW_READY_BYTES)return P360_L_READY;
    if((a[4]&0x7fu)!=0x07u)return P360_L_READY;
    return 0;
}
int p360_bdl_build(const struct p360_dma_span *spans,size_t count,uint64_t bdl_address,
    uint32_t payload_bytes,int dma64,uint8_t *bdl,size_t bdl_bytes,uint16_t *entries)
{
    size_t i;uint32_t total=0;uint16_t n=0;
    (void)bdl_address;
    if(!spans||!count||!payload_bytes||!bdl||!entries)return P360_L_ARGUMENT;
    if(bdl_bytes<P360_BDL_MAX*16u)return P360_L_ARGUMENT;
    memset(bdl,0,bdl_bytes);
    for(i=0;i<count&&total<payload_bytes;i++){
        uint32_t use=spans[i].bytes;
        uint64_t a=spans[i].address;
        if(!a||!use||n>=P360_BDL_MAX)return P360_L_IMAGE;
        if(!dma64 && (a>>32))return P360_L_IMAGE;
        if(use>payload_bytes-total)use=payload_bytes-total;
        bdl[n*16+0]=(uint8_t)a;bdl[n*16+1]=(uint8_t)(a>>8);bdl[n*16+2]=(uint8_t)(a>>16);bdl[n*16+3]=(uint8_t)(a>>24);
        bdl[n*16+4]=(uint8_t)(a>>32);bdl[n*16+5]=(uint8_t)(a>>40);bdl[n*16+6]=(uint8_t)(a>>48);bdl[n*16+7]=(uint8_t)(a>>56);
        bdl[n*16+8]=(uint8_t)use;bdl[n*16+9]=(uint8_t)(use>>8);bdl[n*16+10]=(uint8_t)(use>>16);bdl[n*16+11]=(uint8_t)(use>>24);
        total+=use;n++;
    }
    if(total!=payload_bytes||!n)return P360_L_IMAGE;
    bdl[(n-1)*16+12]=1;*entries=n;return 0;
}
