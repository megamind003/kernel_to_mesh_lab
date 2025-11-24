package cluster

import (
	"fmt"
	"sync"
	"time"
)

type LogEntry struct {
	Term    int
	Command string
}

type RaftNode struct {
	ID          string
	CurrentTerm int
	VotedFor    string
	Log         []LogEntry
	
	// Volatile state
	CommitIndex int
	LastApplied int

	mu sync.Mutex
}

func NewRaftNode(id string) *RaftNode {
	return &RaftNode{
		ID:          id,
		CurrentTerm: 0,
		Log:         make([]LogEntry, 0),
	}
}

// Apply adds a command to the log (Mock implementation of consensus)
func (rn *RaftNode) Apply(command string) error {
	rn.mu.Lock()
	defer rn.mu.Unlock()

	// In a real Raft, we would:
	// 1. Append to local log
	// 2. Broadcast AppendEntries to followers
	// 3. Wait for majority ack
	// 4. Commit

	// For this prototype, we just append and commit immediately (Single Node Mode)
	entry := LogEntry{
		Term:    rn.CurrentTerm,
		Command: command,
	}
	rn.Log = append(rn.Log, entry)
	rn.CommitIndex = len(rn.Log) - 1
	rn.LastApplied = rn.CommitIndex

	fmt.Printf("[RAFT] Node %s applied command: %s (Index: %d, Term: %d)\n", 
		rn.ID, command, rn.CommitIndex, rn.CurrentTerm)
	return nil
}

func (rn *RaftNode) Start() {
	// Mock heartbeat loop
	go func() {
		for {
			time.Sleep(5 * time.Second)
			// fmt.Printf("[RAFT] Node %s heartbeat (Term: %d)\n", rn.ID, rn.CurrentTerm)
		}
	}()
}
