CC = gcc
CFLAGS = -Wall -Wextra -O3 -g -std=c11 -D_FILE_OFFSET_BITS=64
LDFLAGS = -lfuse -lpng -lcrypto -lpthread -lm

SRC_DIR = src
OBJ_DIR = obj
BIN_DIR = bin
TEST_DIR = tests

SOURCES = $(SRC_DIR)/carrier.c $(SRC_DIR)/stego.c $(SRC_DIR)/crypto.c \
          $(SRC_DIR)/metadata.c $(SRC_DIR)/recovery.c $(SRC_DIR)/ghostfs.c

OBJECTS = $(patsubst $(SRC_DIR)/%.c,$(OBJ_DIR)/%.o,$(SOURCES))

TEST_SOURCES = $(TEST_DIR)/test_stego.c $(TEST_DIR)/test_crypto.c $(TEST_DIR)/test_metadata.c
TEST_BINS = $(patsubst $(TEST_DIR)/%.c,$(BIN_DIR)/%,$(TEST_SOURCES))

TARGET = $(BIN_DIR)/ghostfs

all: $(TARGET)

$(TARGET): $(OBJECTS) | $(BIN_DIR)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

$(OBJ_DIR)/%.o: $(SRC_DIR)/%.c | $(OBJ_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(BIN_DIR)/%: $(TEST_DIR)/%.c $(filter-out $(OBJ_DIR)/ghostfs.o,$(OBJECTS)) | $(BIN_DIR)
	$(CC) $(CFLAGS) -o $@ $^ $(LDFLAGS)

$(BIN_DIR) $(OBJ_DIR):
	mkdir -p $@

test: $(TEST_BINS)
	@for test in $(TEST_BINS); do \
		echo "Running $$test..."; \
		$$test || exit 1; \
	done

valgrind: $(TARGET)
	valgrind --leak-check=full --show-leak-kinds=all --track-origins=yes $(TARGET)

stress: $(TARGET)
	cd $(TEST_DIR) && bash stress_test.sh

clean:
	rm -rf $(OBJ_DIR) $(BIN_DIR)

.PHONY: all test valgrind stress clean
