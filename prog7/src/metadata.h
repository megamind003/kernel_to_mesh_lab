#ifndef METADATA_H
#define METADATA_H

#include "carrier.h"
#include <pthread.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>

#define MAGIC_NUMBER 0x47484F5354
#define MAX_FILENAME 256
#define MAX_INODES 256
#define INODE_BITMAP_SIZE (MAX_INODES / 8)

typedef struct {
  uint64_t magic;
  uint64_t version;
  uint64_t block_count;
  uint64_t inode_count;
  uint64_t root_inode;
  time_t created;
  time_t modified;
  uint8_t salt[16];
} Superblock;

typedef struct {
  uint64_t ino;
  mode_t mode;
  uint32_t uid;
  uint32_t gid;
  uint64_t size;
  time_t atime;
  time_t mtime;
  time_t ctime;
  uint32_t nlink;
  uint64_t block_pointers[12];
  uint64_t single_indirect;
} Inode;

typedef struct {
  uint64_t ino;
  uint8_t type;
  char name[MAX_FILENAME];
} DirEntry;

typedef struct {
  Superblock sb;
  Inode *inode_table;
  uint8_t *inode_bitmap;
  uint8_t *block_bitmap;
  Fragment *metadata_fragments;
  size_t metadata_frag_count;
  pthread_mutex_t lock;
} Filesystem;

int fs_init(Filesystem *fs, CarrierPool *pool, const char *password);
int fs_load(Filesystem *fs, CarrierPool *pool, const char *password);
int fs_sync(Filesystem *fs, CarrierPool *pool);
void fs_destroy(Filesystem *fs);

uint64_t fs_alloc_inode(Filesystem *fs);
void fs_free_inode(Filesystem *fs, uint64_t ino);
Inode *fs_get_inode(Filesystem *fs, uint64_t ino);

uint64_t fs_alloc_block(Filesystem *fs);
void fs_free_block(Filesystem *fs, uint64_t block);

int fs_read_dir(Filesystem *fs, uint64_t parent_ino, DirEntry **entries,
                size_t *count);
int fs_add_dir_entry(Filesystem *fs, uint64_t parent_ino, const char *name,
                     uint64_t child_ino, uint8_t type);
int fs_remove_dir_entry(Filesystem *fs, uint64_t parent_ino, const char *name);
int fs_lookup(Filesystem *fs, uint64_t parent_ino, const char *name,
              uint64_t *ino);

#endif
