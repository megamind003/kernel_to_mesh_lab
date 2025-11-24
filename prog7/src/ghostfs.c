#define _POSIX_C_SOURCE 200809L
#define _XOPEN_SOURCE 700
#define FUSE_USE_VERSION 31

#include <assert.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <fuse.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "carrier.h"
#include "crypto.h"
#include "metadata.h"
#include "recovery.h"
#include "stego.h"

#ifndef DT_REG
#define DT_REG 8
#endif

typedef struct {
  CarrierPool pool;
  Filesystem fs;
  CryptoContext crypto;
  char *password;
} GhostFSContext;

static GhostFSContext *get_context() {
  return (GhostFSContext *)fuse_get_context()->private_data;
}

static int ghost_getattr(const char *path, struct stat *stbuf) {
  GhostFSContext *ctx = get_context();
  memset(stbuf, 0, sizeof(struct stat));

  if (strcmp(path, "/") == 0) {
    Inode *root = fs_get_inode(&ctx->fs, ctx->fs.sb.root_inode);
    stbuf->st_mode = root->mode;
    stbuf->st_nlink = root->nlink;
    stbuf->st_size = root->size;
    stbuf->st_uid = root->uid;
    stbuf->st_gid = root->gid;
    stbuf->st_atime = root->atime;
    stbuf->st_mtime = root->mtime;
    stbuf->st_ctime = root->ctime;
    return 0;
  }

  const char *name = path + 1;
  uint64_t ino;

  if (fs_lookup(&ctx->fs, &ctx->pool, &ctx->crypto, ctx->fs.sb.root_inode, name,
                &ino) != 0) {
    return -ENOENT;
  }

  Inode *inode = fs_get_inode(&ctx->fs, ino);
  if (!inode)
    return -ENOENT;

  stbuf->st_ino = inode->ino;
  stbuf->st_mode = inode->mode;
  stbuf->st_nlink = inode->nlink;
  stbuf->st_size = inode->size;
  stbuf->st_uid = inode->uid;
  stbuf->st_gid = inode->gid;
  stbuf->st_atime = inode->atime;
  stbuf->st_mtime = inode->mtime;
  stbuf->st_ctime = inode->ctime;

  return 0;
}

static int ghost_readdir(const char *path, void *buf, fuse_fill_dir_t filler,
                         off_t offset, struct fuse_file_info *fi) {
  (void)offset;
  (void)fi;

  GhostFSContext *ctx = get_context();
  const char *name = path + 1; // Skip leading /
  uint64_t ino;

  if (strcmp(path, "/") == 0) {
    ino = ctx->fs.sb.root_inode;
  } else {
    if (fs_lookup(&ctx->fs, &ctx->pool, &ctx->crypto, ctx->fs.sb.root_inode,
                  name, &ino) != 0) {
      return -ENOENT;
    }
  }

  filler(buf, ".", NULL, 0);
  filler(buf, "..", NULL, 0);

  DirEntry *entries;
  size_t count;

  if (fs_read_dir(&ctx->fs, &ctx->pool, &ctx->crypto, ino, &entries, &count) !=
      0) {
    return -EIO;
  }

  for (size_t i = 0; i < count; i++) {
    filler(buf, entries[i].name, NULL, 0);
  }

  if (entries)
    free(entries);

  return 0;
}

static int ghost_open(const char *path, struct fuse_file_info *fi) {
  GhostFSContext *ctx = get_context();
  const char *name = path + 1;
  uint64_t ino;

  if (fs_lookup(&ctx->fs, &ctx->pool, &ctx->crypto, ctx->fs.sb.root_inode, name,
                &ino) != 0) {
    return -ENOENT;
  }

  Inode *inode = fs_get_inode(&ctx->fs, ino);
  if (!inode)
    return -ENOENT;
  if (S_ISDIR(inode->mode))
    return -EISDIR;

  return 0;
}

