#pragma once

#include <ntddk.h>
#include <wdf.h>

#define RESHUB_USE_HELPER_ROUTINES

typedef struct _P360_MAX_GPIO_CONTEXT {
    WDFIOTARGET Target;
    LARGE_INTEGER ResourceHubId;
    WDFWAITLOCK Lock;
} P360_MAX_GPIO_CONTEXT;

NTSTATUS p360_max_gpio_init(
    _In_ WDFDEVICE Device,
    _Inout_ P360_MAX_GPIO_CONTEXT *Gpio);

VOID p360_max_gpio_deinit(
    _In_ WDFDEVICE Device,
    _Inout_ P360_MAX_GPIO_CONTEXT *Gpio);

NTSTATUS p360_max_gpio_write(
    _Inout_ P360_MAX_GPIO_CONTEXT *Gpio,
    _In_ UCHAR Value);
