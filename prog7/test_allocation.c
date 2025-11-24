#include <stdio.h>
#include "src/carrier.h"

int main() {
    CarrierPool pool;
    carrier_pool_init(&pool, "/home/boss/Documents/prog/prog7/tests/carriers/test");
    
    printf("Total capacity: %zu bits (%zu MB)\n", pool.total_capacity, pool.total_capacity / 8 / 1024 / 1024);
    printf("Total used: %zu bits\n", pool.total_used);
    printf("Carrier count: %zu\n", pool.count);
    
    for (size_t i = 0; i < pool.count; i++) {
        printf("Carrier %zu: used=%zu capacity=%zu\n", i, pool.carriers[i].used_bits, pool.carriers[i].capacity_bits);
    }
    
    return 0;
}
