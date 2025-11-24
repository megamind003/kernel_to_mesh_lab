package storage

import (
	"encoding/binary"
	"io"
	"os"
	"sync"
)

// WAL manages the Write-Ahead Log
type WAL struct {
	file *os.File
	mu   sync.Mutex
}

func OpenWAL(path string) (*WAL, error) {
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_RDWR, 0644)
	if err != nil {
		return nil, err
	}
	return &WAL{file: f}, nil
}

// Write appends a key-value pair to the log
// Format: [KeyLen(4)][ValLen(4)][Key][Value]
func (w *WAL) Write(key string, value []byte) error {
	w.mu.Lock()
	defer w.mu.Unlock()

	keyLen := uint32(len(key))
	valLen := uint32(len(value))

	if err := binary.Write(w.file, binary.LittleEndian, keyLen); err != nil {
		return err
	}
	if err := binary.Write(w.file, binary.LittleEndian, valLen); err != nil {
		return err
	}
	if _, err := w.file.WriteString(key); err != nil {
		return err
	}
	if _, err := w.file.Write(value); err != nil {
		return err
	}

	// Ensure durability
	return w.file.Sync()
}

// Replay reads the log and applies entries to the MemTable
func (w *WAL) Replay(mt *MemTable) error {
	w.mu.Lock()
	defer w.mu.Unlock()

	// Seek to beginning
	if _, err := w.file.Seek(0, 0); err != nil {
		return err
	}

	for {
		var keyLen uint32
		if err := binary.Read(w.file, binary.LittleEndian, &keyLen); err != nil {
			if err == io.EOF {
				break
			}
			return err
		}

		var valLen uint32
		if err := binary.Read(w.file, binary.LittleEndian, &valLen); err != nil {
			return err
		}

		keyBuf := make([]byte, keyLen)
		if _, err := io.ReadFull(w.file, keyBuf); err != nil {
			return err
		}

		valBuf := make([]byte, valLen)
		if _, err := io.ReadFull(w.file, valBuf); err != nil {
			return err
		}

		mt.Put(string(keyBuf), valBuf)
	}

	// Seek back to end for appending
	if _, err := w.file.Seek(0, 2); err != nil {
		return err
	}

	return nil
}

func (w *WAL) Close() error {
	return w.file.Close()
}

func (w *WAL) Clear() error {
	w.mu.Lock()
	defer w.mu.Unlock()
	
	if err := w.file.Truncate(0); err != nil {
		return err
	}
	_, err := w.file.Seek(0, 0)
	return err
}
