#include "stego.h"
#include <math.h>
#include <png.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

size_t stego_calculate_png_capacity(size_t width, size_t height,
                                    size_t channels) {
  return width * height * channels;
}

static void set_bit(uint8_t *byte, int pos, int value) {
  if (value) {
    *byte |= (1 << pos);
  } else {
    *byte &= ~(1 << pos);
  }
}

static int get_bit(uint8_t byte, int pos) { return (byte >> pos) & 1; }

int stego_png_encode(const char *path, size_t offset_bits, size_t length_bits,
                     const uint8_t *data) {
  FILE *fp = fopen(path, "rb");
  if (!fp)
    return -1;

  png_structp png =
      png_create_read_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
  if (!png) {
    fclose(fp);
    return -1;
  }

  png_infop info = png_create_info_struct(png);
  if (!info) {
    png_destroy_read_struct(&png, NULL, NULL);
    fclose(fp);
    return -1;
  }

  if (setjmp(png_jmpbuf(png))) {
    png_destroy_read_struct(&png, &info, NULL);
    fclose(fp);
    return -1;
  }

  png_init_io(png, fp);
  png_read_info(png, info);

  int width = png_get_image_width(png, info);
  int height = png_get_image_height(png, info);
  png_byte color_type = png_get_color_type(png, info);
  png_byte bit_depth = png_get_bit_depth(png, info);

  if (bit_depth == 16) {
    png_set_strip_16(png);
  }

  if (color_type == PNG_COLOR_TYPE_PALETTE) {
    png_set_palette_to_rgb(png);
  }

  if (color_type == PNG_COLOR_TYPE_GRAY && bit_depth < 8) {
    png_set_expand_gray_1_2_4_to_8(png);
  }

  if (png_get_valid(png, info, PNG_INFO_tRNS)) {
    png_set_tRNS_to_alpha(png);
  }

  png_read_update_info(png, info);

  png_bytep *row_pointers = malloc(sizeof(png_bytep) * height);
  for (int y = 0; y < height; y++) {
    row_pointers[y] = malloc(png_get_rowbytes(png, info));
  }

  png_read_image(png, row_pointers);
  fclose(fp);

  size_t channels = png_get_channels(png, info);
  size_t total_pixels = width * height * channels;

  size_t bit_idx = 0;
  for (size_t pixel = offset_bits;
       pixel < total_pixels && bit_idx < length_bits; pixel++) {
    int y = pixel / (width * channels);
    int x = (pixel % (width * channels));

    int data_byte = bit_idx / 8;
    int data_bit = bit_idx % 8;

    int bit_value = get_bit(data[data_byte], data_bit);
    set_bit(&row_pointers[y][x], 0, bit_value);

    bit_idx++;
  }

  char temp_path[1024];
  snprintf(temp_path, sizeof(temp_path), "%s.tmp", path);

  FILE *fp_write = fopen(temp_path, "wb");
  if (!fp_write) {
    for (int y = 0; y < height; y++) {
      free(row_pointers[y]);
    }
    free(row_pointers);
    png_destroy_read_struct(&png, &info, NULL);
    return -1;
  }

  png_structp png_write =
      png_create_write_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
  png_infop info_write = png_create_info_struct(png_write);

  if (setjmp(png_jmpbuf(png_write))) {
    fclose(fp_write);
    unlink(temp_path);
    for (int y = 0; y < height; y++) {
      free(row_pointers[y]);
    }
    free(row_pointers);
    png_destroy_write_struct(&png_write, &info_write);
    png_destroy_read_struct(&png, &info, NULL);
    return -1;
  }

  png_init_io(png_write, fp_write);
  png_set_IHDR(png_write, info_write, width, height, 8, color_type,
               PNG_INTERLACE_NONE, PNG_COMPRESSION_TYPE_DEFAULT,
               PNG_FILTER_TYPE_DEFAULT);
  png_write_info(png_write, info_write);
  png_write_image(png_write, row_pointers);
  png_write_end(png_write, NULL);

  fclose(fp_write);
  png_destroy_write_struct(&png_write, &info_write);

  for (int y = 0; y < height; y++) {
    free(row_pointers[y]);
  }
  free(row_pointers);
  png_destroy_read_struct(&png, &info, NULL);

  if (rename(temp_path, path) != 0) {
    unlink(temp_path);
    return -1;
  }

  return 0;
}

