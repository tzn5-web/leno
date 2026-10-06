#pragma once

#include <ntddk.h>
#include "../sof_core/loader/p360_loader.h"

#define P360_FIRMWARE_NT_PATH \
    L"\\SystemRoot\\System32\\drivers\\P360\\p360-f686.ri"

typedef struct P360_FIRMWARE_BLOB {
    PUCHAR Data;
    SIZE_T Bytes;
} P360_FIRMWARE_BLOB;

NTSTATUS
p360_firmware_load(
    _Out_ P360_FIRMWARE_BLOB *Blob
    );

VOID
p360_firmware_release(
    _Inout_ P360_FIRMWARE_BLOB *Blob
    );