static int ghost_read(const char *path, char *buf, size_t size, off_t offset,
                      struct fuse_file_info *fi) {
  (void)fi;

  GhostFSContext *ctx = get_context();
  const char *name = path + 1;
  uint64_t ino;

  if (fs_lookup(&ctx->fs, &ctx->pool, &ctx->crypto, ctx->fs.sb.root_inode, name,
                &ino) != 0) {
    return -ENOENT;
  }

  Inode *inode = fs_get_inode(&ctx->fs, ino);
  if (!inode)
    return -ENOENT;

  if (offset >= (off_t)inode->size) {
    return 0;
  }

  if (offset + size > inode->size) {
    size = inode->size - offset;
  }

  uint64_t start_block = offset / BLOCK_SIZE;
  uint64_t end_block = (offset + size - 1) / BLOCK_SIZE;
  size_t bytes_read = 0;

  for (uint64_t i = start_block; i <= end_block; i++) {
    uint64_t block_num = 0;

    if (i < 12) {
      block_num = inode->block_pointers[i];
    } else if (i < 12 + 512) {
      if (inode->single_indirect == 0)
        break;

      uint8_t indirect_block[BLOCK_SIZE];
      if (carrier_read_block(&ctx->pool, inode->single_indirect,
                             indirect_block) != 0) {
        return -EIO;
      }

      uint64_t *indirect_pointers = (uint64_t *)indirect_block;
      block_num = indirect_pointers[i - 12];
    } else {
      break;
    }

    if (block_num == 0)
      break;

    uint8_t block_data[BLOCK_SIZE];
    uint8_t decrypted[BLOCK_SIZE];

    if (carrier_read_block(&ctx->pool, block_num, block_data) != 0) {
      return -EIO;
    }

    if (crypto_decrypt_block(&ctx->crypto, block_num, block_data, decrypted,
                             BLOCK_SIZE) != 0) {
      return -EIO;
    }

    size_t block_offset = (i == start_block) ? (offset % BLOCK_SIZE) : 0;
    size_t to_copy = BLOCK_SIZE - block_offset;

    if (bytes_read + to_copy > size) {
      to_copy = size - bytes_read;
    }

    memcpy(buf + bytes_read, decrypted + block_offset, to_copy);
    bytes_read += to_copy;
  }

  inode->atime = time(NULL);

  return bytes_read;
}

static int ghost_write(const char *path, const char *buf, size_t size,
                       off_t offset, struct fuse_file_info *fi) {
  (void)fi;

  GhostFSContext *ctx = get_context();
  const char *name = path + 1;
  uint64_t ino;

  if (fs_lookup(&ctx->fs, &ctx->pool, &ctx->crypto, ctx->fs.sb.root_inode, name,
                &ino) != 0) {
    return -ENOENT;
  }

  Inode *inode = fs_get_inode(&ctx->fs, ino);
  if (!inode)
    return -ENOENT;

  uint64_t start_block = offset / BLOCK_SIZE;
  uint64_t end_block = (offset + size - 1) / BLOCK_SIZE;
  size_t bytes_written = 0;

  uint8_t *indirect_block = NULL;
  int indirect_modified = 0;

  for (uint64_t i = start_block; i <= end_block; i++) {
    if (i >= 12 + 512) {
      if (indirect_block)
        free(indirect_block);
      return -EFBIG;
    }

    uint64_t *block_ptr = NULL;

    if (i < 12) {
      block_ptr = &inode->block_pointers[i];
    } else {
      if (!indirect_block) {
        indirect_block = calloc(1, BLOCK_SIZE);
        if (inode->single_indirect != 0) {
          carrier_read_block(&ctx->pool, inode->single_indirect,
                             indirect_block);
        }
      }

      if (inode->single_indirect == 0) {
        inode->single_indirect = fs_alloc_block(&ctx->fs);
        if (inode->single_indirect == 0) {
          free(indirect_block);
          return -ENOSPC;
        }
      }

      uint64_t *indirect_pointers = (uint64_t *)indirect_block;
      block_ptr = &indirect_pointers[i - 12];
      indirect_modified = 1;
    }

    if (*block_ptr == 0) {
      *block_ptr = fs_alloc_block(&ctx->fs);
      if (*block_ptr == 0) {
        if (indirect_block)
          free(indirect_block);
        return -ENOSPC;
      }
    }

    uint64_t block_num = *block_ptr;
    uint8_t block_data[BLOCK_SIZE];
    uint8_t decrypted[BLOCK_SIZE];
    uint8_t encrypted[BLOCK_SIZE];

    if (i == start_block || i == end_block) {
      if (carrier_read_block(&ctx->pool, block_num, block_data) == 0) {
        crypto_decrypt_block(&ctx->crypto, block_num, block_data, decrypted,
                             BLOCK_SIZE);
      } else {
        memset(decrypted, 0, BLOCK_SIZE);
      }
    } else {
      memset(decrypted, 0, BLOCK_SIZE);
    }

    size_t block_offset = (i == start_block) ? (offset % BLOCK_SIZE) : 0;
    size_t to_write = BLOCK_SIZE - block_offset;

    if (bytes_written + to_write > size) {
      to_write = size - bytes_written;
    }

    memcpy(decrypted + block_offset, buf + bytes_written, to_write);

    if (crypto_encrypt_block(&ctx->crypto, block_num, decrypted, encrypted,
                             BLOCK_SIZE) != 0) {
      if (indirect_block)
        free(indirect_block);
      return -EIO;
    }

    if (carrier_write_block(&ctx->pool, block_num, encrypted) != 0) {
      if (indirect_block)
        free(indirect_block);
      return -EIO;
    }

    bytes_written += to_write;
  }

  if (indirect_modified && inode->single_indirect != 0) {
    if (carrier_write_block(&ctx->pool, inode->single_indirect,
                            indirect_block) != 0) {
      free(indirect_block);
      return -EIO;
    }
  }

  if (indirect_block)
    free(indirect_block);

  if (offset + bytes_written > inode->size) {
    inode->size = offset + bytes_written;
  }

  inode->mtime = inode->ctime = time(NULL);
  fs_sync(&ctx->fs, &ctx->pool);

  return bytes_written;
}

