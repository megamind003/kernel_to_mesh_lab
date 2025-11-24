#ifndef STEGO_H
#define STEGO_H

#include "carrier.h"
#include <stddef.h>
#include <stdint.h>

int stego_png_encode(const char *path, size_t offset_bits, size_t length_bits,
                     const uint8_t *data);
int stego_png_decode(const char *path, size_t offset_bits, size_t length_bits,
                     uint8_t *data);

int stego_encode_fragments(CarrierPool *pool, const Fragment *fragments,
                           size_t frag_count, const uint8_t *data,
                           size_t data_len);
int stego_decode_fragments(CarrierPool *pool, const Fragment *fragments,
                           size_t frag_count, uint8_t *data, size_t data_len);

size_t stego_calculate_png_capacity(size_t width, size_t height,
                                    size_t channels);

int stego_detect_noise_zones(const uint8_t *pixels, size_t width, size_t height,
                             uint8_t *noise_map);

#endif
