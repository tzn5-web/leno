#include "../include/p360_telemetry.h"

static const WCHAR g_p360_telem_path[] =
    L"\\Registry\\Machine\\SYSTEM\\CurrentControlSet\\Services\\P360SofAudio\\Parameters";

static NTSTATUS
p360_telemetry_open(_Out_ PHANDLE Key)
{
    UNICODE_STRING path;
    OBJECT_ATTRIBUTES attributes;
    ULONG disposition=0;

    if (!Key || KeGetCurrentIrql()!=PASSIVE_LEVEL)
        return STATUS_INVALID_DEVICE_STATE;

    *Key=NULL;
    RtlInitUnicodeString(&path,g_p360_telem_path);
    InitializeObjectAttributes(
        &attributes,
        &path,
        OBJ_KERNEL_HANDLE | OBJ_CASE_INSENSITIVE,
        NULL,
        NULL);

    return ZwCreateKey(
        Key,
        KEY_SET_VALUE,
        &attributes,
        0,
        NULL,
        REG_OPTION_NON_VOLATILE,
        &disposition);
}

static NTSTATUS
p360_telemetry_write_dword(
    _In_ PCWSTR Name,
    _In_ ULONG Value)
{
    HANDLE key=NULL;
    UNICODE_STRING name;
    NTSTATUS status;

    if (!Name)
        return STATUS_INVALID_PARAMETER;

    status=p360_telemetry_open(&key);
    if (!NT_SUCCESS(status))
        return status;

    RtlInitUnicodeString(&name,Name);
    status=ZwSetValueKey(
        key,
        &name,
        0,
        REG_DWORD,
        &Value,
        sizeof(Value));
    ZwClose(key);
    return status;
}

static NTSTATUS
p360_telemetry_write_qword(
    _In_ PCWSTR Name,
    _In_ ULONGLONG Value)
{
    HANDLE key=NULL;
    UNICODE_STRING name;
    NTSTATUS status;

    if (!Name)
        return STATUS_INVALID_PARAMETER;

    status=p360_telemetry_open(&key);
    if (!NT_SUCCESS(status))
        return status;

    RtlInitUnicodeString(&name,Name);
    status=ZwSetValueKey(
        key,
        &name,
        0,
        REG_QWORD,
        &Value,
        sizeof(Value));
    ZwClose(key);
    return status;
}

NTSTATUS
p360_telemetry_reset(_In_ ULONG BuildFlags)
{
    NTSTATUS status;

    status=p360_telemetry_write_dword(L"BuildFlags",BuildFlags);
    if (!NT_SUCCESS(status)) return status;
    status=p360_telemetry_write_dword(L"Stage",P360_TELEM_STAGE_RESET);
    if (!NT_SUCCESS(status)) return status;
    status=p360_telemetry_write_qword(L"BootEpoch",0);
    if (!NT_SUCCESS(status)) return status;
    status=p360_telemetry_write_dword(L"FirmwareError",0);
    if (!NT_SUCCESS(status)) return status;
    status=p360_telemetry_write_dword(L"ReplyBytes",0);
    if (!NT_SUCCESS(status)) return status;
    status=p360_telemetry_write_dword(L"FailureReason",0);
    if (!NT_SUCCESS(status)) return status;
    status=p360_telemetry_write_dword(L"LoaderPhase",0);
    if (!NT_SUCCESS(status)) return status;
    status=p360_telemetry_write_dword(L"LoaderError",0);
    if (!NT_SUCCESS(status)) return status;
    status=p360_telemetry_write_dword(L"LoaderCleanupError",0);
    if (!NT_SUCCESS(status)) return status;
    status=p360_telemetry_write_dword(L"EntryAdspcs",0);
    if (!NT_SUCCESS(status)) return status;
    status=p360_telemetry_write_dword(L"NormalizedAdspcs",0);
    if (!NT_SUCCESS(status)) return status;
    status=p360_telemetry_write_dword(L"FinalAdspcs",0);
    if (!NT_SUCCESS(status)) return status;
    status=p360_telemetry_write_dword(L"RomStatus",0);
    if (!NT_SUCCESS(status)) return status;
    status=p360_telemetry_write_dword(L"RomError",0);
    if (!NT_SUCCESS(status)) return status;
    status=p360_telemetry_write_dword(L"LastNtStatus",0);
    if (!NT_SUCCESS(status)) return status;
    status=p360_telemetry_write_dword(L"PrepareStep",P360_PREP_STEP_NONE);
    if (!NT_SUCCESS(status)) return status;
    status=p360_telemetry_write_dword(L"PrepareDetail",0);
    if (!NT_SUCCESS(status)) return status;
    return p360_telemetry_write_dword(L"PrepareNtStatus",0);
}

