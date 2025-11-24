package cluster

import (
	"hash/crc32"
	"sort"
	"strconv"
	"sync"
)

type Node struct {
	ID   string
	Addr string
}

type Ring struct {
	Nodes       map[string]*Node
	VNodes      map[uint32]string // Hash -> NodeID
	SortedHashes []uint32
	VNodeCount  int
	Replication int
	mu          sync.RWMutex
}

func NewRing(vnodeCount int, replication int) *Ring {
	return &Ring{
		Nodes:       make(map[string]*Node),
		VNodes:      make(map[uint32]string),
		SortedHashes: make([]uint32, 0),
		VNodeCount:  vnodeCount,
		Replication: replication,
	}
}

func (r *Ring) AddNode(id, addr string) {
	r.mu.Lock()
	defer r.mu.Unlock()

	node := &Node{ID: id, Addr: addr}
	r.Nodes[id] = node

	// Add VNodes
	for i := 0; i < r.VNodeCount; i++ {
		vnodeKey := id + "#" + strconv.Itoa(i)
		hash := crc32.ChecksumIEEE([]byte(vnodeKey))
		r.VNodes[hash] = id
		r.SortedHashes = append(r.SortedHashes, hash)
	}

	sort.Slice(r.SortedHashes, func(i, j int) bool {
		return r.SortedHashes[i] < r.SortedHashes[j]
	})
}

func (r *Ring) RemoveNode(id string) {
	r.mu.Lock()
	defer r.mu.Unlock()

	if _, ok := r.Nodes[id]; !ok {
		return
	}
	delete(r.Nodes, id)

	// Remove VNodes
	// This is inefficient (O(N)), but ring updates are rare
	newHashes := make([]uint32, 0)
	for _, h := range r.SortedHashes {
		if r.VNodes[h] != id {
			newHashes = append(newHashes, h)
		} else {
			delete(r.VNodes, h)
		}
	}
	r.SortedHashes = newHashes
}

// GetNodes returns the N nodes responsible for a key
func (r *Ring) GetNodes(key string) []*Node {
	r.mu.RLock()
	defer r.mu.RUnlock()

	if len(r.Nodes) == 0 {
		return nil
	}

	hash := crc32.ChecksumIEEE([]byte(key))
	
	// Find the first vnode >= hash
	idx := sort.Search(len(r.SortedHashes), func(i int) bool {
		return r.SortedHashes[i] >= hash
	})

	// Collect unique physical nodes
	nodes := make([]*Node, 0, r.Replication)
	seen := make(map[string]bool)

	// Walk the ring
	for i := 0; i < len(r.SortedHashes); i++ {
		// Wrap around
		currIdx := (idx + i) % len(r.SortedHashes)
		vnodeHash := r.SortedHashes[currIdx]
		nodeID := r.VNodes[vnodeHash]

		if !seen[nodeID] {
			nodes = append(nodes, r.Nodes[nodeID])
			seen[nodeID] = true
		}

		if len(nodes) >= r.Replication {
			break
		}
	}

	return nodes
}
