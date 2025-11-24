package scheduler

import (
	"fmt"
)

type Node struct {
	ID          string
	TotalMemory int
	UsedMemory  int
	TotalPids   int
	UsedPids    int
	Labels      map[string]string
}

type Job struct {
	ID          string
	MemoryReq   int
	PidsReq     int
	Affinity    map[string]string // Label Key -> Value required on Node
}

// Scheduler decides where to place jobs
type Scheduler struct {
	Nodes map[string]*Node
}

func NewScheduler() *Scheduler {
	return &Scheduler{
		Nodes: make(map[string]*Node),
	}
}

func (s *Scheduler) AddNode(n *Node) {
	s.Nodes[n.ID] = n
}

// SelectNode finds the best node for the job (Bin Packing / First Fit)
func (s *Scheduler) SelectNode(job Job) (*Node, error) {
	// Simple First Fit with Affinity check
	for _, node := range s.Nodes {
		// 1. Check Resources
		if (node.TotalMemory - node.UsedMemory) < job.MemoryReq {
			continue
		}
		if (node.TotalPids - node.UsedPids) < job.PidsReq {
			continue
		}

		// 2. Check Affinity
		matchesAffinity := true
		for key, val := range job.Affinity {
			if nodeVal, ok := node.Labels[key]; !ok || nodeVal != val {
				matchesAffinity = false
				break
			}
		}
		if !matchesAffinity {
			continue
		}

		// Found a candidate
		return node, nil
	}

	return nil, fmt.Errorf("no suitable node found for job %s", job.ID)
}
