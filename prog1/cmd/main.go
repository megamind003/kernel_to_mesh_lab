package main

import (
	"flag"
	"fmt"
	"os"
	"prog1/pkg/cluster"
	"prog1/pkg/container"
	"prog1/pkg/network"
	"prog1/pkg/scheduler"
	"prog1/pkg/telemetry"
	"time"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: prog1 <command> [args...]")
		os.Exit(1)
	}

	switch os.Args[1] {
	case "run":
		runCmd := flag.NewFlagSet("run", flag.ExitOnError)
		mem := runCmd.Int("memory", 0, "Memory limit in bytes")
		pids := runCmd.Int("pids", 0, "Max number of pids")
		
		if len(os.Args) < 2 {
			fmt.Println("Usage: prog1 run [flags] <cmd> [args...]")
			os.Exit(1)
		}

		runCmd.Parse(os.Args[2:])
		args := runCmd.Args()

		if len(args) < 1 {
			fmt.Println("Usage: prog1 run [flags] <cmd> [args...]")
			os.Exit(1)
		}

		// Generate a simple ID (timestamp + randomish)
		id := fmt.Sprintf("container-%d", os.Getpid())

		// Initialize Telemetry Listener
		bus := telemetry.GetBus()
		events := bus.Subscribe()
		go func() {
			for evt := range events {
				fmt.Printf("[EVENT] %s: %s (%v)\n", evt.Timestamp.Format(time.RFC3339), evt.Type, evt.Data)
			}
		}()

		// Initialize Scheduler (Mock Node)
		sched := scheduler.NewScheduler()
		sched.AddNode(&scheduler.Node{
			ID:          "local-node",
			TotalMemory: 1024 * 1024 * 1024, // 1GB
			TotalPids:   1000,
			Labels:      map[string]string{"env": "dev"},
		})

		// Initialize Raft (Distributed State)
		raftNode := cluster.NewRaftNode("node-1")
		raftNode.Start()

		// Schedule Job
		job := scheduler.Job{
			ID:        id,
			MemoryReq: *mem,
			PidsReq:   *pids,
			Affinity:  map[string]string{"env": "dev"},
		}
		node, err := sched.SelectNode(job)
		if err != nil {
			fmt.Printf("Scheduler failed: %v\n", err)
			os.Exit(1)
		}
		fmt.Printf("Scheduled job %s on node %s\n", job.ID, node.ID)

		// Commit to Raft
		raftCmd := fmt.Sprintf("SCHEDULE %s %s", job.ID, node.ID)
		raftNode.Apply(raftCmd)

		// Titan Directories
		baseDir := "./tmp/titan/containers"
		imagesDir := "./tmp/titan/images"
		
		fmt.Printf("Starting container %s...\n", id)

		// Initialize OverlayManager
		om := container.NewOverlayManager(baseDir, imagesDir)
		
		// Setup OverlayFS (using 'busybox' image)
		rootfs, err := om.Setup(id, "busybox")
		if err != nil {
			fmt.Printf("Error setting up overlay: %v\n", err)
			os.Exit(1)
		}
		
		// Ensure cleanup on exit
		defer func() {
			fmt.Println("Cleaning up container...")
			if err := om.Cleanup(id); err != nil {
				fmt.Printf("Error cleaning up: %v\n", err)
			}
		}()

		// Setup Bridge
		if err := network.SetupBridge(); err != nil {
			fmt.Printf("Error setting up bridge: %v\n", err)
			os.Exit(1)
		}

		cfg := container.Config{
			Command:     args,
			RootFS:      rootfs,
			MemoryLimit: *mem,
			PidsLimit:   *pids,
			OnStart: func(pid int) error {
				fmt.Printf("Setting up network for PID %d...\n", pid)
				ip, err := network.SetupNetwork(id, pid)
				if err != nil {
					return err
				}
				fmt.Printf("Container IP: %s\n", ip)
				return nil
			},
		}
		if err := container.RunParent(cfg); err != nil {
			fmt.Printf("Error running container: %v\n", err)
			// Don't exit here, let defer cleanup run
		}

	case "child":
		// This is the internal command executed inside the namespace
		if len(os.Args) < 3 {
			fmt.Println("Usage: prog1 child <cmd> [args...]")
			os.Exit(1)
		}
		if err := container.RunChild(os.Args[2:]); err != nil {
			fmt.Printf("Error in child process: %v\n", err)
			os.Exit(1)
		}

	default:
		fmt.Printf("Unknown command: %s\n", os.Args[1])
		os.Exit(1)
	}
}