static int ghost_create(const char *path, mode_t mode,
                        struct fuse_file_info *fi) {
  (void)fi;

  GhostFSContext *ctx = get_context();
  const char *name = path + 1;

  fprintf(stderr, "[DEBUG ghost_create] Creating file: %s\n", name);

  uint64_t ino = fs_alloc_inode(&ctx->fs);
  if (ino == 0) {
    fprintf(stderr, "[DEBUG ghost_create] Failed to allocate inode\n");
    return -ENOSPC;
  }
  fprintf(stderr, "[DEBUG ghost_create] Allocated inode: %lu\n", ino);

  Inode *inode = fs_get_inode(&ctx->fs, ino);
  inode->mode = mode | S_IFREG;
  inode->uid = getuid();
  inode->gid = getgid();
  inode->size = 0;
  inode->atime = inode->mtime = inode->ctime = time(NULL);
  inode->nlink = 1;

  fprintf(stderr, "[DEBUG ghost_create] Adding directory entry...\n");

  if (fs_add_dir_entry(&ctx->fs, &ctx->pool, &ctx->crypto,
                       ctx->fs.sb.root_inode, name, ino, DT_REG) != 0) {
    fprintf(stderr, "[DEBUG ghost_create] Failed to add directory entry\n");
    fs_free_inode(&ctx->fs, ino);
    return -EIO;
  }

  fprintf(stderr, "[DEBUG ghost_create] Syncing filesystem...\n");

  fs_sync(&ctx->fs, &ctx->pool);

  fprintf(stderr, "[DEBUG ghost_create] File created successfully\n");
  return 0;
}

static int ghost_unlink(const char *path) {
  GhostFSContext *ctx = get_context();
  const char *name = path + 1;
  uint64_t ino;

  if (fs_lookup(&ctx->fs, &ctx->pool, &ctx->crypto, ctx->fs.sb.root_inode, name,
                &ino) != 0) {
    return -ENOENT;
  }

  Inode *inode = fs_get_inode(&ctx->fs, ino);
  if (!inode)
    return -ENOENT;

  for (int i = 0; i < 12 && inode->block_pointers[i] != 0; i++) {
    fs_free_block(&ctx->fs, inode->block_pointers[i]);
  }

  fs_remove_dir_entry(&ctx->fs, &ctx->pool, &ctx->crypto, ctx->fs.sb.root_inode,
                      name);
  fs_free_inode(&ctx->fs, ino);
  fs_sync(&ctx->fs, &ctx->pool);

  return 0;
}

static int ghost_mknod(const char *path, mode_t mode, dev_t dev) {
  (void)dev;

  fprintf(stderr, "[DEBUG ghost_mknod] Called for: %s, mode: %o\n", path, mode);

  // For regular files, delegate to create
  if (S_ISREG(mode)) {
    return ghost_create(path, mode, NULL);
  }

  // We don't support other node types
  return -ENOTSUP;
}

static int ghost_chmod(const char *path, mode_t mode) {
  GhostFSContext *ctx = get_context();

  if (strcmp(path, "/") == 0) {
    Inode *root = fs_get_inode(&ctx->fs, ctx->fs.sb.root_inode);
    root->mode = (root->mode & S_IFMT) | (mode & 0777);
    return 0;
  }

  const char *name = path + 1;
  uint64_t ino;

  if (fs_lookup(&ctx->fs, &ctx->pool, &ctx->crypto, ctx->fs.sb.root_inode, name,
                &ino) != 0) {
    return -ENOENT;
  }

  Inode *inode = fs_get_inode(&ctx->fs, ino);
  if (!inode)
    return -ENOENT;

  inode->mode = (inode->mode & S_IFMT) | (mode & 0777);
  inode->ctime = time(NULL);

  return 0;
}

static void *ghost_init(struct fuse_conn_info *conn) {
  (void)conn;
  return fuse_get_context()->private_data;
}

static void ghost_destroy(void *private_data) {
  GhostFSContext *ctx = (GhostFSContext *)private_data;

  fs_sync(&ctx->fs, &ctx->pool);
  fs_destroy(&ctx->fs);
  carrier_pool_destroy(&ctx->pool);
  crypto_destroy(&ctx->crypto);

  if (ctx->password) {
    memset(ctx->password, 0, strlen(ctx->password));
    free(ctx->password);
  }

  free(ctx);
}

