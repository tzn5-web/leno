#pragma once
#include <stddef.h>
#include <stdint.h>
#include "p360_board.h"

/*
 * Bounded parser for the ACPI NHLT table returned by the pinned CoolStar bus.
 * It does not retain pointers into firmware memory and performs no allocation.
 */
int p360_nhlt_parse(
    const void *table,
    size_t bytes,
    P360_NHLT_FACTS *facts
    );
