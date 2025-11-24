#ifndef CRYPTO_H
#define CRYPTO_H

#include <stddef.h>
#include <stdint.h>

#define KEY_SIZE 32
#define SALT_SIZE 16
#define IV_SIZE 16

typedef struct {
  uint8_t key[KEY_SIZE];
  uint8_t salt[SALT_SIZE];
} CryptoContext;

int crypto_init(CryptoContext *ctx, const char *password);
void crypto_destroy(CryptoContext *ctx);

int crypto_encrypt_block(CryptoContext *ctx, uint64_t block_num,
                         const uint8_t *plaintext, uint8_t *ciphertext,
                         size_t len);
int crypto_decrypt_block(CryptoContext *ctx, uint64_t block_num,
                         const uint8_t *ciphertext, uint8_t *plaintext,
                         size_t len);

int crypto_derive_key(const char *password, const uint8_t *salt, uint8_t *key);

#endif
