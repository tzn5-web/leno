#include "../include/p360_nhlt.h"
#include <string.h>

#define P360_ACPI_HEADER_BYTES 36u
#define P360_NHLT_FIRST_ENDPOINT 37u
#define P360_NHLT_ENDPOINT_FIXED 19u
#define P360_NHLT_CFG_HEADER 4u
#define P360_NHLT_WAVE_EXT_BYTES 40u
#define P360_NHLT_FORMAT_CFG_HEADER 4u

#define P360_NHLT_LINK_PDM 2u
#define P360_NHLT_LINK_SSP 3u
#define P360_NHLT_DIR_RENDER 0u
#define P360_NHLT_DIR_CAPTURE 1u
#define P360_NHLT_DEVICE_CODEC 4u
#define P360_NHLT_DEVICEID_DMIC 0xae20u
#define P360_NHLT_DEVICEID_I2S 0xae34u
#define P360_NHLT_VENDOR_INTEL 0x8086u

static uint16_t p360_le16(const uint8_t *p)
{
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

static uint32_t p360_le32(const uint8_t *p)
{
    return (uint32_t)p[0] |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static int p360_span(size_t offset,size_t need,size_t limit)
{
    return offset <= limit && need <= limit - offset;
}

static int p360_checksum_ok(const uint8_t *p,size_t bytes)
{
    uint8_t sum=0;
    size_t i;
    for(i=0;i<bytes;i++)
        sum=(uint8_t)(sum+p[i]);
    return sum==0;
}

static int p360_endpoint_has_format(
    const uint8_t *ep,
    size_t ep_bytes,
    uint16_t channels,
    uint32_t rate,
    uint16_t container_bits,
    uint16_t valid_bits)
{
    size_t off;
    uint32_t cfg_size;
    uint8_t count;
    unsigned i;

    if (!ep || ep_bytes < P360_NHLT_ENDPOINT_FIXED + P360_NHLT_CFG_HEADER)
        return 0;

    cfg_size=p360_le32(ep+P360_NHLT_ENDPOINT_FIXED);
    off=P360_NHLT_ENDPOINT_FIXED+P360_NHLT_CFG_HEADER;

    if (!p360_span(off,cfg_size,ep_bytes))
        return 0;
    off+=cfg_size;

    if (!p360_span(off,1,ep_bytes))
        return 0;
    count=ep[off++];

    if (count==0 || count>32)
        return 0;

    for(i=0;i<count;i++) {
        const uint8_t *w;
        uint32_t specific;

        if (!p360_span(off,P360_NHLT_WAVE_EXT_BYTES+
                           P360_NHLT_FORMAT_CFG_HEADER,ep_bytes))
            return 0;

        w=ep+off;

        /*
         * NHLT uses WAVEFORMATEXTENSIBLE:
         * channels@2, samples/sec@4, container bits@14, valid bits@18.
         */
        specific=p360_le32(w+P360_NHLT_WAVE_EXT_BYTES);

        if (p360_le16(w+2)==channels &&
            p360_le32(w+4)==rate &&
            p360_le16(w+14)==container_bits &&
            p360_le16(w+18)==valid_bits)
            return 1;

        off+=P360_NHLT_WAVE_EXT_BYTES+P360_NHLT_FORMAT_CFG_HEADER;
        if (!p360_span(off,specific,ep_bytes))
            return 0;
        off+=specific;
    }

    return 0;
}

int p360_nhlt_parse(
    const void *table,
    size_t bytes,
    P360_NHLT_FACTS *facts)
{
    const uint8_t *p=(const uint8_t *)table;
    uint32_t table_bytes;
    uint8_t endpoints;
    size_t off;
    unsigned i;
    P360_NHLT_FACTS out;

    if (!facts)
        return 0;
    memset(&out,0,sizeof(out));

    if (!p || bytes < P360_NHLT_FIRST_ENDPOINT || bytes > 0x10000u)
        return 0;

    if (memcmp(p,"NHLT",4)!=0)
        return 0;

    table_bytes=p360_le32(p+4);
    if (table_bytes < P360_NHLT_FIRST_ENDPOINT ||
        table_bytes > bytes ||
        table_bytes > 0x10000u)
        return 0;

    if (!p360_checksum_ok(p,table_bytes))
        return 0;

    endpoints=p[36];
    if (endpoints==0 || endpoints>16)
        return 0;

    out.table_length=table_bytes;
    out.checksum_ok=1;
    off=P360_NHLT_FIRST_ENDPOINT;

    for(i=0;i<endpoints;i++) {
        const uint8_t *ep;
        uint32_t ep_bytes;
        uint8_t link;
        uint8_t type;
        uint8_t dir;
        uint8_t vbus;
        uint16_t vendor;
        uint16_t device;

        if (!p360_span(off,P360_NHLT_ENDPOINT_FIXED+
                           P360_NHLT_CFG_HEADER,table_bytes))
            return 0;

        ep=p+off;
        ep_bytes=p360_le32(ep);

        if (ep_bytes < P360_NHLT_ENDPOINT_FIXED+
                       P360_NHLT_CFG_HEADER+1u ||
            !p360_span(off,ep_bytes,table_bytes))
            return 0;

        link=ep[4];
        vendor=p360_le16(ep+6);
        device=p360_le16(ep+8);
        type=ep[16];
        dir=ep[17];
        vbus=ep[18];

        if (vendor==P360_NHLT_VENDOR_INTEL &&
            device==P360_NHLT_DEVICEID_DMIC &&
            link==P360_NHLT_LINK_PDM &&
            dir==P360_NHLT_DIR_CAPTURE &&
            vbus==0 &&
            p360_endpoint_has_format(
                ep,ep_bytes,2,48000,16,16)) {
            if (out.dmic_capture)
                return 0;
            out.dmic_capture=1;
        }

        if (vendor==P360_NHLT_VENDOR_INTEL &&
            device==P360_NHLT_DEVICEID_I2S &&
            link==P360_NHLT_LINK_SSP &&
            type==P360_NHLT_DEVICE_CODEC &&
            dir==P360_NHLT_DIR_RENDER &&
            vbus==1 &&
            p360_endpoint_has_format(
                ep,ep_bytes,2,48000,32,24)) {
            if (out.ssp1_render)
                return 0;
            out.ssp1_render=1;
        }

        if (vendor==P360_NHLT_VENDOR_INTEL &&
            device==P360_NHLT_DEVICEID_I2S &&
            link==P360_NHLT_LINK_SSP &&
            type==P360_NHLT_DEVICE_CODEC &&
            vbus==2 &&
            p360_endpoint_has_format(
                ep,ep_bytes,2,48000,32,24)) {
            if (dir==P360_NHLT_DIR_RENDER) {
                if (out.ssp2_render)
                    return 0;
                out.ssp2_render=1;
            } else if (dir==P360_NHLT_DIR_CAPTURE) {
                if (out.ssp2_capture)
                    return 0;
                out.ssp2_capture=1;
            }
        }

        off+=ep_bytes;
    }

    /*
     * Optional OED config may follow endpoint descriptors. Its first dword is
     * a capabilities-size field. Validate the residual structurally without
     * interpreting it.
     */
    if (off < table_bytes) {
        uint32_t oed_bytes;
        if (!p360_span(off,4,table_bytes))
            return 0;
        oed_bytes=p360_le32(p+off);
        if (!p360_span(off+4u,oed_bytes,table_bytes))
            return 0;
        if (off+4u+oed_bytes != table_bytes)
            return 0;
    }

    if (!p360_board_validate_nhlt(&out))
        return 0;

    *facts=out;
    return 1;
}
