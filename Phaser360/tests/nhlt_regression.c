#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "../include/p360_nhlt.h"

static void put16(uint8_t *p,uint16_t v)
{
    p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);
}
static void put32(uint8_t *p,uint32_t v)
{
    p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);
    p[2]=(uint8_t)(v>>16);p[3]=(uint8_t)(v>>24);
}

static size_t endpoint(
    uint8_t *p,
    uint8_t link,
    uint16_t device,
    uint8_t type,
    uint8_t dir,
    uint8_t vbus,
    uint16_t channels,
    uint32_t rate,
    uint16_t bits,
    uint16_t valid)
{
    const uint32_t n=68;
    memset(p,0,n);
    put32(p,n);
    p[4]=link;
    p[5]=0;
    put16(p+6,0x8086);
    put16(p+8,device);
    put16(p+10,1);
    put32(p+12,1);
    p[16]=type;
    p[17]=dir;
    p[18]=vbus;
    put32(p+19,0); /* device-specific capabilities */
    p[23]=1;       /* format count */

    put16(p+24,0xfffe);
    put16(p+26,channels);
    put32(p+28,rate);
    put16(p+38,bits);
    put16(p+40,22);
    put16(p+42,valid);
    put32(p+64,0); /* format-specific capabilities */
    return n;
}

static size_t fixture(uint8_t *b,size_t cap)
{
    size_t off=37;
    unsigned i;
    uint8_t sum=0;

    assert(cap>=313);
    memset(b,0,cap);
    memcpy(b,"NHLT",4);
    b[8]=1;
    b[36]=4;

    off+=endpoint(b+off,2,0xae20,0,1,0,2,48000,16,16);
    off+=endpoint(b+off,3,0xae34,4,0,2,2,48000,32,24);
    off+=endpoint(b+off,3,0xae34,4,1,2,2,48000,32,24);
    off+=endpoint(b+off,3,0xae34,4,0,1,2,48000,32,24);

    put32(b+off,0);
    off+=4;
    put32(b+4,(uint32_t)off);

    for(i=0;i<off;i++)
        sum=(uint8_t)(sum+b[i]);
    b[9]=(uint8_t)(0u-sum);
    return off;
}

int main(void)
{
    uint8_t b[512];
    P360_NHLT_FACTS f;
    size_t n=fixture(b,sizeof(b));

    assert(p360_nhlt_parse(b,n,&f));
    assert(f.checksum_ok && f.ssp1_render && f.ssp2_render &&
           f.ssp2_capture && f.dmic_capture);

    b[37+17]=0;
    assert(!p360_nhlt_parse(b,n,&f));
    b[37+17]=1;

    /* Rebuild checksum after restoring and then break SSP1's rate. */
    n=fixture(b,sizeof(b));
    put32(b+37+68*3+28,44100);
    {
        unsigned i;uint8_t sum=0;
        b[9]=0;
        for(i=0;i<n;i++)sum=(uint8_t)(sum+b[i]);
        b[9]=(uint8_t)(0u-sum);
    }
    assert(!p360_nhlt_parse(b,n,&f));

    n=fixture(b,sizeof(b));
    b[100]^=1;
    assert(!p360_nhlt_parse(b,n,&f));

    puts("Phaser360 NHLT regression: PASS");
    return 0;
}
