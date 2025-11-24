package storage

import (
	"hash/fnv"
	"math"
)

// BloomFilter is a probabilistic data structure
type BloomFilter struct {
	bitset []bool
	k      uint // Number of hash functions
	m      uint // Size of bitset
}

func NewBloomFilter(n uint, p float64) *BloomFilter {
	// n: expected number of elements
	// p: desired false positive probability
	m := uint(math.Ceil(float64(n) * math.Log(p) / math.Log(1.0/math.Pow(2.0, math.Log(2.0)))))
	k := uint(math.Round(math.Log(2.0) * float64(m) / float64(n)))

	return &BloomFilter{
		bitset: make([]bool, m),
		k:      k,
		m:      m,
	}
}

func (bf *BloomFilter) Add(key []byte) {
	for i := uint(0); i < bf.k; i++ {
		idx := bf.hash(key, i) % bf.m
		bf.bitset[idx] = true
	}
}

func (bf *BloomFilter) MayContain(key []byte) bool {
	for i := uint(0); i < bf.k; i++ {
		idx := bf.hash(key, i) % bf.m
		if !bf.bitset[idx] {
			return false
		}
	}
	return true
}

// Simple double hashing
func (bf *BloomFilter) hash(key []byte, i uint) uint {
	h1 := fnv.New64a()
	h1.Write(key)
	hash1 := h1.Sum64()

	h2 := fnv.New64()
	h2.Write(key)
	hash2 := h2.Sum64()

	return uint(hash1 + uint64(i)*hash2)
}
