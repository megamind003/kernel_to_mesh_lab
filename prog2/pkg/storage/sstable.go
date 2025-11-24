package storage

import (
	"encoding/binary"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// SSTable represents an on-disk sorted string table
type SSTable struct {
	path string
}

// FlushMemTable writes the MemTable to an SSTable on disk
func FlushMemTable(mt *MemTable, dir string) (*SSTable, error) {
	// Generate filename
	filename := fmt.Sprintf("sstable-%d.sst", time.Now().UnixNano())
	path := filepath.Join(dir, filename)

	f, err := os.Create(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	// Create Bloom Filter
	// Estimate n from MemTable size (rough guess, assuming avg entry 100 bytes)
	n := uint(mt.Size() / 100)
	if n == 0 { n = 100 }
	bf := NewBloomFilter(n, 0.01)

	// Iterate and Write
	iter := mt.Iterator()
	for {
		k, v, ok := iter()
		if !ok {
			break
		}

		// Add to Bloom Filter
		bf.Add([]byte(k))

		// Write Key/Value
		// Format: [KeyLen][ValLen][Key][Value]
		keyLen := uint32(len(k))
		valLen := uint32(len(v))

		if err := binary.Write(f, binary.LittleEndian, keyLen); err != nil {
			return nil, err
		}
		if err := binary.Write(f, binary.LittleEndian, valLen); err != nil {
			return nil, err
		}
		if _, err := f.WriteString(k); err != nil {
			return nil, err
		}
		if _, err := f.Write(v); err != nil {
			return nil, err
		}
	}

	// TODO: Write Bloom Filter and Index at the end for optimized reads
	// For this prototype, we just write data.
	// Real LSM would write a footer with offsets.

	return &SSTable{path: path}, nil
}
