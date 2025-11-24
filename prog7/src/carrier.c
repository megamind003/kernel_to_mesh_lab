#include "carrier.h"
#include "stego.h"
#include <dirent.h>
#include <png.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>

static int is_png_file(const char *path) {
  size_t len = strlen(path);
  return len > 4 && strcmp(path + len - 4, ".png") == 0;
}

int carrier_analyze(const char *path, Carrier *carrier) {
  if (!is_png_file(path)) {
    carrier->type = CARRIER_UNKNOWN;
    return -1;
  }

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

  carrier->width = png_get_image_width(png, info);
  carrier->height = png_get_image_height(png, info);
  carrier->channels = png_get_channels(png, info);
  carrier->type = CARRIER_PNG;
  strncpy(carrier->path, path, sizeof(carrier->path) - 1);

  carrier->capacity_bits = stego_calculate_png_capacity(
      carrier->width, carrier->height, carrier->channels);
  carrier->used_bits = 0;

  size_t bitmap_size = (carrier->capacity_bits + 7) / 8;
  carrier->bitmap = calloc(1, bitmap_size);

  png_destroy_read_struct(&png, &info, NULL);
  fclose(fp);

  return 0;
}

int carrier_pool_init(CarrierPool *pool, const char *host_dir) {
  memset(pool, 0, sizeof(CarrierPool));
  pthread_mutex_init(&pool->lock, NULL);

  DIR *dir = opendir(host_dir);
  if (!dir) {
    fprintf(stderr, "Cannot open host directory: %s\n", host_dir);
    return -1;
  }

  struct dirent *entry;
  char full_path[1024];

  while ((entry = readdir(dir)) != NULL && pool->count < MAX_CARRIERS) {
    snprintf(full_path, sizeof(full_path), "%s/%s", host_dir, entry->d_name);

    struct stat st;
    if (stat(full_path, &st) != 0 || !S_ISREG(st.st_mode))
      continue;

    Carrier *carrier = &pool->carriers[pool->count];
    if (carrier_analyze(full_path, carrier) == 0) {
      pool->total_capacity += carrier->capacity_bits;
      pool->count++;
      printf("Discovered carrier: %s (capacity: %zu bits)\n", entry->d_name,
             carrier->capacity_bits);
    }
  }

  closedir(dir);

  if (pool->count == 0) {
    fprintf(stderr, "No valid carriers found\n");
    return -1;
  }

  printf("Carrier pool initialized: %zu carriers, total capacity: %zu MB\n",
         pool->count, pool->total_capacity / 8 / 1024 / 1024);

  return 0;
}

void carrier_pool_destroy(CarrierPool *pool) {
  for (size_t i = 0; i < pool->count; i++) {
    if (pool->carriers[i].bitmap) {
      free(pool->carriers[i].bitmap);
    }
  }
  pthread_mutex_destroy(&pool->lock);
}

size_t carrier_get_capacity(const Carrier *carrier) {
  return carrier->capacity_bits;
}

int carrier_allocate(CarrierPool *pool, size_t size_bytes, Fragment **fragments,
                     size_t *frag_count) {
  size_t needed_bits = size_bytes * 8;

  pthread_mutex_lock(&pool->lock);

  if (pool->total_capacity - pool->total_used < needed_bits) {
    pthread_mutex_unlock(&pool->lock);
    fprintf(stderr, "Insufficient capacity: need %zu bits, have %zu bits\n",
            needed_bits, pool->total_capacity - pool->total_used);
    return -1;
  }

  size_t max_frags = pool->count;
  Fragment *frags = malloc(sizeof(Fragment) * max_frags);
  size_t frag_idx = 0;
  size_t allocated = 0;

  for (size_t i = 0; i < pool->count && allocated < needed_bits; i++) {
    Carrier *c = &pool->carriers[i];
    size_t available = c->capacity_bits - c->used_bits;

    if (available == 0)
      continue;

    size_t to_alloc = (needed_bits - allocated < available)
                          ? (needed_bits - allocated)
                          : available;

    frags[frag_idx].carrier_idx = i;
    frags[frag_idx].offset_bits = c->used_bits;
    frags[frag_idx].length_bits = to_alloc;
    frag_idx++;

    c->used_bits += to_alloc;
    allocated += to_alloc;
  }

  pool->total_used += allocated;
  pthread_mutex_unlock(&pool->lock);

  *fragments = frags;
  *frag_count = frag_idx;

  return 0;
}

void carrier_free_fragments(Fragment *fragments) { free(fragments); }

int carrier_read_block(CarrierPool *pool, uint64_t block_num, uint8_t *buffer) {
  size_t offset_bits = block_num * BLOCK_SIZE * 8;
  size_t needed_bits = BLOCK_SIZE * 8;
  size_t bits_read = 0;
  size_t buffer_offset = 0;

  pthread_mutex_lock(&pool->lock);

  for (size_t i = 0; i < pool->count && bits_read < needed_bits; i++) {
    Carrier *c = &pool->carriers[i];

    if (offset_bits >= c->used_bits) {
      offset_bits -= c->used_bits;
      continue;
    }

    size_t local_offset = offset_bits;
    size_t to_read = (needed_bits - bits_read < c->used_bits - local_offset)
                         ? (needed_bits - bits_read)
                         : (c->used_bits - local_offset);

    pthread_mutex_unlock(&pool->lock);

    uint8_t temp_buf[(to_read + 7) / 8];
    if (stego_png_decode(c->path, local_offset, to_read, temp_buf) != 0) {
      return -1;
    }

    size_t bytes_to_copy = (to_read + 7) / 8;
    memcpy(buffer + buffer_offset, temp_buf, bytes_to_copy);
    buffer_offset += bytes_to_copy;
    bits_read += to_read;
    offset_bits = 0;

    pthread_mutex_lock(&pool->lock);
  }

  pthread_mutex_unlock(&pool->lock);
  return 0;
}

int carrier_write_block(CarrierPool *pool, uint64_t block_num,
                        const uint8_t *buffer) {
  size_t offset_bits = block_num * BLOCK_SIZE * 8;
  size_t needed_bits = BLOCK_SIZE * 8;
  size_t bits_written = 0;
  size_t buffer_offset = 0;

  pthread_mutex_lock(&pool->lock);

  for (size_t i = 0; i < pool->count && bits_written < needed_bits; i++) {
    Carrier *c = &pool->carriers[i];

    if (offset_bits >= c->used_bits) {
      offset_bits -= c->used_bits;
      continue;
    }

    size_t local_offset = offset_bits;
    size_t to_write = (needed_bits - bits_written < c->used_bits - local_offset)
                          ? (needed_bits - bits_written)
                          : (c->used_bits - local_offset);

    pthread_mutex_unlock(&pool->lock);

    if (stego_png_encode(c->path, local_offset, to_write,
                         buffer + buffer_offset) != 0) {
      return -1;
    }

    size_t bytes_written = (to_write + 7) / 8;
    buffer_offset += bytes_written;
    bits_written += to_write;
    offset_bits = 0;

    pthread_mutex_lock(&pool->lock);
  }

  pthread_mutex_unlock(&pool->lock);
  return 0;
}
