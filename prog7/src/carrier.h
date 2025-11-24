#ifndef CARRIER_H
#define CARRIER_H

#include <pthread.h>
#include <stddef.h>
#include <stdint.h>

#define MAX_CARRIERS 1024
#define BLOCK_SIZE 4096

typedef enum {
  CARRIER_PNG,
  CARRIER_JPEG,
  CARRIER_WAV,
  CARRIER_UNKNOWN
} CarrierType;

typedef struct {
  char path[512];
  CarrierType type;
  size_t width;
  size_t height;
  size_t channels;
  size_t capacity_bits;
  size_t used_bits;
  uint8_t *bitmap;
} Carrier;

typedef struct {
  Carrier carriers[MAX_CARRIERS];
  size_t count;
  size_t total_capacity;
  size_t total_used;
  pthread_mutex_t lock;
} CarrierPool;

typedef struct {
  uint32_t carrier_idx;
  size_t offset_bits;
  size_t length_bits;
} Fragment;

int carrier_pool_init(CarrierPool *pool, const char *host_dir);
void carrier_pool_destroy(CarrierPool *pool);
int carrier_analyze(const char *path, Carrier *carrier);
size_t carrier_get_capacity(const Carrier *carrier);

int carrier_allocate(CarrierPool *pool, size_t size_bytes, Fragment **fragments,
                     size_t *frag_count);
void carrier_free_fragments(Fragment *fragments);

int carrier_read_block(CarrierPool *pool, uint64_t block_num, uint8_t *buffer);
int carrier_write_block(CarrierPool *pool, uint64_t block_num,
                        const uint8_t *buffer);

#endif
