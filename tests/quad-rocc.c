#include <riscv-pk/encoding.h>
#include <stdio.h>
#include "rocc.h"

#define CORES 4

static unsigned long inputs[CORES];
static unsigned long results[CORES];
static volatile int arrived;
static volatile int finished;

/* libgloss calls __main on secondary harts; main joins on hart zero. */
void __main(void)
{
  unsigned long hart = read_csr(mhartid);
  if (hart >= CORES)
    while (1);

  inputs[hart] = 100 + hart;
  __sync_fetch_and_add(&arrived, 1);
  while (__atomic_load_n(&arrived, __ATOMIC_ACQUIRE) != CORES);

  /* Load another hart's data through RoCC's D-cache port, then add/read. */
  unsigned long source = (hart + 1) % CORES;
  unsigned long result;
  asm volatile ("fence" ::: "memory");
  ROCC_INSTRUCTION_SS(0, (uintptr_t)&inputs[source], 0, 2);
  ROCC_INSTRUCTION_SS(0, hart + 1, 0, 3);
  ROCC_INSTRUCTION_DSS(0, result, 0, 0, 1);
  results[hart] = result;
  __sync_fetch_and_add(&finished, 1);

  if (hart != 0)
    while (1);
  while (__atomic_load_n(&finished, __ATOMIC_ACQUIRE) != CORES);
}

int main(void)
{
  __main();
  for (unsigned long hart = 0; hart < CORES; hart++) {
    unsigned long expected = 100 + (hart + 1) % CORES + hart + 1;
    if (results[hart] != expected) {
      printf("FAIL: hart %lu RoCC result %lu, expected %lu\n",
             hart, results[hart], expected);
      return 1;
    }
    printf("PASS: hart %lu RoCC load/add/read = %lu\n", hart, results[hart]);
  }
  return 0;
}
