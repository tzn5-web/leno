#pragma once
/*
 * Freestanding C99 integer types for the P360 kernel build.
 *
 * WDK km/crt intentionally does not provide <stdint.h>. Pulling the MSVC
 * user-mode header into a kernel project mixes VCRuntime with km/crt.
 * Keep this shim minimal, ABI-fixed and free of user-mode runtime headers.
 */
#ifndef P360_KERNEL_STDINT_H
#define P360_KERNEL_STDINT_H

typedef signed char         int8_t;
typedef unsigned char       uint8_t;
typedef signed short        int16_t;
typedef unsigned short      uint16_t;
typedef signed int          int32_t;
typedef unsigned int        uint32_t;
typedef signed __int64      int64_t;
typedef unsigned __int64    uint64_t;

typedef int8_t              int_least8_t;
typedef uint8_t             uint_least8_t;
typedef int16_t             int_least16_t;
typedef uint16_t            uint_least16_t;
typedef int32_t             int_least32_t;
typedef uint32_t            uint_least32_t;
typedef int64_t             int_least64_t;
typedef uint64_t            uint_least64_t;

typedef int8_t              int_fast8_t;
typedef uint8_t             uint_fast8_t;
typedef int32_t             int_fast16_t;
typedef uint32_t            uint_fast16_t;
typedef int32_t             int_fast32_t;
typedef uint32_t            uint_fast32_t;
typedef int64_t             int_fast64_t;
typedef uint64_t            uint_fast64_t;

#if defined(_WIN64)
typedef int64_t             intptr_t;
typedef uint64_t            uintptr_t;
#else
typedef int32_t             intptr_t;
typedef uint32_t            uintptr_t;
#endif

typedef int64_t             intmax_t;
typedef uint64_t            uintmax_t;

#define INT8_MIN            (-127 - 1)
#define INT8_MAX            127
#define UINT8_MAX           0xffu
#define INT16_MIN           (-32767 - 1)
#define INT16_MAX           32767
#define UINT16_MAX          0xffffu
#define INT32_MIN           (-2147483647 - 1)
#define INT32_MAX           2147483647
#define UINT32_MAX          0xffffffffu
#define INT64_MIN           (-9223372036854775807LL - 1)
#define INT64_MAX           9223372036854775807LL
#define UINT64_MAX          0xffffffffffffffffULL

#define INTPTR_MIN          INT64_MIN
#define INTPTR_MAX          INT64_MAX
#define UINTPTR_MAX         UINT64_MAX
#define INTMAX_MIN          INT64_MIN
#define INTMAX_MAX          INT64_MAX
#define UINTMAX_MAX         UINT64_MAX

#define INT8_C(x)           x
#define UINT8_C(x)          x##u
#define INT16_C(x)          x
#define UINT16_C(x)         x##u
#define INT32_C(x)          x
#define UINT32_C(x)         x##u
#define INT64_C(x)          x##LL
#define UINT64_C(x)         x##ULL
#define INTMAX_C(x)         INT64_C(x)
#define UINTMAX_C(x)        UINT64_C(x)

#endif
