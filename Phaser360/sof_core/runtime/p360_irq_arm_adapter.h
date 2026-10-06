/* SPDX-License-Identifier: BSD-3-Clause */
#ifndef P360_IRQ_ARM_ADAPTER_H
#define P360_IRQ_ARM_ADAPTER_H
#include <stdint.h>
#include "p360_irq_arm.h"
#define P360_DSP_ADSPIC 0x08u
#define P360_DSP_ADSPIS 0x0cu
#define P360_DSP_HIPCT 0x40u
#define P360_DSP_HIPCTE 0x44u
#define P360_DSP_HIPCI 0x48u
#define P360_DSP_HIPCIE 0x4cu
#define P360_DSP_HIPCCTL 0x50u
enum p360_irq_arm_adapter_status{P360_IRQ_ADAPTER_OK=0,P360_IRQ_ADAPTER_ARGUMENT=-1,P360_IRQ_ADAPTER_ACCESS=-2,P360_IRQ_ADAPTER_SNAPSHOT=-3,P360_IRQ_ADAPTER_POLICY=-4,P360_IRQ_ADAPTER_WRITE=-5,P360_IRQ_ADAPTER_VERIFY=-6,P360_IRQ_ADAPTER_ROLLBACK_UNPROVED=-7};
struct p360_irq_arm_adapter_io{int(*permit)(void*);int(*read32)(void*,uint32_t,uint32_t*);int(*write32)(void*,uint32_t,uint32_t);void(*barrier)(void*);};
struct p360_irq_arm_adapter_result{int status,writes_started,rollback_attempted,rollback_proved,poison_required;struct p360_irq_arm_snapshot before,after;struct p360_irq_arm_plan plan;};
int p360_irq_arm_adapter_run(const struct p360_irq_arm_adapter_io*,void*,uint64_t,int,unsigned,int,int,int,struct p360_irq_arm_adapter_result*);
#endif
