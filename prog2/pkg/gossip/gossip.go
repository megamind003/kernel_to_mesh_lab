package gossip

import (
	"fmt"
	"math/rand"
	"sync"
	"time"
)

type Member struct {
	ID          string
	Addr        string
	Status      string // "Alive", "Suspect", "Dead"
	Incarnation int
	LastUpdate  time.Time
}

type Gossiper struct {
	Self    *Member
	Members map[string]*Member
	mu      sync.RWMutex
}

func NewGossiper(id, addr string) *Gossiper {
	return &Gossiper{
		Self: &Member{
			ID:          id,
			Addr:        addr,
			Status:      "Alive",
			Incarnation: 0,
			LastUpdate:  time.Now(),
		},
		Members: make(map[string]*Member),
	}
}

func (g *Gossiper) AddMember(id, addr string) {
	g.mu.Lock()
	defer g.mu.Unlock()
	if _, ok := g.Members[id]; !ok {
		g.Members[id] = &Member{
			ID:          id,
			Addr:        addr,
			Status:      "Alive",
			Incarnation: 0,
			LastUpdate:  time.Now(),
		}
		fmt.Printf("[GOSSIP] Node %s joined the cluster\n", id)
	}
}

func (g *Gossiper) GetMembers() []*Member {
	g.mu.RLock()
	defer g.mu.RUnlock()
	members := make([]*Member, 0, len(g.Members))
	for _, m := range g.Members {
		members = append(members, m)
	}
	return members
}

func (g *Gossiper) Start() {
	go func() {
		for {
			time.Sleep(2 * time.Second)
			g.gossip()
		}
	}()
}

func (g *Gossiper) gossip() {
	g.mu.RLock()
	peers := make([]*Member, 0, len(g.Members))
	for _, m := range g.Members {
		if m.ID != g.Self.ID && m.Status == "Alive" {
			peers = append(peers, m)
		}
	}
	g.mu.RUnlock()

	if len(peers) == 0 {
		// fmt.Println("[GOSSIP] No peers to gossip with.")
		return
	}

	// Pick random peer
	peer := peers[rand.Intn(len(peers))]
	
	// In a real implementation, we would send a UDP packet here
	// For now, we just log to show activity
	fmt.Printf("[GOSSIP] %s sending heartbeat to %s (%s)\n", g.Self.ID, peer.ID, peer.Addr)
}
