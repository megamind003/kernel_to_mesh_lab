package storage

import (
	"sort"
	"sync"
)

// MemTable is an in-memory sorted key-value store
type MemTable struct {
	data map[string][]byte
	keys []string // Sorted keys for iteration
	size int64    // Approximate size in bytes
	mu   sync.RWMutex
}

func NewMemTable() *MemTable {
	return &MemTable{
		data: make(map[string][]byte),
		keys: make([]string, 0),
		size: 0,
	}
}

// Put adds or updates a key-value pair
func (m *MemTable) Put(key string, value []byte) {
	m.mu.Lock()
	defer m.mu.Unlock()

	if _, exists := m.data[key]; !exists {
		m.keys = append(m.keys, key)
		sort.Strings(m.keys) // Keep keys sorted (O(N log N) - optimization needed for prod)
	}
	
	// Update size estimation (rough)
	m.size += int64(len(key) + len(value))
	m.data[key] = value
}

// Get retrieves a value by key
func (m *MemTable) Get(key string) ([]byte, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	val, ok := m.data[key]
	return val, ok
}

// Size returns the approximate size in bytes
func (m *MemTable) Size() int64 {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.size
}

// Iterator returns all key-value pairs in sorted order
// Useful for flushing to SSTable
func (m *MemTable) Iterator() func() (string, []byte, bool) {
	m.mu.RLock()
	// Note: This locks the memtable for the duration of iteration setup
	// In a real system, we might want to snapshot or copy
	defer m.mu.RUnlock()

	// Copy keys/data to avoid holding lock during iteration if caller is slow
	// For now, we'll just return a closure that iterates over a snapshot
	keys := make([]string, len(m.keys))
	copy(keys, m.keys)
	data := make(map[string][]byte, len(m.data))
	for k, v := range m.data {
		data[k] = v
	}

	i := 0
	return func() (string, []byte, bool) {
		if i >= len(keys) {
			return "", nil, false
		}
		k := keys[i]
		v := data[k]
		i++
		return k, v, true
	}
}

// Clear resets the memtable
func (m *MemTable) Clear() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.data = make(map[string][]byte)
	m.keys = make([]string, 0)
	m.size = 0
}
