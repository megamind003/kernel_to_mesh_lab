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

  pthread_mutexattr_t attr;
  pthread_mutexattr_init(&attr);
  pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_RECURSIVE);
  pthread_mutex_init(&fs->lock, &attr);
  pthread_mutexattr_destroy(&attr);

  fs->sb.magic = MAGIC_NUMBER;
  fs->sb.version = 1;

  CryptoContext crypto_ctx;
  crypto_init(&crypto_ctx, password);
  memcpy(fs->sb.salt, crypto_ctx.salt, 16);
  crypto_destroy(&crypto_ctx);

  fs->inode_table = calloc(MAX_INODES, sizeof(Inode));
  fs->inode_bitmap = calloc(INODE_BITMAP_SIZE, 1);

  // Calculate fixed metadata size (without block_bitmap)
  size_t fixed_metadata =
      sizeof(Superblock) + (MAX_INODES * sizeof(Inode)) + INODE_BITMAP_SIZE;

  // Calculate max possible data blocks
  size_t total_capacity_bytes = pool->total_capacity / 8;
  size_t max_data_blocks = total_capacity_bytes / BLOCK_SIZE;

  // Iterate to find the right balance between data blocks and metadata
  // metadata_total = fixed_metadata + block_bitmap_size
  // data_space = data_blocks * BLOCK_SIZE
  // We need: data_space + metadata_total <= total_capacity_bytes

  size_t data_blocks = max_data_blocks;
  size_t metadata_total;
  size_t data_space;

  do {
    size_t block_bitmap_size = (data_blocks + 7) / 8;
    metadata_total = fixed_metadata + block_bitmap_size;
    data_space = data_blocks * BLOCK_SIZE;

    if (data_space + metadata_total <= total_capacity_bytes) {
      break; // Found a valid configuration
    }

    // Reduce data blocks and try again
    data_blocks--;
  } while (data_blocks > 0);

  if (data_blocks == 0) {
    fprintf(stderr, "Insufficient capacity for filesystem\n");
    fs_destroy(fs);
    return -1;
  }

  fprintf(stderr,
          "[DEBUG fs_init] Allocating %zu data blocks (%zu bytes), metadata: "
          "%zu bytes\n",
          data_blocks, data_space, metadata_total);

  // Pre-allocate space for data blocks
  Fragment *data_fragments = NULL;
  size_t data_frag_count = 0;

  if (carrier_allocate(pool, data_space, &data_fragments, &data_frag_count) !=
      0) {
    fprintf(stderr, "Failed to pre-allocate data block space\n");
    fs_destroy(fs);
    return -1;
  }

  // We don't need to track these fragments individually
  carrier_free_fragments(data_fragments);

  fs->sb.block_count = data_blocks;
  fs->sb.inode_count = MAX_INODES;
  fs->sb.root_inode = 1;
  fs->sb.created = time(NULL);
  fs->sb.modified = time(NULL);

  // Allocate block bitmap
  fs->block_bitmap = calloc((fs->sb.block_count + 7) / 8, 1);

  // Allocate space for metadata
  if (carrier_allocate(pool, metadata_total, &fs->metadata_fragments,
                       &fs->metadata_frag_count) != 0) {
    fprintf(stderr, "Failed to allocate space for metadata\n");
    fs_destroy(fs);
    return -1;
  }

  Inode *root = &fs->inode_table[fs->sb.root_inode];
  root->ino = fs->sb.root_inode;
  root->mode = S_IFDIR | 0755;
  root->uid = getuid();
  root->gid = getgid();
  root->size = 0;
  root->atime = root->mtime = root->ctime = time(NULL);
  root->nlink = 2;

  fs->inode_bitmap[fs->sb.root_inode / 8] |= (1 << (fs->sb.root_inode % 8));

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

  pthread_mutexattr_t attr;
  pthread_mutexattr_init(&attr);
  pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_RECURSIVE);
  pthread_mutex_init(&fs->lock, &attr);
  pthread_mutexattr_destroy(&attr);

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

