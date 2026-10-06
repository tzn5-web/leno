#pragma once
#include <stdint.h>
#include <stddef.h>

#define P360_IPC3_MAX_PAYLOAD 4096u

typedef struct P360_IPC3_MESSAGE {
    uint32_t primary;
    uint32_t extension;
    uint32_t payload_bytes;
    uint8_t payload[P360_IPC3_MAX_PAYLOAD];
} P360_IPC3_MESSAGE;

typedef struct P360_IPC3_TRANSPORT {
    void *context;
    int (*mailbox_write)(void *context, uint32_t offset, const void *src, uint32_t bytes);
    int (*mailbox_read)(void *context, uint32_t offset, void *dst, uint32_t bytes);
    uint32_t (*read32)(void *context, uint32_t reg);
    void (*write32)(void *context, uint32_t reg, uint32_t value);
    int (*wait_event)(void *context, uint32_t timeout_ms);
} P360_IPC3_TRANSPORT;

int p360_ipc3_send(P360_IPC3_TRANSPORT *t, const P360_IPC3_MESSAGE *request);
int p360_ipc3_receive(P360_IPC3_TRANSPORT *t, P360_IPC3_MESSAGE *reply);
