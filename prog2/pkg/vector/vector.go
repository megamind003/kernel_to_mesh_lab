package vector

import (
	"fmt"
	"sync"
)

// VectorClock represents causal history
type VectorClock struct {
	Versions map[string]uint64
	mu       sync.RWMutex
}

func NewVectorClock() *VectorClock {
	return &VectorClock{
		Versions: make(map[string]uint64),
	}
}

func (vc *VectorClock) Increment(nodeID string) {
	vc.mu.Lock()
	defer vc.mu.Unlock()
	vc.Versions[nodeID]++
}

func (vc *VectorClock) Merge(other *VectorClock) {
	vc.mu.Lock()
	defer vc.mu.Unlock()
	other.mu.RLock()
	defer other.mu.RUnlock()

	for node, ver := range other.Versions {
		if current, ok := vc.Versions[node]; !ok || ver > current {
			vc.Versions[node] = ver
		}
	}
}

func (vc *VectorClock) Compare(other *VectorClock) int {
	// Returns:
	// -1 if vc < other
	//  1 if vc > other
	//  0 if concurrent or equal
	
	vc.mu.RLock()
	defer vc.mu.RUnlock()
	other.mu.RLock()
	defer other.mu.RUnlock()

	hasGreater := false
	hasLess := false

	// Check all keys in vc
	for node, ver := range vc.Versions {
		otherVer := other.Versions[node]
		if ver > otherVer {
			hasGreater = true
		} else if ver < otherVer {
			hasLess = true
		}
	}

	// Check keys in other that are not in vc
	for node, otherVer := range other.Versions {
		if _, ok := vc.Versions[node]; !ok && otherVer > 0 {
			hasLess = true
		}
	}

	if hasGreater && hasLess {
		return 0 // Concurrent
	}
	if hasGreater {
		return 1
	}
	if hasLess {
		return -1
	}
	return 0 // Equal
}

func (vc *VectorClock) String() string {
	vc.mu.RLock()
	defer vc.mu.RUnlock()
	return fmt.Sprintf("%v", vc.Versions)
}
