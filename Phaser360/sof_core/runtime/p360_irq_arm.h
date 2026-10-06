/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef P360_IRQ_ARM_H
#define P360_IRQ_ARM_H
#include <stdint.h>
#define P360_ADSPIS_IPC 0x00000001u
#define P360_ADSPIC_IPC 0x00000001u
#define P360_HIPCI_BUSY 0x80000000u
#define P360_HIPCIE_DONE 0x40000000u
#define P360_HIPCCTL_BUSY 0x00000001u
#define P360_HIPCCTL_DONE 0x00000002u
#define P360_HIPCT_BUSY 0x80000000u
struct p360_irq_arm_snapshot { uint32_t adspis,hipci,hipcie,hipct,hipcte,hipcctl,adspic; };
struct p360_irq_arm_plan { uint32_t hipcctl_before,hipcctl_after,adspic_before,adspic_after; };
int p360_irq_arm_prepare(const struct p360_irq_arm_snapshot*,uint64_t,int,unsigned,int,int,int,struct p360_irq_arm_plan*);
int p360_irq_arm_verify(const struct p360_irq_arm_snapshot*,const struct p360_irq_arm_plan*);
#endif
