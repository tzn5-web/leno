#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
cc -std=c11 -Wall -Wextra -Werror -pedantic   tests/core_smoke.c   src/p360_state.c src/p360_board.c src/p360_safety.c   -Iinclude -o /tmp/p360_core_smoke
/tmp/p360_core_smoke
