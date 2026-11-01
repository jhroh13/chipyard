OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY {
 CODE (rx) : ORIGIN = 0x613c0000, LENGTH = 0x20000
 RW (rw) : ORIGIN = 0x613e0000, LENGTH = 0x20000
}
SECTIONS {
 .text : { KEEP(*(.text.init)) *(.text*) } > CODE
 .rodata : { *(.rodata*) } > CODE
 .mailbox 0x613f8000 (NOLOAD) : { *(.mailbox) } > RW
 ASSERT(SIZEOF(.text)+SIZEOF(.rodata) <= 0x20000, "code exceeds boot reservation")
 ASSERT(SIZEOF(.mailbox) <= 0x1000, "mailbox overflow")
}
