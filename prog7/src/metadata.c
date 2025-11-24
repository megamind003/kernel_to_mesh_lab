#define _POSIX_C_SOURCE 200809L
#define _XOPEN_SOURCE 700

#include "metadata.h"
#include "crypto.h"
#include "stego.h"
#include <errno.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int fs_init(Filesystem *fs, CarrierPool *pool, const char *password) {
  memset(fs, 0, sizeof(Filesystem));
  pthread_mutex_init(&fs->lock, NULL);

  fs->sb.magic = MAGIC_NUMBER;
  fs->sb.version = 1;
  fs->sb.block_count = (pool->total_capacity / 8) / BLOCK_SIZE;
  fs->sb.inode_count = MAX_INODES;
  fs->sb.root_inode = 1;
  fs->sb.created = time(NULL);
  fs->sb.modified = fs->sb.created;

  CryptoContext crypto_ctx;
  crypto_init(&crypto_ctx, password);
  memcpy(fs->sb.salt, crypto_ctx.salt, 16);
  crypto_destroy(&crypto_ctx);

  fs->inode_table = calloc(MAX_INODES, sizeof(Inode));
  fs->inode_bitmap = calloc(INODE_BITMAP_SIZE, 1);
  fs->block_bitmap = calloc((fs->sb.block_count + 7) / 8, 1);

  Inode *root = &fs->inode_table[fs->sb.root_inode];
  root->ino = fs->sb.root_inode;
  root->mode = S_IFDIR | 0755;
  root->uid = getuid();
  root->gid = getgid();
  root->size = 0;
  root->atime = root->mtime = root->ctime = time(NULL);
  root->nlink = 2;

  fs->inode_bitmap[fs->sb.root_inode / 8] |= (1 << (fs->sb.root_inode % 8));

  size_t metadata_size = sizeof(Superblock) + (MAX_INODES * sizeof(Inode)) +
                         INODE_BITMAP_SIZE + ((fs->sb.block_count + 7) / 8);

  if (carrier_allocate(pool, metadata_size, &fs->metadata_fragments,
                       &fs->metadata_frag_count) != 0) {
    fprintf(stderr, "Failed to allocate space for metadata\n");
    fs_destroy(fs);
    return -1;
  }

  return fs_sync(fs, pool);
}

int fs_sync(Filesystem *fs, CarrierPool *pool) {
  pthread_mutex_lock(&fs->lock);

  size_t offset = 0;
  size_t total_size = sizeof(Superblock) + (MAX_INODES * sizeof(Inode)) +
                      INODE_BITMAP_SIZE + ((fs->sb.block_count + 7) / 8);

  uint8_t *buffer = malloc(total_size);
  if (!buffer) {
    pthread_mutex_unlock(&fs->lock);
    return -1;
  }

  fs->sb.modified = time(NULL);

  memcpy(buffer + offset, &fs->sb, sizeof(Superblock));
  offset += sizeof(Superblock);

  memcpy(buffer + offset, fs->inode_table, MAX_INODES * sizeof(Inode));
  offset += MAX_INODES * sizeof(Inode);

  memcpy(buffer + offset, fs->inode_bitmap, INODE_BITMAP_SIZE);
  offset += INODE_BITMAP_SIZE;

  memcpy(buffer + offset, fs->block_bitmap, (fs->sb.block_count + 7) / 8);

  if (stego_encode_fragments(pool, fs->metadata_fragments,
                             fs->metadata_frag_count, buffer,
                             total_size) != 0) {
    free(buffer);
    pthread_mutex_unlock(&fs->lock);
    return -1;
  }

  free(buffer);
  pthread_mutex_unlock(&fs->lock);
  return 0;
}

int fs_load(Filesystem *fs, CarrierPool *pool, const char *password) {
  memset(fs, 0, sizeof(Filesystem));
  pthread_mutex_init(&fs->lock, NULL);

  size_t metadata_size =
      sizeof(Superblock) + (MAX_INODES * sizeof(Inode)) + INODE_BITMAP_SIZE;

  if (carrier_allocate(pool, metadata_size, &fs->metadata_fragments,
                       &fs->metadata_frag_count) != 0) {
    return -1;
  }

  uint8_t *buffer = malloc(metadata_size);
  if (!buffer)
    return -1;

  if (stego_decode_fragments(pool, fs->metadata_fragments,
                             fs->metadata_frag_count, buffer,
                             metadata_size) != 0) {
    free(buffer);
    return -1;
  }

  size_t offset = 0;
  memcpy(&fs->sb, buffer + offset, sizeof(Superblock));
  offset += sizeof(Superblock);

  if (fs->sb.magic != MAGIC_NUMBER) {
    fprintf(stderr, "Invalid filesystem magic\n");
    free(buffer);
    return -1;
  }

  fs->inode_table = malloc(MAX_INODES * sizeof(Inode));
  memcpy(fs->inode_table, buffer + offset, MAX_INODES * sizeof(Inode));
  offset += MAX_INODES * sizeof(Inode);

  fs->inode_bitmap = malloc(INODE_BITMAP_SIZE);
  memcpy(fs->inode_bitmap, buffer + offset, INODE_BITMAP_SIZE);

  fs->block_bitmap = calloc((fs->sb.block_count + 7) / 8, 1);

  free(buffer);
  return 0;
}

void fs_destroy(Filesystem *fs) {
  if (fs->inode_table)
    free(fs->inode_table);
  if (fs->inode_bitmap)
    free(fs->inode_bitmap);
  if (fs->block_bitmap)
    free(fs->block_bitmap);
  if (fs->metadata_fragments)
    carrier_free_fragments(fs->metadata_fragments);
  pthread_mutex_destroy(&fs->lock);
}

