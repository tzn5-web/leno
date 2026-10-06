#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."

OBJ="$(mktemp -d)"
trap 'rm -rf "$OBJ"' EXIT INT TERM

CFLAGS="-std=c11 -Wall -Wextra -Werror -pedantic -Isof_core -Isof_core/loader -Isof_core/adapter"

for src in   sof_core/p360_transport_core.c   sof_core/loader/p360_loader.c   sof_core/loader/p360_fw_image.c   sof_core/loader/p360_irq.c   sof_core/loader/p360_dispatch.c   sof_core/loader/p360_ipc3_tx.c   sof_core/loader/p360_ipc_timer.c   sof_core/loader/p360_irq_arm.c   sof_core/adapter/p360_irq_arm_adapter.c
do
  cc $CFLAGS -c "$src" -o "$OBJ/$(basename "$src" .c).o"
done

SAN="-fsanitize=address,undefined -fno-omit-frame-pointer"

cc $CFLAGS $SAN tests/b4_transport_regression.c   sof_core/p360_transport_core.c   -o "$OBJ/transport"
"$OBJ/transport"

cc $CFLAGS $SAN tests/b4_irq_regression.c   sof_core/loader/p360_irq.c   -o "$OBJ/irq"
"$OBJ/irq"

cc $CFLAGS $SAN tests/b4_ipc_timer_regression.c   sof_core/p360_transport_core.c   sof_core/loader/p360_ipc_timer.c   -o "$OBJ/ipc_timer"
"$OBJ/ipc_timer"

cc $CFLAGS $SAN tests/irq_arm_adapter_regression.c   sof_core/loader/p360_irq_arm.c   sof_core/adapter/p360_irq_arm_adapter.c   -o "$OBJ/irq_arm"
"$OBJ/irq_arm"

cc $CFLAGS $SAN tests/ipc3_tx_regression.c   sof_core/p360_transport_core.c   sof_core/loader/p360_fw_image.c   sof_core/loader/p360_dispatch.c   sof_core/loader/p360_ipc3_tx.c   -o "$OBJ/ipc3_tx"
"$OBJ/ipc3_tx"

echo "B4 core compile/regressions: PASS"