int fs_read_dir(Filesystem *fs, CarrierPool *pool, CryptoContext *crypto,
                uint64_t parent_ino, DirEntry **entries, size_t *count) {
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

  uint8_t *indirect_block = NULL;

  while (bytes_read < inode->size) {
    uint64_t block_num = 0;

    if (block_idx < 12) {
      block_num = inode->block_pointers[block_idx];
    } else if (block_idx < 12 + 512) {
      if (inode->single_indirect == 0)
        break;

      if (!indirect_block) {
        indirect_block = malloc(BLOCK_SIZE);
        if (carrier_read_block(pool, inode->single_indirect, indirect_block) !=
            0) {
          free(*entries);
          return -EIO;
        }
      }
      uint64_t *indirect_pointers = (uint64_t *)indirect_block;
      block_num = indirect_pointers[block_idx - 12];
    } else {
      break;
    }

    if (block_num == 0)
      break;

    uint8_t block_data[BLOCK_SIZE];
    uint8_t decrypted[BLOCK_SIZE];

    if (carrier_read_block(pool, block_num, block_data) != 0) {
      if (indirect_block)
        free(indirect_block);
      free(*entries);
      return -EIO;
    }

    if (crypto_decrypt_block(crypto, block_num, block_data, decrypted,
                             BLOCK_SIZE) != 0) {
      if (indirect_block)
        free(indirect_block);
      free(*entries);
      return -EIO;
    }

    size_t to_read = (inode->size - bytes_read < BLOCK_SIZE)
                         ? (inode->size - bytes_read)
                         : BLOCK_SIZE;

    memcpy(((uint8_t *)*entries) + bytes_read, decrypted, to_read);

    bytes_read += to_read;
    block_idx++;
  }

  if (indirect_block)
    free(indirect_block);

  return 0;
}