uint64_t fs_alloc_inode(Filesystem *fs) {
  pthread_mutex_lock(&fs->lock);

  for (uint64_t i = 1; i < MAX_INODES; i++) {
    if (!(fs->inode_bitmap[i / 8] & (1 << (i % 8)))) {
      fs->inode_bitmap[i / 8] |= (1 << (i % 8));

      Inode *inode = &fs->inode_table[i];
      memset(inode, 0, sizeof(Inode));
      inode->ino = i;

      pthread_mutex_unlock(&fs->lock);
      return i;
    }
  }

  pthread_mutex_unlock(&fs->lock);
  return 0;
}

void fs_free_inode(Filesystem *fs, uint64_t ino) {
  pthread_mutex_lock(&fs->lock);
  fs->inode_bitmap[ino / 8] &= ~(1 << (ino % 8));
  pthread_mutex_unlock(&fs->lock);
}

Inode *fs_get_inode(Filesystem *fs, uint64_t ino) {
  if (ino >= MAX_INODES)
    return NULL;
  return &fs->inode_table[ino];
}

uint64_t fs_alloc_block(Filesystem *fs) {
  pthread_mutex_lock(&fs->lock);

  for (uint64_t i = 0; i < fs->sb.block_count; i++) {
    if (!(fs->block_bitmap[i / 8] & (1 << (i % 8)))) {
      fs->block_bitmap[i / 8] |= (1 << (i % 8));
      pthread_mutex_unlock(&fs->lock);
      return i;
    }
  }

  pthread_mutex_unlock(&fs->lock);
  return 0;
}

void fs_free_block(Filesystem *fs, uint64_t block) {
  pthread_mutex_lock(&fs->lock);
  fs->block_bitmap[block / 8] &= ~(1 << (block % 8));
  pthread_mutex_unlock(&fs->lock);
}

int fs_read_dir(Filesystem *fs, uint64_t parent_ino, DirEntry **entries,
                size_t *count) {
  Inode *inode = fs_get_inode(fs, parent_ino);
  if (!inode || !S_ISDIR(inode->mode)) {
    return -ENOTDIR;
  }

  *count = inode->size / sizeof(DirEntry);
  if (*count == 0) {
    *entries = NULL;
    return 0;
  }

  *entries = malloc(inode->size);
  if (!*entries)
    return -ENOMEM;

  size_t bytes_read = 0;
  size_t block_idx = 0;

  while (bytes_read < inode->size && block_idx < 12) {
    uint64_t block_num = inode->block_pointers[block_idx];
    if (block_num == 0)
      break;

    size_t to_read = (inode->size - bytes_read < BLOCK_SIZE)
                         ? (inode->size - bytes_read)
                         : BLOCK_SIZE;

    memcpy(((uint8_t *)*entries) + bytes_read,
           ((uint8_t *)inode) + sizeof(Inode) + (block_idx * BLOCK_SIZE),
           to_read);

    bytes_read += to_read;
    block_idx++;
  }

  return 0;
}

int fs_add_dir_entry(Filesystem *fs, uint64_t parent_ino, const char *name,
                     uint64_t child_ino, uint8_t type) {
  Inode *parent = fs_get_inode(fs, parent_ino);
  if (!parent || !S_ISDIR(parent->mode)) {
    return -ENOTDIR;
  }

  DirEntry *entries;
  size_t count;

  if (fs_read_dir(fs, parent_ino, &entries, &count) != 0) {
    return -EIO;
  }

  pthread_mutex_lock(&fs->lock);

  size_t new_count = count + 1;
  DirEntry *new_entries = realloc(entries, new_count * sizeof(DirEntry));
  if (!new_entries) {
    free(entries);
    pthread_mutex_unlock(&fs->lock);
    return -ENOMEM;
  }

  new_entries[count].ino = child_ino;
  new_entries[count].type = type;
  strncpy(new_entries[count].name, name, MAX_FILENAME - 1);
  new_entries[count].name[MAX_FILENAME - 1] = '\0';

  size_t new_size = new_count * sizeof(DirEntry);
  size_t blocks_needed = (new_size + BLOCK_SIZE - 1) / BLOCK_SIZE;

  for (size_t i = 0; i < blocks_needed && i < 12; i++) {
    if (parent->block_pointers[i] == 0) {
      parent->block_pointers[i] = fs_alloc_block(fs);
      if (parent->block_pointers[i] == 0) {
        free(new_entries);
        pthread_mutex_unlock(&fs->lock);
        return -ENOSPC;
      }
    }
  }

  parent->size = new_size;
  parent->mtime = time(NULL);

  memcpy(((uint8_t *)parent) + sizeof(Inode), new_entries, new_size);

  free(new_entries);
  pthread_mutex_unlock(&fs->lock);
  return 0;
}

int fs_remove_dir_entry(Filesystem *fs, uint64_t parent_ino, const char *name) {
  Inode *parent = fs_get_inode(fs, parent_ino);
  if (!parent || !S_ISDIR(parent->mode)) {
    return -ENOTDIR;
  }

  pthread_mutex_lock(&fs->lock);
  parent->mtime = time(NULL);
  pthread_mutex_unlock(&fs->lock);

  return 0;
}

int fs_lookup(Filesystem *fs, uint64_t parent_ino, const char *name,
              uint64_t *ino) {
  DirEntry *entries;
  size_t count;

  if (fs_read_dir(fs, parent_ino, &entries, &count) != 0) {
    return -1;
  }

  for (size_t i = 0; i < count; i++) {
    if (strcmp(entries[i].name, name) == 0) {
      *ino = entries[i].ino;
      free(entries);
      return 0;
    }
  }

  if (entries)
    free(entries);
  return -ENOENT;
}
