#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <functiondiscoverykeys_devpkey.h>
#include <ks.h>
#include <ksmedia.h>
#include <propvarutil.h>
#include <stdint.h>
#include <stdio.h>
#include <wchar.h>
#include <math.h>

#pragma comment(lib,"ole32.lib")
#pragma comment(lib,"uuid.lib")
#pragma comment(lib,"propsys.lib")

#define P360_RATE 48000u
#define P360_CHANNELS 2u
#define P360_CONTAINER_BITS 32u
#define P360_VALID_BITS 16u
#define P360_DURATION_MS 2000u
#define P360_TONE_HZ 997.0
#define P360_Q16_PEAK 163

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

static void init_expected(WAVEFORMATEXTENSIBLE *f)
{
    ZeroMemory(f,sizeof(*f));
    f->Format.wFormatTag=WAVE_FORMAT_EXTENSIBLE;
    f->Format.nChannels=P360_CHANNELS;
    f->Format.nSamplesPerSec=P360_RATE;
    f->Format.wBitsPerSample=P360_CONTAINER_BITS;
    f->Format.nBlockAlign=(WORD)(P360_CHANNELS*(P360_CONTAINER_BITS/8u));
    f->Format.nAvgBytesPerSec=f->Format.nSamplesPerSec*f->Format.nBlockAlign;
    f->Format.cbSize=sizeof(WAVEFORMATEXTENSIBLE)-sizeof(WAVEFORMATEX);
    f->Samples.wValidBitsPerSample=P360_VALID_BITS;
    f->dwChannelMask=SPEAKER_FRONT_LEFT|SPEAKER_FRONT_RIGHT;
    f->SubFormat=KSDATAFORMAT_SUBTYPE_PCM;
}

static int exact_expected(const WAVEFORMATEX *w)
{
    const WAVEFORMATEXTENSIBLE *e;
    if (!w || w->wFormatTag!=WAVE_FORMAT_EXTENSIBLE ||
        w->cbSize<sizeof(WAVEFORMATEXTENSIBLE)-sizeof(WAVEFORMATEX) ||
        w->nChannels!=P360_CHANNELS ||
        w->nSamplesPerSec!=P360_RATE ||
        w->wBitsPerSample!=P360_CONTAINER_BITS ||
        w->nBlockAlign!=P360_CHANNELS*(P360_CONTAINER_BITS/8u) ||
        w->nAvgBytesPerSec!=P360_RATE*P360_CHANNELS*(P360_CONTAINER_BITS/8u)) {
        return 0;
    }
    e=(const WAVEFORMATEXTENSIBLE *)w;
    return e->Samples.wValidBitsPerSample==P360_VALID_BITS &&
           e->dwChannelMask==(SPEAKER_FRONT_LEFT|SPEAKER_FRONT_RIGHT) &&
           IsEqualGUID(e->SubFormat,KSDATAFORMAT_SUBTYPE_PCM);
}

static void print_format(const wchar_t *prefix,const WAVEFORMATEX *w)
{
    if (!w) {
        wprintf(L"%ls=<null>\n",prefix);
        return;
    }
    wprintf(L"%ls_TAG=0x%04X\n",prefix,w->wFormatTag);
    wprintf(L"%ls_RATE=%lu\n",prefix,w->nSamplesPerSec);
    wprintf(L"%ls_CHANNELS=%u\n",prefix,w->nChannels);
    wprintf(L"%ls_BITS=%u\n",prefix,w->wBitsPerSample);
    if (w->wFormatTag==WAVE_FORMAT_EXTENSIBLE &&
        w->cbSize>=sizeof(WAVEFORMATEXTENSIBLE)-sizeof(WAVEFORMATEX)) {
        const WAVEFORMATEXTENSIBLE *e=(const WAVEFORMATEXTENSIBLE *)w;
        wprintf(L"%ls_VALID_BITS=%u\n",prefix,e->Samples.wValidBitsPerSample);
        wprintf(L"%ls_CHANNEL_MASK=0x%08lX\n",prefix,e->dwChannelMask);
    }
}