NTSTATUS
p360_telemetry_stage(_In_ ULONG Stage)
{
    return p360_telemetry_write_dword(L"Stage",Stage);
}

NTSTATUS
p360_telemetry_prepare(
    _In_ ULONG Step,
    _In_ ULONG Detail,
    _In_ NTSTATUS Status)
{
    NTSTATUS writeStatus;

    writeStatus=p360_telemetry_write_dword(L"PrepareStep",Step);
    if (!NT_SUCCESS(writeStatus))
        return writeStatus;
    writeStatus=p360_telemetry_write_dword(L"PrepareDetail",Detail);
    if (!NT_SUCCESS(writeStatus))
        return writeStatus;
    return p360_telemetry_write_dword(
        L"PrepareNtStatus",
        (ULONG)Status);
}

NTSTATUS
p360_telemetry_boot_epoch(_In_ ULONGLONG Epoch)
{
    return p360_telemetry_write_qword(L"BootEpoch",Epoch);
}

NTSTATUS
p360_telemetry_ipc(
    _In_ LONG FirmwareError,
    _In_ ULONG ReplyBytes)
{
    NTSTATUS status;

    status=p360_telemetry_write_dword(
        L"FirmwareError",
        (ULONG)FirmwareError);
    if (!NT_SUCCESS(status))
        return status;

    return p360_telemetry_write_dword(
        L"ReplyBytes",
        ReplyBytes);
}

NTSTATUS
p360_telemetry_result(
    _In_ ULONG FailureReason,
    _In_ NTSTATUS Status)
{
    NTSTATUS writeStatus;

    writeStatus=p360_telemetry_write_dword(
        L"FailureReason",
        FailureReason);
    if (!NT_SUCCESS(writeStatus))
        return writeStatus;

    return p360_telemetry_write_dword(
        L"LastNtStatus",
        (ULONG)Status);
}


NTSTATUS
p360_telemetry_loader(
    ULONG Phase,
    LONG LoaderError,
    LONG CleanupError,
    ULONG EntryAdspcs,
    ULONG NormalizedAdspcs,
    ULONG FinalAdspcs,
    ULONG RomStatus,
    ULONG RomError)
{
    NTSTATUS status;

#define P360_WRITE_LOADER_DWORD(_name,_value)                     \
    do {                                                           \
        status=p360_telemetry_write_dword((_name),(ULONG)(_value));\
        if (!NT_SUCCESS(status))                                   \
            return status;                                         \
    } while (0)

    P360_WRITE_LOADER_DWORD(L"LoaderPhase",Phase);
    P360_WRITE_LOADER_DWORD(L"LoaderError",LoaderError);
    P360_WRITE_LOADER_DWORD(L"LoaderCleanupError",CleanupError);
    P360_WRITE_LOADER_DWORD(L"EntryAdspcs",EntryAdspcs);
    P360_WRITE_LOADER_DWORD(L"NormalizedAdspcs",NormalizedAdspcs);
    P360_WRITE_LOADER_DWORD(L"FinalAdspcs",FinalAdspcs);
    P360_WRITE_LOADER_DWORD(L"RomStatus",RomStatus);
    P360_WRITE_LOADER_DWORD(L"RomError",RomError);

#undef P360_WRITE_LOADER_DWORD
    return STATUS_SUCCESS;
}