int stego_png_decode(const char *path, size_t offset_bits, size_t length_bits,
                     uint8_t *data) {
  FILE *fp = fopen(path, "rb");
  if (!fp)
    return -1;

  png_structp png =
      png_create_read_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
  if (!png) {
    fclose(fp);
    return -1;
  }

  png_infop info = png_create_info_struct(png);
  if (!info) {
    png_destroy_read_struct(&png, NULL, NULL);
    fclose(fp);
    return -1;
  }

  if (setjmp(png_jmpbuf(png))) {
    png_destroy_read_struct(&png, &info, NULL);
    fclose(fp);
    return -1;
  }

  png_init_io(png, fp);
  png_read_info(png, info);

  int width = png_get_image_width(png, info);
  int height = png_get_image_height(png, info);
  png_byte color_type = png_get_color_type(png, info);
  png_byte bit_depth = png_get_bit_depth(png, info);

  if (bit_depth == 16) {
    png_set_strip_16(png);
  }

  if (color_type == PNG_COLOR_TYPE_PALETTE) {
    png_set_palette_to_rgb(png);
  }

  if (color_type == PNG_COLOR_TYPE_GRAY && bit_depth < 8) {
    png_set_expand_gray_1_2_4_to_8(png);
  }

  if (png_get_valid(png, info, PNG_INFO_tRNS)) {
    png_set_tRNS_to_alpha(png);
  }

  png_read_update_info(png, info);

  png_bytep *row_pointers = malloc(sizeof(png_bytep) * height);
  for (int y = 0; y < height; y++) {
    row_pointers[y] = malloc(png_get_rowbytes(png, info));
  }

  png_read_image(png, row_pointers);
  fclose(fp);

  size_t channels = png_get_channels(png, info);
  size_t total_pixels = width * height * channels;

  memset(data, 0, (length_bits + 7) / 8);

  size_t bit_idx = 0;
  for (size_t pixel = offset_bits;
       pixel < total_pixels && bit_idx < length_bits; pixel++) {
    int y = pixel / (width * channels);
    int x = (pixel % (width * channels));

    int bit_value = get_bit(row_pointers[y][x], 0);

    int data_byte = bit_idx / 8;
    int data_bit = bit_idx % 8;
    set_bit(&data[data_byte], data_bit, bit_value);

    bit_idx++;
  }

  for (int y = 0; y < height; y++) {
    free(row_pointers[y]);
  }
  free(row_pointers);
  png_destroy_read_struct(&png, &info, NULL);

  return 0;
}

int stego_encode_fragments(CarrierPool *pool, const Fragment *fragments,
                           size_t frag_count, const uint8_t *data,
                           size_t data_len) {
  size_t data_offset = 0;

  for (size_t i = 0; i < frag_count; i++) {
    const Fragment *frag = &fragments[i];
    Carrier *carrier = &pool->carriers[frag->carrier_idx];

    size_t bytes_to_encode = (frag->length_bits + 7) / 8;
    if (data_offset + bytes_to_encode > data_len) {
      bytes_to_encode = data_len - data_offset;
    }

    if (stego_png_encode(carrier->path, frag->offset_bits, frag->length_bits,
                         data + data_offset) != 0) {
      return -1;
    }

    data_offset += bytes_to_encode;
  }

  return 0;
}

int stego_decode_fragments(CarrierPool *pool, const Fragment *fragments,
                           size_t frag_count, uint8_t *data, size_t data_len) {
  size_t data_offset = 0;

  for (size_t i = 0; i < frag_count; i++) {
    const Fragment *frag = &fragments[i];
    Carrier *carrier = &pool->carriers[frag->carrier_idx];

    size_t bytes_to_decode = (frag->length_bits + 7) / 8;
    if (data_offset + bytes_to_decode > data_len) {
      bytes_to_decode = data_len - data_offset;
    }

    if (stego_png_decode(carrier->path, frag->offset_bits, frag->length_bits,
                         data + data_offset) != 0) {
      return -1;
    }

    data_offset += bytes_to_decode;
  }

  return 0;
}

int stego_detect_noise_zones(const uint8_t *pixels, size_t width, size_t height,
                             uint8_t *noise_map) {
  for (size_t y = 1; y < height - 1; y++) {
    for (size_t x = 1; x < width - 1; x++) {
      size_t idx = y * width + x;

      int center = pixels[idx];
      int sum = 0;
      sum += abs(center - pixels[(y - 1) * width + x]);
      sum += abs(center - pixels[(y + 1) * width + x]);
      sum += abs(center - pixels[y * width + (x - 1)]);
      sum += abs(center - pixels[y * width + (x + 1)]);

      noise_map[idx] = (sum / 4 > 15) ? 1 : 0;
    }
  }

  return 0;
}
