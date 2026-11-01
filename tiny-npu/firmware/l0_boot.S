/* Minimal shared RV64 stage1 code resident in reserved L0 SRAM.
 * Real stage0 must load/verify code, initialize RW, fence.i, then release harts.
 * Spike preloads the ELF; it does not model the actual Rocket/TL/guard path.
 */
.include "boot_config.S.inc"
.option norvc
.section .text.init,"ax",@progbits
.globl _start
_start:
  fence.i
  csrr a0, mhartid
  li t0, ROCKET_CORES
  bgeu a0, t0, .Lpark
  li sp, L0_BOOT_STACK_BASE_ADDR
  li t0, L0_BOOT_STACK_BYTES_PER_HART
  addi t1, a0, 1
  mul t1, t1, t0
  add sp, sp, t1
  sd a0, -8(sp)
  ld t2, -8(sp)
  bne t2, a0, .Lfail
  la t0, hart_records
  slli t1, a0, 6
  add t0, t0, t1
  sd sp, 8(t0)
  fence w,w
  addi t1, a0, 1
  sd t1, 0(t0)
  bnez a0, .Lpark
  li s0, 0
  la s1, hart_records
.Lwait:
  ld t0, 0(s1)
  beqz t0, .Lwait
  fence r,rw
  addi t1, s0, 1
  bne t0, t1, .Lfail
  li t2, L0_BOOT_STACK_BYTES_PER_HART
  mul t2, t2, t1
  li t3, L0_BOOT_STACK_BASE_ADDR
  add t2, t2, t3
  ld t3, 8(s1)
  bne t2, t3, .Lfail
  addi s1, s1, 64
  addi s0, s0, 1
  li t0, ROCKET_CORES
  bltu s0, t0, .Lwait
  li t0, 1
  j .Lfinish
.Lfail:
  li t0, 3
.Lfinish:
  la t1, tohost
  fence rw,w
  sd t0, 0(t1)
.Lpark:
  wfi
  j .Lpark
.section .mailbox,"aw",@nobits
.balign 64
.globl tohost
.globl fromhost
tohost: .zero 8
fromhost: .zero 8
.balign 64
.globl hart_records
hart_records: .zero 64*ROCKET_CORES
