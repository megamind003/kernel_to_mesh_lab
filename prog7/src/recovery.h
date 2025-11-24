#ifndef RECOVERY_H
#define RECOVERY_H

#include <stddef.h>
#include <stdint.h>

uint32_t crc32_calculate(const uint8_t *data, size_t len);
int crc32_verify(const uint8_t *data, size_t len, uint32_t expected);

typedef struct {
  uint32_t crc;
  uint8_t data[];
} ChecksummedBlock;

int recovery_encode_block(const uint8_t *input, size_t len,
                          ChecksummedBlock **output);
int recovery_decode_block(const ChecksummedBlock *input, uint8_t *output,
                          size_t *len);

#endif
