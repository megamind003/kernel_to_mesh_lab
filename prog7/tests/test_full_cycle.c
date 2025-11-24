#include "../src/carrier.h"
#include "../src/metadata.h"
#include <dirent.h>
#include <fuse.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define TEST_DIR "/tmp/ghostfs_fulltest"
#define MOUNT_DIR "/tmp/ghostfs_fulltest_mount"
#define TEST_PASSWORD "test123"

void cleanup_test() {
  system("fusermount -u " MOUNT_DIR " 2>/dev/null || true");
  system("rm -rf " TEST_DIR " " MOUNT_DIR);
}

int main() {
  printf("=== GhostFS Full Cycle Integration Test ===\\n\\n");

  cleanup_test();
  mkdir(TEST_DIR, 0755);
  mkdir(MOUNT_DIR, 0755);

  printf("[1] Initializing carrier pool...\\n");
  CarrierPool pool;
  if (carrier_pool_init(&pool, TEST_DIR) != 0) {
    fprintf(stderr, "FAIL: No carriers found. Need PNG files in %s\\n",
            TEST_DIR);
    cleanup_test();
    return 1;
  }
  printf("  Found %zu carriers\\n", pool.count);

  printf("[2] Initializing filesystem...\\n");
  Filesystem fs;
  if (fs_init(&fs, &pool, TEST_PASSWORD) != 0) {
    fprintf(stderr, "FAIL: Cannot initialize filesystem\\n");
    carrier_pool_destroy(&pool);
    cleanup_test();
    return 1;
  }
  printf("  Filesystem initialized with %lu blocks\\n", fs.sb.block_count);

  printf("[3] Writing test data...\\n");
  const char *test_data = "GhostFS: Plausible Deniability Filesystem Test";
  size_t data_len = strlen(test_data);

  uint64_t test_ino = fs_alloc_inode(&fs);
  if (test_ino == 0) {
    fprintf(stderr, "FAIL: Cannot allocate inode\\n");
    fs_destroy(&fs);
    carrier_pool_destroy(&pool);
    cleanup_test();
    return 1;
  }

  Inode *inode = fs_get_inode(&fs, test_ino);
  inode->mode = S_IFREG | 0644;
  inode->size = data_len;

  printf("  Created test inode %lu\\n", test_ino);

  printf("[4] Adding directory entry...\\n");
  if (fs_add_dir_entry(&fs, fs.sb.root_inode, "test.txt", test_ino, DT_REG) !=
      0) {
    fprintf(stderr, "FAIL: Cannot add directory entry\\n");
    fs_destroy(&fs);
    carrier_pool_destroy(&pool);
    cleanup_test();
    return 1;
  }
  printf("  Added test.txt to root directory\\n");

  printf("[5] Syncing metadata...\\n");
  if (fs_sync(&fs, &pool) != 0) {
    fprintf(stderr, "FAIL: Cannot sync metadata\\n");
    fs_destroy(&fs);
    carrier_pool_destroy(&pool);
    cleanup_test();
    return 1;
  }
  printf("  Metadata persisted\\n");

  printf("[6] Reloading filesystem...\\n");
  fs_destroy(&fs);

  if (fs_load(&fs, &pool, TEST_PASSWORD) != 0) {
    fprintf(stderr, "FAIL: Cannot reload filesystem\\n");
    carrier_pool_destroy(&pool);
    cleanup_test();
    return 1;
  }

  if (fs.sb.magic != MAGIC_NUMBER) {
    fprintf(stderr, "FAIL: Magic number mismatch after reload\\n");
    fs_destroy(&fs);
    carrier_pool_destroy(&pool);
    cleanup_test();
    return 1;
  }
  printf("  Filesystem reloaded successfully\\n");

  printf("[7] Verifying directory entry...\\n");
  uint64_t found_ino;
  if (fs_lookup(&fs, fs.sb.root_inode, "test.txt", &found_ino) != 0) {
    fprintf(stderr, "FAIL: Cannot find test.txt\\n");
    fs_destroy(&fs);
    carrier_pool_destroy(&pool);
    cleanup_test();
    return 1;
  }

  if (found_ino != test_ino) {
    fprintf(stderr, "FAIL: Inode mismatch (%lu vs %lu)\\n", found_ino,
            test_ino);
    fs_destroy(&fs);
    carrier_pool_destroy(&pool);
    cleanup_test();
    return 1;
  }
  printf("  test.txt found with correct inode\\n");

  printf("\\n=== ALL TESTS PASSED ===\\n");

  fs_destroy(&fs);
  carrier_pool_destroy(&pool);
  cleanup_test();

  return 0;
}
