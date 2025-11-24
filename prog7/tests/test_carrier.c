#include "../src/carrier.h"
#include "../src/stego.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TEST_DIR "/tmp/ghostfs_test_carriers"

void test_carrier_pool_init() {
  printf("Testing carrier pool initialization...\\n");

  CarrierPool pool;
  int result = carrier_pool_init(&pool, TEST_DIR);

  assert(result == 0 || pool.count > 0);
  assert(pool.total_capacity > 0);

  printf("  Found %zu carriers with %zu total capacity\\n", pool.count,
         pool.total_capacity);

  carrier_pool_destroy(&pool);
  printf("  PASS\\n");
}

void test_fragment_allocation() {
  printf("Testing fragment allocation...\\n");

  CarrierPool pool;
  carrier_pool_init(&pool, TEST_DIR);

  Fragment *frags;
  size_t frag_count;

  size_t test_size = 1024 * 1024;
  int result = carrier_allocate(&pool, test_size, &frags, &frag_count);

  assert(result == 0);
  assert(frag_count > 0);

  size_t total_bits = 0;
  for (size_t i = 0; i < frag_count; i++) {
    total_bits += frags[i].length_bits;
  }

  assert(total_bits >= test_size * 8);

  carrier_free_fragments(frags);
  carrier_pool_destroy(&pool);

  printf("  Allocated %zu fragments for %zu bytes\\n", frag_count, test_size);
  printf("  PASS\\n");
}

void test_capacity_calculation() {
  printf("Testing capacity calculation...\\n");

  size_t width = 1024;
  size_t height = 1024;
  size_t channels = 3;

  size_t capacity = stego_calculate_png_capacity(width, height, channels);
  size_t expected = width * height * channels;

  assert(capacity == expected);

  printf("  Capacity for %zux%zu RGB: %zu bits\\n", width, height, capacity);
  printf("  PASS\\n");
}

int main() {
  printf("Running carrier pool tests...\\n\\n");

  test_capacity_calculation();
  test_carrier_pool_init();
  test_fragment_allocation();

  printf("\\nAll tests passed!\\n");
  return 0;
}
