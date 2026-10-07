#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <newdev.h>
#include <stdio.h>

#pragma comment(lib,"newdev.lib")

static int force_one(const wchar_t *inf,const wchar_t *hwid,BOOL *rebootAny)
{
    BOOL reboot=FALSE;
    SetLastError(ERROR_SUCCESS);

    if (!UpdateDriverForPlugAndPlayDevicesW(
            NULL,
            hwid,
            inf,
            INSTALLFLAG_FORCE,
            &reboot)) {
        DWORD err=GetLastError();
        wprintf(L"FORCE_BIND=FAIL HWID=%ls ERROR=%lu\n",hwid,(unsigned long)err);
        return (int)(err ? err : ERROR_GEN_FAILURE);
    }

    if (reboot) *rebootAny=TRUE;
    wprintf(L"FORCE_BIND=PASS HWID=%ls REBOOT=%ls\n",
            hwid,reboot ? L"YES" : L"NO");
    return 0;
}

int wmain(int argc,wchar_t **argv)
{
    wchar_t fullInf[MAX_PATH];
    DWORD n;
    BOOL rebootAny=FALSE;
    int rc;

    if (argc!=4) {
        wprintf(L"USAGE=P360_FORCE_INSTALL.exe <full-inf-path> <adsp-hwid> <amp-hwid>\n");
        return 64;
    }

    n=GetFullPathNameW(argv[1],MAX_PATH,fullInf,NULL);
    if (!n || n>=MAX_PATH) {
        wprintf(L"INF_PATH=FAIL ERROR=%lu\n",(unsigned long)GetLastError());
        return 65;
    }

    rc=force_one(fullInf,argv[2],&rebootAny);
    if (rc) return rc;

    rc=force_one(fullInf,argv[3],&rebootAny);
    if (rc) return rc;

    wprintf(L"FULL_DRIVER_BIND=PASS\n");
    wprintf(L"REBOOT_REQUIRED=%ls\n",rebootAny ? L"YES" : L"NO");
    return rebootAny ? 3010 : 0;
}
