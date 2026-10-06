#include "../include/p360_firmware.h"

#define P360_FW_POOL_TAG ((ULONG)0x30363350u) /* P360 */

static VOID
p360_firmware_zero(
    _Out_ P360_FIRMWARE_BLOB *blob
    )
{
    if (blob)
        RtlZeroMemory(blob,sizeof(*blob));
}

VOID
p360_firmware_release(
    P360_FIRMWARE_BLOB *blob
    )
{
    if (!blob)
        return;

    if (blob->Data) {
        RtlSecureZeroMemory(blob->Data,blob->Bytes);
        ExFreePoolWithTag(blob->Data,P360_FW_POOL_TAG);
    }

    p360_firmware_zero(blob);
}

NTSTATUS
p360_firmware_load(
    P360_FIRMWARE_BLOB *blob
    )
{
    UNICODE_STRING path;
    OBJECT_ATTRIBUTES attributes;
    IO_STATUS_BLOCK iosb;
    FILE_STANDARD_INFORMATION standardInfo;
    LARGE_INTEGER offset;
    HANDLE handle = NULL;
    PUCHAR data = NULL;
    NTSTATUS status;
    struct p360_fw_view view;

    if (!blob || KeGetCurrentIrql() != PASSIVE_LEVEL)
        return STATUS_INVALID_PARAMETER;

    p360_firmware_zero(blob);

    RtlInitUnicodeString(
        &path,
        P360_FIRMWARE_NT_PATH);

    InitializeObjectAttributes(
        &attributes,
        &path,
        OBJ_CASE_INSENSITIVE | OBJ_KERNEL_HANDLE,
        NULL,
        NULL);

    status = ZwCreateFile(
        &handle,
        GENERIC_READ | SYNCHRONIZE,
        &attributes,
        &iosb,
        NULL,
        FILE_ATTRIBUTE_NORMAL,
        FILE_SHARE_READ,
        FILE_OPEN,
        FILE_NON_DIRECTORY_FILE |
            FILE_SYNCHRONOUS_IO_NONALERT,
        NULL,
        0);

    if (!NT_SUCCESS(status))
        return status;

    RtlZeroMemory(&standardInfo,sizeof(standardInfo));

    status = ZwQueryInformationFile(
        handle,
        &iosb,
        &standardInfo,
        sizeof(standardInfo),
        FileStandardInformation);

    if (!NT_SUCCESS(status))
        goto cleanup;

    if (standardInfo.Directory ||
        standardInfo.EndOfFile.QuadPart !=
            (LONGLONG)P360_FW_FILE_BYTES) {
        status = STATUS_INVALID_IMAGE_FORMAT;
        goto cleanup;
    }

    data = (PUCHAR)ExAllocatePool2(
        POOL_FLAG_NON_PAGED,
        P360_FW_FILE_BYTES,
        P360_FW_POOL_TAG);

    if (!data) {
        status = STATUS_INSUFFICIENT_RESOURCES;
        goto cleanup;
    }

    offset.QuadPart = 0;
    RtlZeroMemory(&iosb,sizeof(iosb));

    status = ZwReadFile(
        handle,
        NULL,
        NULL,
        NULL,
        &iosb,
        data,
        P360_FW_FILE_BYTES,
        &offset,
        NULL);

    if (!NT_SUCCESS(status))
        goto cleanup;

    if (iosb.Information != P360_FW_FILE_BYTES) {
        status = STATUS_END_OF_FILE;
        goto cleanup;
    }

    if (p360_fw_validate(
            data,
            P360_FW_FILE_BYTES,
            &view) != 0 ||
        view.payload !=
            data + P360_FW_MANIFEST_BYTES ||
        view.bytes != P360_FW_PAYLOAD_BYTES) {
        status = STATUS_INVALID_IMAGE_HASH;
        goto cleanup;
    }

    blob->Data = data;
    blob->Bytes = P360_FW_FILE_BYTES;
    data = NULL;
    status = STATUS_SUCCESS;

cleanup:
    if (data) {
        RtlSecureZeroMemory(data,P360_FW_FILE_BYTES);
        ExFreePoolWithTag(data,P360_FW_POOL_TAG);
    }

    if (handle)
        ZwClose(handle);

    return status;
}
