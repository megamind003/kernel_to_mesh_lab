package main

import (
	"bufio"
	"flag"
	"fmt"
	"hydra/pkg/cluster"
	"hydra/pkg/gossip"
	"hydra/pkg/storage"
	"net"
	"strings"
)

func main() {
	nodeID := flag.String("id", "", "Node ID")
	addr := flag.String("addr", "", "Address to listen on")
	dataDir := flag.String("data-dir", "", "Data directory")
	joinAddr := flag.String("join", "", "Address of a node to join")
	
	flag.Parse()

	if *nodeID == "" || *addr == "" || *dataDir == "" {
		fmt.Println("Usage: hydra --id <id> --addr <host:port> --data-dir <path> [--join <host:port>]")
		return
	}

	runNode(*nodeID, *addr, *dataDir, *joinAddr)
}

func runNode(id, addr, dataDir, joinAddr string) {
	fmt.Printf("Starting node %s on %s with data dir %s\n", id, addr, dataDir)
	
	// 1. Initialize Storage Engine
	engine, err := storage.NewRustEngine(dataDir)
	if err != nil {
		panic(fmt.Sprintf("Failed to initialize engine: %v", err))
	}
	defer engine.Close()

	// 2. Initialize Cluster Components
	ring := cluster.NewRing(10, 3) // 10 VNodes, RF=3
	ring.AddNode(id, addr)         // Add self

	gossiper := gossip.NewGossiper(id, addr)
	gossiper.Start()

	// 3. Join Cluster if requested
	if joinAddr != "" {
		fmt.Printf("Joining cluster via %s...\n", joinAddr)
		if err := joinCluster(id, addr, joinAddr, ring, gossiper); err != nil {
			fmt.Printf("Failed to join cluster: %v\n", err)
		}
	}

	// 4. Start TCP Server
	ln, err := net.Listen("tcp", addr)
	if err != nil {
		panic(fmt.Sprintf("Failed to listen on %s: %v", addr, err))
	}

	fmt.Println("Ready to accept connections")

	for {
		conn, err := ln.Accept()
		if err != nil {
			fmt.Printf("Accept error: %v\n", err)
			continue
		}
		go handleConn(conn, engine, ring, gossiper)
	}
}

func joinCluster(myID, myAddr, seedAddr string, ring *cluster.Ring, g *gossip.Gossiper) error {
	conn, err := net.Dial("tcp", seedAddr)
	if err != nil {
		return err
	}
	defer conn.Close()

	// Send JOIN command
	fmt.Fprintf(conn, "JOIN %s %s\n", myID, myAddr)
	
	// Read response (simple OK for now, ideally would return full member list)
	scanner := bufio.NewScanner(conn)
	if scanner.Scan() {
		resp := scanner.Text()
		if resp == "OK" {
			fmt.Println("Joined cluster successfully")
			// Add seed to our list
			// In a real system, we'd get the ID of the seed from the handshake
			// For now, we assume the seed adds us, and we will eventually discover others via gossip
			// But to bootstrap, we need to add the seed. We don't know its ID here easily without protocol change.
			// Hack: Add seed with unknown ID or ask user to provide it. 
			// Better: The seed should return its ID in the OK response.
		} else if strings.HasPrefix(resp, "WELCOME") {
			// WELCOME <seedID>
			parts := strings.Split(resp, " ")
			if len(parts) >= 2 {
				seedID := parts[1]
				ring.AddNode(seedID, seedAddr)
				g.AddMember(seedID, seedAddr)
				fmt.Printf("Added seed node %s\n", seedID)
			}
		} else {
			return fmt.Errorf("unexpected response: %s", resp)
		}
	}
	return nil
}

func handleConn(conn net.Conn, engine *storage.RustEngine, ring *cluster.Ring, g *gossip.Gossiper) {
	defer conn.Close()
	scanner := bufio.NewScanner(conn)
	for scanner.Scan() {
		line := scanner.Text()
		parts := strings.SplitN(line, " ", 3)
		if len(parts) == 0 {
			continue
		}
		cmd := parts[0]

		switch cmd {
		case "PUT":
			if len(parts) == 3 {
				// TODO: Check ring if we are responsible
				// For now, we accept all writes (Mesh/Anycast style) or just local
				err := engine.Put(parts[1], []byte(parts[2]))
				if err != nil {
					fmt.Fprintf(conn, "ERROR: %v\n", err)
				} else {
					fmt.Fprintf(conn, "OK\n")
				}
			}
		case "GET":
			if len(parts) == 2 {
				val, err := engine.Get(parts[1])
				if err != nil {
					fmt.Fprintf(conn, "NOT_FOUND\n")
				} else {
					fmt.Fprintf(conn, "VALUE %s\n", string(val))
				}
			}
		case "JOIN":
			if len(parts) == 3 {
				joinerID := parts[1]
				joinerAddr := parts[2]
				fmt.Printf("Node %s (%s) requesting to join\n", joinerID, joinerAddr)
				
				ring.AddNode(joinerID, joinerAddr)
				g.AddMember(joinerID, joinerAddr)
				
				// Return WELCOME <myID>
				fmt.Fprintf(conn, "WELCOME %s\n", g.Self.ID)
			}
		default:
			fmt.Fprintf(conn, "UNKNOWN_CMD\n")
		}
	}
}
