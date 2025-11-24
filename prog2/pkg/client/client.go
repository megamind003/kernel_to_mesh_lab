package client

import (
	"fmt"
	"hydra/pkg/cluster"
	"hydra/pkg/storage"
)

type Client struct {
	Ring *cluster.Ring
	// In a real system, client would connect to nodes via TCP
	// Here we simulate by holding references to "Nodes" which are just storage engines
	StorageEngines map[string]*storage.MemTable
}

func NewClient(ring *cluster.Ring, engines map[string]*storage.MemTable) *Client {
	return &Client{
		Ring:           ring,
		StorageEngines: engines,
	}
}

func (c *Client) Put(key string, value []byte, consistencyLevel string) error {
	nodes := c.Ring.GetNodes(key)
	if len(nodes) == 0 {
		return fmt.Errorf("no nodes available")
	}

	// Write to N replicas
	successCount := 0
	for _, node := range nodes {
		if engine, ok := c.StorageEngines[node.ID]; ok {
			engine.Put(key, value)
			successCount++
			fmt.Printf("[CLIENT] Wrote %s to %s\n", key, node.ID)
		}
	}

	// Check consistency
	required := 1
	if consistencyLevel == "QUORUM" {
		required = (len(nodes) / 2) + 1
	} else if consistencyLevel == "ALL" {
		required = len(nodes)
	}

	if successCount >= required {
		return nil
	}
	return fmt.Errorf("consistency level not met: got %d, needed %d", successCount, required)
}

func (c *Client) Get(key string, consistencyLevel string) ([]byte, bool) {
	nodes := c.Ring.GetNodes(key)
	if len(nodes) == 0 {
		return nil, false
	}

	// Read from replicas (Simple Read-Repair could happen here)
	// For now, just return first success
	for _, node := range nodes {
		if engine, ok := c.StorageEngines[node.ID]; ok {
			if val, ok := engine.Get(key); ok {
				fmt.Printf("[CLIENT] Read %s from %s\n", key, node.ID)
				return val, true
			}
		}
	}
	return nil, false
}
