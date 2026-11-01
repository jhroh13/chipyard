// SPDX-License-Identifier: Apache-2.0
#ifndef TINY_NPU_REVB_ABI_H
#define TINY_NPU_REVB_ABI_H
#include <stdint.h>
#define TINY_NPU_ROCC_OPCODE 0x0b
#define TINY_NPU_ROCC_FUNCT3 7
#define TINY_NPU_REVB_ABI_VERSION 2
enum tiny_npu_funct7 {
 TINY_NPU_TC_CONFIG = 0x00,
 TINY_NPU_TC_ARM = 0x01,
 TINY_NPU_TC_READ = 0x02,
 TINY_NPU_TC_RESET = 0x03,
 TINY_NPU_OIC_INIT = 0x08,
 TINY_NPU_OIC_SIGNAL = 0x09,
 TINY_NPU_OIC_ACQUIRE = 0x0a,
 TINY_NPU_OIC_WAIT = 0x0b,
 TINY_NPU_OIC_QUERY = 0x0c,
 TINY_NPU_DESC_VALIDATE = 0x10,
 TINY_NPU_ENGINE_STATUS = 0x11,
 TINY_NPU_JOB_FENCE = 0x12,
 TINY_NPU_ENGINE_ABORT = 0x13,
 TINY_NPU_DMA_L0_READ = 0x20,
 TINY_NPU_DMA_L0_WRITE = 0x21,
 TINY_NPU_LOAD_SRCA = 0x22,
 TINY_NPU_LOAD_SRCB = 0x23,
 TINY_NPU_LOAD_SRCC = 0x24,
 TINY_NPU_STORE_TARGETR = 0x25,
 TINY_NPU_MAC_RUN = 0x26,
 TINY_NPU_VEC_RUN = 0x27,
 TINY_NPU_LUT_LOAD = 0x28,
 TINY_NPU_TF32_TO_FP32 = 0x29,
 TINY_NPU_FP32_TO_TF32 = 0x2a,
 TINY_NPU_ACT_RUN = 0x2b,
 TINY_NPU_LUT_RUN = 0x2c,
 TINY_NPU_VEC_ALU = 0x2d,
};

typedef struct { uint16_t oic_id; uint8_t comparison,flags; uint32_t reserved; uint64_t value; } tiny_npu_condition;
typedef struct {
 uint32_t magic; uint16_t version; uint8_t engine,flags;
 uint64_t job_id,epoch;
 uint16_t source_tc,dest_tc,scale_tc,aux_tc;
 uint32_t m,n,k,repeat,formats,operation,route,condition_counts;
 tiny_npu_condition waits[4],signals[4],credits[4];
} tiny_npu_job_descriptor;
typedef struct {
 uint64_t base_byte,window_base,window_bytes;
 int64_t stride_units[6]; uint32_t limit[6]; int32_t step[6]; uint32_t start[6];
 uint8_t unit_bits,dims,owner_core,layout; uint32_t flags;
 uint64_t job_id,epoch; uint16_t context_id,reserved16; uint32_t base_bit_offset;
 uint8_t reserved[80];
} tiny_npu_tc_descriptor;
#if defined(__cplusplus)
static_assert(sizeof(tiny_npu_condition)==16,"condition ABI");
static_assert(sizeof(tiny_npu_job_descriptor)==256,"job ABI");
static_assert(sizeof(tiny_npu_tc_descriptor)==256,"TC ABI");
#else
_Static_assert(sizeof(tiny_npu_condition)==16,"condition ABI");
_Static_assert(sizeof(tiny_npu_job_descriptor)==256,"job ABI");
_Static_assert(sizeof(tiny_npu_tc_descriptor)==256,"TC ABI");
#endif
#endif