static struct fuse_operations ghost_ops = {
    .getattr = ghost_getattr,
    .readdir = ghost_readdir,
    .open = ghost_open,
    .read = ghost_read,
    .write = ghost_write,
    .create = ghost_create,
    .mknod = ghost_mknod,
    .chmod = ghost_chmod,
    .unlink = ghost_unlink,
    .init = ghost_init,
    .destroy = ghost_destroy,
};

int main(int argc, char *argv[]) {
  if (argc < 3) {
    fprintf(stderr, "Usage: %s <host_dir> <mountpoint> [fuse_options]\n",
            argv[0]);
    return 1;
  }

  GhostFSContext *ctx = calloc(1, sizeof(GhostFSContext));
  if (!ctx) {
    fprintf(stderr, "Failed to allocate context\n");
    return 1;
  }

  printf("Initializing carrier pool from: %s\n", argv[1]);
  if (carrier_pool_init(&ctx->pool, argv[1]) != 0) {
    fprintf(stderr, "Failed to initialize carrier pool\n");
    free(ctx);
    return 1;
  }

  // Parse password from arguments or environment
  const char *env_pass = getenv("GHOSTFS_PASSWORD");
  if (env_pass) {
    ctx->password = strdup(env_pass);
  } else {
    // Check for -o password=... in args
    for (int i = 3; i < argc; i++) {
      if (strncmp(argv[i], "-o", 2) == 0) {
        char *opts = strdup(argv[i] + 2);
        if (strlen(opts) == 0 && i + 1 < argc) {
          free(opts);
          opts = strdup(argv[i + 1]);
          i++; // Skip the next argument as it was consumed
        }

        char *token = strtok(opts, ",");
        while (token) {
          if (strncmp(token, "password=", 9) == 0) {
            ctx->password = strdup(token + 9);
            break;
          }
          token = strtok(NULL, ",");
        }
        free(opts);
        if (ctx->password)
          break;
      } else if (strncmp(argv[i], "password=", 9) == 0) {
        ctx->password = strdup(argv[i] + 9);
        break;
      }
    }
  }

  if (!ctx->password) {
    ctx->password = strdup("ghostfs_default_password");
    printf("Warning: Using default password. Set GHOSTFS_PASSWORD env var or "
           "use -o password=...\n");
  }

  printf("Initializing crypto...\n");
  if (crypto_init(&ctx->crypto, ctx->password) != 0) {
    fprintf(stderr, "Failed to initialize crypto: Argon2id error\n");
    carrier_pool_destroy(&ctx->pool);
    free(ctx);
    return 1;
  }

  printf("Initializing filesystem...\n");
  if (fs_init(&ctx->fs, &ctx->pool, ctx->password) != 0) {
    fprintf(stderr, "Failed to initialize filesystem\n");
    crypto_destroy(&ctx->crypto);
    carrier_pool_destroy(&ctx->pool);
    free(ctx);
    return 1;
  }

  printf("Mounting GhostFS at: %s\n", argv[2]);

  char *fuse_argv[argc];
  int fuse_argc = 0;
  fuse_argv[fuse_argc++] = argv[0];
  fuse_argv[fuse_argc++] = argv[2];

  for (int i = 3; i < argc; i++) {
    // Filter out password option to avoid FUSE error
    if (strncmp(argv[i], "password=", 9) != 0 &&
        (strncmp(argv[i], "-o", 2) != 0 ||
         (i + 1 < argc && strncmp(argv[i + 1], "password=", 9) != 0 &&
          strstr(argv[i + 1], "password=") == NULL))) {
      fuse_argv[fuse_argc++] = argv[i];
    } else if (strncmp(argv[i], "-o", 2) == 0 && i + 1 < argc &&
               strstr(argv[i + 1], "password=") != NULL) {
      // If -o is followed by password=, skip both
      i++;
    } else if (strncmp(argv[i], "-o", 2) == 0) {
      // If -o contains password= within the same arg
      char *opts_copy = strdup(argv[i] + 2);
      char *token = strtok(opts_copy, ",");
      int found_password_in_opts = 0;
      while (token) {
        if (strncmp(token, "password=", 9) == 0) {
          found_password_in_opts = 1;
          break;
        }
        token = strtok(NULL, ",");
      }
      free(opts_copy);
      if (!found_password_in_opts) {
        fuse_argv[fuse_argc++] = argv[i];
      }
    }
  }

  int ret = fuse_main(fuse_argc, fuse_argv, &ghost_ops, ctx);

  return ret;
}
