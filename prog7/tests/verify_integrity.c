#include <openssl/md5.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

void compute_md5(const char *path, unsigned char *md5_out) {
  FILE *f = fopen(path, "rb");
  if (!f) {
    perror("fopen");
    exit(1);
  }

  MD5_CTX ctx;
  MD5_Init(&ctx);

  unsigned char buffer[8192];
  size_t bytes;
  while ((bytes = fread(buffer, 1, sizeof(buffer), f)) > 0) {
    MD5_Update(&ctx, buffer, bytes);
  }

  MD5_Final(md5_out, &ctx);
  fclose(f);
}

void print_md5(const unsigned char *md5) {
  for (int i = 0; i < MD5_DIGEST_LENGTH; i++) {
    printf("%02x", md5[i]);
  }
}

int compare_files(const char *path1, const char *path2) {
  unsigned char md5_1[MD5_DIGEST_LENGTH];
  unsigned char md5_2[MD5_DIGEST_LENGTH];

  compute_md5(path1, md5_1);
  compute_md5(path2, md5_2);

  return memcmp(md5_1, md5_2, MD5_DIGEST_LENGTH) == 0;
}

int main(int argc, char *argv[]) {
  if (argc != 3) {
    fprintf(stderr, "Usage: %s <file1> <file2>\\n", argv[0]);
    return 1;
  }

  printf("Computing MD5 hashes...\\n");

  unsigned char md5_1[MD5_DIGEST_LENGTH];
  unsigned char md5_2[MD5_DIGEST_LENGTH];

  compute_md5(argv[1], md5_1);
  compute_md5(argv[2], md5_2);

  printf("File 1: ");
  print_md5(md5_1);
  printf("\\n");

  printf("File 2: ");
  print_md5(md5_2);
  printf("\\n");

  if (memcmp(md5_1, md5_2, MD5_DIGEST_LENGTH) == 0) {
    printf("\\nMD5 hashes MATCH - Files are identical\\n");
    return 0;
  } else {
    printf("\\nMD5 hashes DIFFER - Files are different\\n");
    return 1;
  }
}
