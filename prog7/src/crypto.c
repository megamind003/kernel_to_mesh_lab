#include "crypto.h"
#include <openssl/evp.h>
#include <openssl/kdf.h>
#include <openssl/rand.h>
#include <stdio.h>
#include <string.h>

int crypto_derive_key(const char *password, const uint8_t *salt, uint8_t *key) {
  if (PKCS5_PBKDF2_HMAC(password, strlen(password), salt, SALT_SIZE, 100000,
                        EVP_sha256(), KEY_SIZE, key) != 1) {
    fprintf(stderr, "PBKDF2 derivation failed\n");
    return -1;
  }
  return 0;
}

int crypto_init(CryptoContext *ctx, const char *password) {
  if (RAND_bytes(ctx->salt, SALT_SIZE) != 1) {
    return -1;
  }

  return crypto_derive_key(password, ctx->salt, ctx->key);
}

void crypto_destroy(CryptoContext *ctx) {
  memset(ctx->key, 0, KEY_SIZE);
  memset(ctx->salt, 0, SALT_SIZE);
}

int crypto_encrypt_block(CryptoContext *ctx, uint64_t block_num,
                         const uint8_t *plaintext, uint8_t *ciphertext,
                         size_t len) {
  EVP_CIPHER_CTX *cipher_ctx = EVP_CIPHER_CTX_new();
  if (!cipher_ctx)
    return -1;

  uint8_t iv[IV_SIZE];
  memset(iv, 0, IV_SIZE);
  memcpy(iv, &block_num, sizeof(block_num));

  if (EVP_EncryptInit_ex(cipher_ctx, EVP_aes_256_xts(), NULL, ctx->key, iv) !=
      1) {
    EVP_CIPHER_CTX_free(cipher_ctx);
    return -1;
  }

  int out_len;
  if (EVP_EncryptUpdate(cipher_ctx, ciphertext, &out_len, plaintext, len) !=
      1) {
    EVP_CIPHER_CTX_free(cipher_ctx);
    return -1;
  }

  int final_len;
  if (EVP_EncryptFinal_ex(cipher_ctx, ciphertext + out_len, &final_len) != 1) {
    EVP_CIPHER_CTX_free(cipher_ctx);
    return -1;
  }

  EVP_CIPHER_CTX_free(cipher_ctx);
  return 0;
}

int crypto_decrypt_block(CryptoContext *ctx, uint64_t block_num,
                         const uint8_t *ciphertext, uint8_t *plaintext,
                         size_t len) {
  EVP_CIPHER_CTX *cipher_ctx = EVP_CIPHER_CTX_new();
  if (!cipher_ctx)
    return -1;

  uint8_t iv[IV_SIZE];
  memset(iv, 0, IV_SIZE);
  memcpy(iv, &block_num, sizeof(block_num));

  if (EVP_DecryptInit_ex(cipher_ctx, EVP_aes_256_xts(), NULL, ctx->key, iv) !=
      1) {
    EVP_CIPHER_CTX_free(cipher_ctx);
    return -1;
  }

  int out_len;
  if (EVP_DecryptUpdate(cipher_ctx, plaintext, &out_len, ciphertext, len) !=
      1) {
    EVP_CIPHER_CTX_free(cipher_ctx);
    return -1;
  }

  int final_len;
  if (EVP_DecryptFinal_ex(cipher_ctx, plaintext + out_len, &final_len) != 1) {
    EVP_CIPHER_CTX_free(cipher_ctx);
    return -1;
  }

  EVP_CIPHER_CTX_free(cipher_ctx);
  return 0;
}