int fs_add_dir_entry(Filesystem *fs, CarrierPool *pool, CryptoContext *crypto,
                     uint64_t parent_ino, const char *name, uint64_t child_ino,
                     uint8_t type) {
  Inode *parent = fs_get_inode(fs, parent_ino);
  if (!parent || !S_ISDIR(parent->mode)) {
    return -ENOTDIR;
  }

  DirEntry *entries;
  size_t count;

  if (fs_read_dir(fs, pool, crypto, parent_ino, &entries, &count) != 0) {
    return -EIO;
  }

  // Check if entry already exists
  for (size_t i = 0; i < count; i++) {
    if (strcmp(entries[i].name, name) == 0) {
      free(entries);
      return -EEXIST;
    }
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
  parent->size = new_size;
  parent->mtime = time(NULL);

  // Write back
  size_t bytes_written = 0;
  size_t block_idx = 0;
  uint8_t *indirect_block = NULL;
  int indirect_modified = 0;

  while (bytes_written < new_size) {
    uint64_t *block_ptr = NULL;

    if (block_idx < 12) {
      block_ptr = &parent->block_pointers[block_idx];
    } else if (block_idx < 12 + 512) {
      if (!indirect_block) {
        indirect_block = calloc(1, BLOCK_SIZE);
        if (parent->single_indirect != 0) {
          carrier_read_block(pool, parent->single_indirect, indirect_block);
        } else {
          parent->single_indirect = fs_alloc_block(fs);
          if (parent->single_indirect == 0) {
            free(new_entries);
            if (indirect_block)
              free(indirect_block);
            pthread_mutex_unlock(&fs->lock);
            return -ENOSPC;
          }
          indirect_modified = 1;
        }
      }
      uint64_t *indirect_pointers = (uint64_t *)indirect_block;
      block_ptr = &indirect_pointers[block_idx - 12];
      indirect_modified = 1;
    } else {
      break;
    }

    if (*block_ptr == 0) {
      *block_ptr = fs_alloc_block(fs);
      if (*block_ptr == 0) {
        free(new_entries);
        if (indirect_block)
          free(indirect_block);
        pthread_mutex_unlock(&fs->lock);
        return -ENOSPC;
      }
    }

    uint64_t block_num = *block_ptr;
    uint8_t block_data[BLOCK_SIZE];
    uint8_t decrypted[BLOCK_SIZE];
    memset(decrypted, 0, BLOCK_SIZE);

    size_t to_write = (new_size - bytes_written < BLOCK_SIZE)
                          ? (new_size - bytes_written)
                          : BLOCK_SIZE;

    memcpy(decrypted, ((uint8_t *)new_entries) + bytes_written, to_write);

    if (crypto_encrypt_block(crypto, block_num, decrypted, block_data,
                             BLOCK_SIZE) != 0) {
      free(new_entries);
      if (indirect_block)
        free(indirect_block);
      pthread_mutex_unlock(&fs->lock);
      return -EIO;
    }

    if (carrier_write_block(pool, block_num, block_data) != 0) {
      free(new_entries);
      if (indirect_block)
        free(indirect_block);
      pthread_mutex_unlock(&fs->lock);
      return -EIO;
    }

    bytes_written += to_write;
    block_idx++;
  }

  if (indirect_modified && parent->single_indirect != 0) {
    carrier_write_block(pool, parent->single_indirect, indirect_block);
  }

  if (indirect_block)
    free(indirect_block);

  free(new_entries);
  pthread_mutex_unlock(&fs->lock);
  return 0;
}

int fs_remove_dir_entry(Filesystem *fs, CarrierPool *pool,
                        CryptoContext *crypto, uint64_t parent_ino,
                        const char *name) {
  Inode *parent = fs_get_inode(fs, parent_ino);
  if (!parent || !S_ISDIR(parent->mode)) {
    return -ENOTDIR;
  }

  DirEntry *entries;
  size_t count;

  if (fs_read_dir(fs, pool, crypto, parent_ino, &entries, &count) != 0) {
    return -EIO;
  }

  int found = 0;
  for (size_t i = 0; i < count; i++) {
    if (strcmp(entries[i].name, name) == 0) {
      // Move last entry to this slot
      entries[i] = entries[count - 1];
      found = 1;
      break;
    }
  }

  if (!found) {
    free(entries);
    return -ENOENT;
  }

  pthread_mutex_lock(&fs->lock);

  size_t new_count = count - 1;
  size_t new_size = new_count * sizeof(DirEntry);
  parent->size = new_size;
  parent->mtime = time(NULL);

  // Write back (similar to add, but we can reuse logic or just copy-paste for
  // now)
  size_t bytes_written = 0;
  size_t block_idx = 0;
  uint8_t *indirect_block = NULL;
  int indirect_modified = 0;

  while (bytes_written < new_size) {
    uint64_t *block_ptr = NULL;

    if (block_idx < 12) {
      block_ptr = &parent->block_pointers[block_idx];
    } else if (block_idx < 12 + 512) {
      if (!indirect_block) {
        indirect_block = calloc(1, BLOCK_SIZE);
        if (parent->single_indirect != 0) {
          carrier_read_block(pool, parent->single_indirect, indirect_block);
        }
      }
      uint64_t *indirect_pointers = (uint64_t *)indirect_block;
      block_ptr = &indirect_pointers[block_idx - 12];
    } else {
      break;
    }

    // Should exist
    uint64_t block_num = *block_ptr;
    uint8_t block_data[BLOCK_SIZE];
    uint8_t decrypted[BLOCK_SIZE];
    memset(decrypted, 0, BLOCK_SIZE);

    size_t to_write = (new_size - bytes_written < BLOCK_SIZE)
                          ? (new_size - bytes_written)
                          : BLOCK_SIZE;

    memcpy(decrypted, ((uint8_t *)entries) + bytes_written, to_write);

    crypto_encrypt_block(crypto, block_num, decrypted, block_data, BLOCK_SIZE);
    carrier_write_block(pool, block_num, block_data);

    bytes_written += to_write;
    block_idx++;
  }

  // Free unused blocks if size shrank significantly (optional for now, but good
  // for correctness)
  // ... (skipping explicit block freeing for simplicity, but we should handle
  // it ideally)

  if (indirect_block)
    free(indirect_block);

  free(entries);
  pthread_mutex_unlock(&fs->lock);
  return 0;
}

int fs_lookup(Filesystem *fs, CarrierPool *pool, CryptoContext *crypto,
              uint64_t parent_ino, const char *name, uint64_t *ino) {
  DirEntry *entries;
  size_t count;

  if (fs_read_dir(fs, pool, crypto, parent_ino, &entries, &count) != 0) {
    return -1;
  }

  for (size_t i = 0; i < count; i++) {
    if (strcmp(entries[i].name, name) == 0) {
      *ino = entries[i].ino;
      free(entries);
      return 0;
    }
  }

  free(entries);
  return -ENOENT;
}
