#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <mmsystem.h>
#include <mmreg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>
#include <math.h>

#pragma comment(lib,"winmm.lib")

#define P360_RATE 48000u
#define P360_CHANNELS 2u
#define P360_SECONDS 2u
#define P360_FRAMES (P360_RATE * P360_SECONDS)
#define P360_AMPLITUDE 10737418.0
#define P360_TONE_HZ 997.0

static const GUID P360_KSDATAFORMAT_SUBTYPE_PCM =
    {0x00000001,0x0000,0x0010,{0x80,0x00,0x00,0xaa,0x00,0x38,0x9b,0x71}};

static int contains_i(const wchar_t *s,const wchar_t *needle)
{
    size_t i,j,n,m;
    if (!s || !needle) return 0;
    n=wcslen(s); m=wcslen(needle);
    if (!m || m>n) return 0;
    for (i=0;i+m<=n;++i) {
        for (j=0;j<m;++j) {
            wchar_t a=s[i+j],b=needle[j];
            if (a>=L'A' && a<=L'Z') a=(wchar_t)(a-L'A'+L'a');
            if (b>=L'A' && b<=L'Z') b=(wchar_t)(b-L'A'+L'a');
            if (a!=b) break;
        }
        if (j==m) return 1;
    }
    return 0;
}

static int find_p360_waveout(UINT *id_out)
{
    UINT count=waveOutGetNumDevs();
    UINT i,found=WAVE_MAPPER;
    unsigned matches=0;

    wprintf(L"WAVEOUT_COUNT=%u\n",count);
    for (i=0;i<count;++i) {
        WAVEOUTCAPSW caps;
        MMRESULT r;
        ZeroMemory(&caps,sizeof(caps));
        r=waveOutGetDevCapsW(i,&caps,sizeof(caps));
        if (r!=MMSYSERR_NOERROR) continue;
        wprintf(L"WAVEOUT[%u]=%ls\n",i,caps.szPname);
        if (contains_i(caps.szPname,L"PHASER360")) {
            found=i;
            ++matches;
        }
    }

    if (matches!=1) {
        wprintf(L"PHASER360_WAVEOUT_MATCHES=%u\n",matches);
        return 0;
    }

    *id_out=found;
    wprintf(L"PHASER360_WAVEOUT_ID=%u\n",found);
    return 1;
}

static void init_format(WAVEFORMATEXTENSIBLE *f)
{
    ZeroMemory(f,sizeof(*f));
    f->Format.wFormatTag=WAVE_FORMAT_EXTENSIBLE;
    f->Format.nChannels=P360_CHANNELS;
    f->Format.nSamplesPerSec=P360_RATE;
    f->Format.wBitsPerSample=32;
    f->Format.nBlockAlign=(WORD)(P360_CHANNELS * 4u);
    f->Format.nAvgBytesPerSec=
        f->Format.nSamplesPerSec * f->Format.nBlockAlign;
    f->Format.cbSize=22;
    f->Samples.wValidBitsPerSample=16;
    f->dwChannelMask=SPEAKER_FRONT_LEFT|SPEAKER_FRONT_RIGHT;
    f->SubFormat=P360_KSDATAFORMAT_SUBTYPE_PCM;
}

int wmain(void)
{
    UINT device_id;
    WAVEFORMATEXTENSIBLE fmt;
    HWAVEOUT hwo=NULL;
    WAVEHDR hdr;
    int32_t *samples=NULL;
    DWORD bytes=P360_FRAMES * P360_CHANNELS * sizeof(int32_t);
    MMRESULT r;
    DWORD start;
    uint32_t frame;

    if (!find_p360_waveout(&device_id)) {
        wprintf(L"TEST=FAIL endpoint match is not unique\n");
        return 20;
    }

    init_format(&fmt);

    r=waveOutOpen(
        &hwo,
        device_id,
        (WAVEFORMATEX *)&fmt,
        0,
        0,
        CALLBACK_NULL);
    if (r!=MMSYSERR_NOERROR) {
        wprintf(L"TEST=FAIL waveOutOpen=%u\n",r);
        return 21;
    }

    samples=(int32_t *)VirtualAlloc(
        NULL,
        bytes,
        MEM_COMMIT|MEM_RESERVE,
        PAGE_READWRITE);
    if (!samples) {
        waveOutClose(hwo);
        wprintf(L"TEST=FAIL VirtualAlloc\n");
        return 22;
    }

    /*
     * WAVEFORMATEXTENSIBLE valid bits are left aligned in the 32-bit
     * container. 10737418 is 0.5% of signed 32-bit full-scale, equivalent
     * to about 164 counts at 16 valid bits. No sample can exceed this bound.
     */
    for (frame=0;frame<P360_FRAMES;++frame) {
        double phase=(2.0*3.14159265358979323846*P360_TONE_HZ*
                      (double)frame)/(double)P360_RATE;
        int32_t v=(int32_t)(sin(phase)*P360_AMPLITUDE);
        samples[frame*2u]=v;
        samples[frame*2u+1u]=v;
    }

    ZeroMemory(&hdr,sizeof(hdr));
    hdr.lpData=(LPSTR)samples;
    hdr.dwBufferLength=bytes;

    r=waveOutPrepareHeader(hwo,&hdr,sizeof(hdr));
    if (r!=MMSYSERR_NOERROR) {
        VirtualFree(samples,0,MEM_RELEASE);
        waveOutClose(hwo);
        wprintf(L"TEST=FAIL waveOutPrepareHeader=%u\n",r);
        return 23;
    }

    wprintf(L"FORMAT=48000Hz stereo 32-container 16-valid\n");
    wprintf(L"AMPLITUDE_Q31=10737418\n");
    wprintf(L"AMPLITUDE_PERCENT=0.5\n");
    wprintf(L"DURATION_MS=2000\n");
    wprintf(L"PLAY=BEGIN\n");

    r=waveOutWrite(hwo,&hdr,sizeof(hdr));
    if (r!=MMSYSERR_NOERROR) {
        waveOutUnprepareHeader(hwo,&hdr,sizeof(hdr));
        VirtualFree(samples,0,MEM_RELEASE);
        waveOutClose(hwo);
        wprintf(L"TEST=FAIL waveOutWrite=%u\n",r);
        return 24;
    }

    start=GetTickCount();
    while ((hdr.dwFlags & WHDR_DONE)==0) {
        if ((DWORD)(GetTickCount()-start)>3000u) {
            waveOutReset(hwo);
            waveOutUnprepareHeader(hwo,&hdr,sizeof(hdr));
            VirtualFree(samples,0,MEM_RELEASE);
            waveOutClose(hwo);
            wprintf(L"TEST=FAIL playback timeout\n");
            return 25;
        }
        Sleep(10);
    }

    wprintf(L"PLAY=COMPLETE\n");
    waveOutReset(hwo);
    waveOutUnprepareHeader(hwo,&hdr,sizeof(hdr));
    VirtualFree(samples,0,MEM_RELEASE);
    waveOutClose(hwo);

    wprintf(L"TEST=PASS\n");
    return 0;
}