static HRESULT find_endpoint(IMMDevice **out)
{
    IMMDeviceEnumerator *enumerator=NULL;
    IMMDeviceCollection *collection=NULL;
    IMMDevice *selected=NULL;
    HRESULT hr;
    UINT count=0,matches=0;

    if (!out) return E_POINTER;
    *out=NULL;

    hr=CoCreateInstance(__uuidof(MMDeviceEnumerator),NULL,CLSCTX_ALL,
                        __uuidof(IMMDeviceEnumerator),(void **)&enumerator);
    if (FAILED(hr)) goto done;

    hr=enumerator->EnumAudioEndpoints(eRender,DEVICE_STATE_ACTIVE,&collection);
    if (FAILED(hr)) goto done;

    hr=collection->GetCount(&count);
    if (FAILED(hr)) goto done;

    wprintf(L"WASAPI_RENDER_ENDPOINTS=%u\n",count);
    for (UINT i=0;i<count;++i) {
        IMMDevice *device=NULL;
        IPropertyStore *store=NULL;
        PROPVARIANT name;
        PropVariantInit(&name);

        if (FAILED(collection->Item(i,&device))) continue;
        if (SUCCEEDED(device->OpenPropertyStore(STGM_READ,&store)) &&
            SUCCEEDED(store->GetValue(PKEY_Device_FriendlyName,&name)) &&
            name.vt==VT_LPWSTR && name.pwszVal) {
            wprintf(L"WASAPI_ENDPOINT[%u]=%ls\n",i,name.pwszVal);
            if (contains_i(name.pwszVal,L"PHASER360")) {
                ++matches;
                if (!selected) {
                    selected=device;
                    selected->AddRef();
                }
            }
        }

        PropVariantClear(&name);
        if (store) store->Release();
        device->Release();
    }

    wprintf(L"PHASER360_WASAPI_MATCHES=%u\n",matches);
    if (matches!=1 || !selected) {
        hr=HRESULT_FROM_WIN32(ERROR_NOT_FOUND);
        goto done;
    }

    {
        LPWSTR id=NULL;
        if (SUCCEEDED(selected->GetId(&id)) && id) {
            wprintf(L"PHASER360_ENDPOINT_ID=%ls\n",id);
            CoTaskMemFree(id);
        }
    }

    *out=selected;
    selected=NULL;
    hr=S_OK;

done:
    if (selected) selected->Release();
    if (collection) collection->Release();
    if (enumerator) enumerator->Release();
    return hr;
}

static void fill_tone(BYTE *data,UINT32 frames,uint64_t *frameCursor)
{
    int32_t *samples=(int32_t *)data;
    uint64_t cursor=*frameCursor;
    for (UINT32 i=0;i<frames;++i,++cursor) {
        double phase=(2.0*3.14159265358979323846*P360_TONE_HZ*(double)cursor)/
                     (double)P360_RATE;
        int32_t q16=(int32_t)(sin(phase)*(double)P360_Q16_PEAK);
        int32_t sample=q16*65536;
        samples[i*2u]=sample;
        samples[i*2u+1u]=sample;
    }
    *frameCursor=cursor;
}

