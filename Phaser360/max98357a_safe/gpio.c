/*
 * Derived from CoolStar/max98357a gpio.c (Apache-2.0).
 */
#include "gpio.h"
#include <gpio.h>
#include <reshub.h>

NTSTATUS
p360_max_gpio_write(
    P360_MAX_GPIO_CONTEXT *Gpio,
    UCHAR Value)
{
    WDF_MEMORY_DESCRIPTOR input;
    WDF_MEMORY_DESCRIPTOR output;
    NTSTATUS status;

    if (!Gpio || !Gpio->Target || !Gpio->Lock)
        return STATUS_INVALID_DEVICE_STATE;

    WdfWaitLockAcquire(Gpio->Lock,NULL);
    WDF_MEMORY_DESCRIPTOR_INIT_BUFFER(&input,&Value,sizeof(Value));
    WDF_MEMORY_DESCRIPTOR_INIT_BUFFER(&output,&Value,sizeof(Value));

    status=WdfIoTargetSendIoctlSynchronously(
        Gpio->Target,
        NULL,
        IOCTL_GPIO_WRITE_PINS,
        &input,
        &output,
        NULL,
        NULL);

    WdfWaitLockRelease(Gpio->Lock);
    return status;
}

VOID
p360_max_gpio_deinit(
    WDFDEVICE Device,
    P360_MAX_GPIO_CONTEXT *Gpio)
{
    UNREFERENCED_PARAMETER(Device);

    if (!Gpio)
        return;

    if (Gpio->Lock) {
        WdfObjectDelete(Gpio->Lock);
        Gpio->Lock=NULL;
    }

    if (Gpio->Target) {
        WdfIoTargetClose(Gpio->Target);
        WdfObjectDelete(Gpio->Target);
        Gpio->Target=NULL;
    }

    RtlZeroMemory(&Gpio->ResourceHubId,sizeof(Gpio->ResourceHubId));
}

NTSTATUS
p360_max_gpio_init(
    WDFDEVICE Device,
    P360_MAX_GPIO_CONTEXT *Gpio)
{
    WDF_OBJECT_ATTRIBUTES attributes;
    WDF_IO_TARGET_OPEN_PARAMS openParams;
    UNICODE_STRING gpioName;
    WCHAR gpioNameBuffer[RESOURCE_HUB_PATH_SIZE];
    NTSTATUS status;

    if (!Device || !Gpio)
        return STATUS_INVALID_PARAMETER;

    WDF_OBJECT_ATTRIBUTES_INIT(&attributes);
    attributes.ParentObject=Device;

    status=WdfIoTargetCreate(
        Device,
        &attributes,
        &Gpio->Target);
    if (!NT_SUCCESS(status))
        goto fail;

    RtlInitEmptyUnicodeString(
        &gpioName,
        gpioNameBuffer,
        sizeof(gpioNameBuffer));

    status=RESOURCE_HUB_CREATE_PATH_FROM_ID(
        &gpioName,
        Gpio->ResourceHubId.LowPart,
        Gpio->ResourceHubId.HighPart);
    if (!NT_SUCCESS(status))
        goto fail;

    WDF_IO_TARGET_OPEN_PARAMS_INIT_OPEN_BY_NAME(
        &openParams,
        &gpioName,
        FILE_GENERIC_WRITE);

    status=WdfIoTargetOpen(
        Gpio->Target,
        &openParams);
    if (!NT_SUCCESS(status))
        goto fail;

    status=WdfWaitLockCreate(
        WDF_NO_OBJECT_ATTRIBUTES,
        &Gpio->Lock);
    if (!NT_SUCCESS(status))
        goto fail;

    return STATUS_SUCCESS;

fail:
    p360_max_gpio_deinit(Device,Gpio);
    return status;
}