int wmain(int argc,wchar_t **argv)
{
    int preflight=0;
    HRESULT hr;
    HRESULT cohr;
    IMMDevice *endpoint=NULL;
    IAudioClient *client=NULL;
    IAudioRenderClient *render=NULL;
    IAudioClock *clock=NULL;
    WAVEFORMATEX *mix=NULL;
    WAVEFORMATEX *closest=NULL;
    WAVEFORMATEXTENSIBLE expected;
    UINT32 bufferFrames=0;
    UINT64 clockFreq=0,clockBefore=0,clockAfter=0,qpc=0;
    uint64_t frameCursor=0;
    DWORD startTick;
    int rc=1;

    if (argc==2 && wcscmp(argv[1],L"--preflight")==0) {
        preflight=1;
    } else if (argc!=1) {
        wprintf(L"WASAPI_TEST=FAIL reason=invalid_arguments\n");
        return 40;
    }

    cohr=CoInitializeEx(NULL,COINIT_MULTITHREADED);
    if (FAILED(cohr) && cohr!=RPC_E_CHANGED_MODE) {
        wprintf(L"WASAPI_TEST=FAIL stage=CoInitialize hr=0x%08lX\n",(unsigned long)cohr);
        return 41;
    }

    hr=find_endpoint(&endpoint);
    if (FAILED(hr)) {
        wprintf(L"WASAPI_TEST=FAIL stage=FindEndpoint hr=0x%08lX\n",(unsigned long)hr);
        rc=42;
        goto done;
    }

    hr=endpoint->Activate(__uuidof(IAudioClient),CLSCTX_ALL,NULL,(void **)&client);
    if (FAILED(hr)) {
        wprintf(L"WASAPI_TEST=FAIL stage=ActivateIAudioClient hr=0x%08lX\n",(unsigned long)hr);
        rc=43;
        goto done;
    }

    hr=client->GetMixFormat(&mix);
    if (FAILED(hr) || !mix) {
        wprintf(L"WASAPI_TEST=FAIL stage=GetMixFormat hr=0x%08lX\n",(unsigned long)hr);
        rc=44;
        goto done;
    }

    print_format(L"MIX",mix);
    wprintf(L"MIX_EXACT_P360=%ls\n",exact_expected(mix)?L"YES":L"NO");
    if (!exact_expected(mix)) {
        wprintf(L"WASAPI_TEST=FAIL stage=MixFormat expected=48000_stereo_s32container_s16valid\n");
        rc=61;
        goto done;
    }

    init_expected(&expected);
    hr=client->IsFormatSupported(AUDCLNT_SHAREMODE_SHARED,
                                  (WAVEFORMATEX *)&expected,
                                  &closest);
    wprintf(L"EXPECTED_SHARED_FORMAT_SUPPORTED_HR=0x%08lX\n",(unsigned long)hr);
    if (closest) {
        print_format(L"CLOSEST",closest);
        CoTaskMemFree(closest);
        closest=NULL;
    }
    if (hr!=S_OK) {
        wprintf(L"WASAPI_TEST=FAIL stage=IsFormatSupported expected=48000_stereo_s32container_s16valid\n");
        rc=45;
        goto done;
    }

    hr=client->Initialize(AUDCLNT_SHAREMODE_SHARED,
                          AUDCLNT_STREAMFLAGS_NOPERSIST,
                          1000000,
                          0,
                          (WAVEFORMATEX *)&expected,
                          NULL);
    if (FAILED(hr)) {
        wprintf(L"WASAPI_TEST=FAIL stage=InitializeShared hr=0x%08lX\n",(unsigned long)hr);
        rc=46;
        goto done;
    }

    hr=client->GetBufferSize(&bufferFrames);
    if (FAILED(hr) || !bufferFrames) {
        wprintf(L"WASAPI_TEST=FAIL stage=GetBufferSize hr=0x%08lX frames=%u\n",
                (unsigned long)hr,bufferFrames);
        rc=47;
        goto done;
    }

    wprintf(L"WASAPI_SHARED_INITIALIZE=PASS\n");
    wprintf(L"WASAPI_SHARED_BUFFER_FRAMES=%u\n",bufferFrames);

    if (preflight) {
        wprintf(L"WASAPI_SHARED_PREFLIGHT=PASS\n");
        wprintf(L"WASAPI_TEST=PASS\n");
        rc=0;
        goto done;
    }

    hr=client->GetService(__uuidof(IAudioRenderClient),(void **)&render);
    if (FAILED(hr)) {
        wprintf(L"WASAPI_TEST=FAIL stage=GetRenderClient hr=0x%08lX\n",(unsigned long)hr);
        rc=48;
        goto done;
    }

    hr=client->GetService(__uuidof(IAudioClock),(void **)&clock);
    if (FAILED(hr)) {
        wprintf(L"WASAPI_TEST=FAIL stage=GetAudioClock hr=0x%08lX\n",(unsigned long)hr);
        rc=49;
        goto done;
    }

    hr=clock->GetFrequency(&clockFreq);
    if (FAILED(hr) || !clockFreq) {
        wprintf(L"WASAPI_TEST=FAIL stage=ClockFrequency hr=0x%08lX\n",(unsigned long)hr);
        rc=50;
        goto done;
    }

    {
        BYTE *data=NULL;
        hr=render->GetBuffer(bufferFrames,&data);
        if (FAILED(hr)) {
            wprintf(L"WASAPI_TEST=FAIL stage=PrimeGetBuffer hr=0x%08lX\n",(unsigned long)hr);
            rc=51;
            goto done;
        }
        fill_tone(data,bufferFrames,&frameCursor);
        hr=render->ReleaseBuffer(bufferFrames,0);
        if (FAILED(hr)) {
            wprintf(L"WASAPI_TEST=FAIL stage=PrimeReleaseBuffer hr=0x%08lX\n",(unsigned long)hr);
            rc=52;
            goto done;
        }
    }

    (void)clock->GetPosition(&clockBefore,&qpc);

    wprintf(L"WASAPI_SHARED_PLAY=BEGIN\n");
    wprintf(L"FORMAT=48000Hz stereo 32-container 16-valid\n");
    wprintf(L"TONE_HZ=997\n");
    wprintf(L"AMPLITUDE_PERCENT_LT=0.5\n");
    wprintf(L"DURATION_MS=2000\n");

    hr=client->Start();
    if (FAILED(hr)) {
        wprintf(L"WASAPI_TEST=FAIL stage=Start hr=0x%08lX\n",(unsigned long)hr);
        rc=53;
        goto done;
    }

    startTick=GetTickCount();
    while ((DWORD)(GetTickCount()-startTick)<P360_DURATION_MS) {
        UINT32 padding=0,available=0;
        Sleep(5);
        hr=client->GetCurrentPadding(&padding);
        if (FAILED(hr)) {
            wprintf(L"WASAPI_TEST=FAIL stage=GetCurrentPadding hr=0x%08lX\n",(unsigned long)hr);
            (void)client->Stop();
            rc=54;
            goto done;
        }
        if (padding>bufferFrames) {
            wprintf(L"WASAPI_TEST=FAIL stage=PaddingRange padding=%u buffer=%u\n",padding,bufferFrames);
            (void)client->Stop();
            rc=55;
            goto done;
        }
        available=bufferFrames-padding;
        if (available) {
            BYTE *data=NULL;
            hr=render->GetBuffer(available,&data);
            if (FAILED(hr)) {
                wprintf(L"WASAPI_TEST=FAIL stage=RenderGetBuffer hr=0x%08lX\n",(unsigned long)hr);
                (void)client->Stop();
                rc=56;
                goto done;
            }
            fill_tone(data,available,&frameCursor);
            hr=render->ReleaseBuffer(available,0);
            if (FAILED(hr)) {
                wprintf(L"WASAPI_TEST=FAIL stage=RenderReleaseBuffer hr=0x%08lX\n",(unsigned long)hr);
                (void)client->Stop();
                rc=57;
                goto done;
            }
        }
    }

    Sleep(30);
    hr=clock->GetPosition(&clockAfter,&qpc);
    if (FAILED(hr)) {
        wprintf(L"WASAPI_TEST=FAIL stage=ClockAfter hr=0x%08lX\n",(unsigned long)hr);
        (void)client->Stop();
        rc=58;
        goto done;
    }

    hr=client->Stop();
    if (FAILED(hr)) {
        wprintf(L"WASAPI_TEST=FAIL stage=Stop hr=0x%08lX\n",(unsigned long)hr);
        rc=59;
        goto done;
    }

    wprintf(L"AUDIO_CLOCK_FREQUENCY=%llu\n",(unsigned long long)clockFreq);
    wprintf(L"AUDIO_CLOCK_BEFORE=%llu\n",(unsigned long long)clockBefore);
    wprintf(L"AUDIO_CLOCK_AFTER=%llu\n",(unsigned long long)clockAfter);
    if (clockAfter<=clockBefore) {
        wprintf(L"WASAPI_TEST=FAIL stage=ClockAdvance\n");
        rc=60;
        goto done;
    }

    wprintf(L"AUDIO_ENGINE_CLOCK_ADVANCED=YES\n");
    wprintf(L"WASAPI_SHARED_PLAYBACK=PASS\n");
    wprintf(L"WASAPI_TEST=PASS\n");
    rc=0;

done:
    if (client) (void)client->Stop();
    if (clock) clock->Release();
    if (render) render->Release();
    if (mix) CoTaskMemFree(mix);
    if (closest) CoTaskMemFree(closest);
    if (client) client->Release();
    if (endpoint) endpoint->Release();
    if (SUCCEEDED(cohr)) CoUninitialize();
    return rc;
}
