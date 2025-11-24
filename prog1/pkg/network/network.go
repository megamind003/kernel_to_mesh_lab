package network

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
)

const (
	BridgeName = "titan0"
	BridgeIP   = "172.18.0.1/16"
)

// SetupBridge creates the bridge interface if it doesn't exist
func SetupBridge() error {
	// Check if bridge exists
	if _, err := os.Stat("/sys/class/net/" + BridgeName); err == nil {
		return nil // Already exists
	}

	// Create bridge
	if err := runIP("link", "add", "name", BridgeName, "type", "bridge"); err != nil {
		return fmt.Errorf("failed to create bridge: %w", err)
	}

	// Set IP
	if err := runIP("addr", "add", BridgeIP, "dev", BridgeName); err != nil {
		return fmt.Errorf("failed to set bridge IP: %w", err)
	}

	// Up
	if err := runIP("link", "set", BridgeName, "up"); err != nil {
		return fmt.Errorf("failed to set bridge up: %w", err)
	}
	
	// Setup NAT (Masquerade) - requires iptables
	// This allows containers to reach the internet
	cmd := exec.Command("iptables", "-t", "nat", "-A", "POSTROUTING", "-s", "172.18.0.0/16", "!", "-d", "172.18.0.0/16", "-j", "MASQUERADE")
	if err := cmd.Run(); err != nil {
		fmt.Printf("Warning: failed to setup NAT: %v\n", err)
	}

	return nil
}

// SetupNetwork configures networking for a container
// It creates a veth pair, moves one end to the container's namespace, and sets IPs
func SetupNetwork(containerID string, pid int) (string, error) {
	// Generate names
	// Host interface: veth<shortID>
	// Container interface: eth0
	shortID := containerID
	if len(shortID) > 8 {
		shortID = shortID[:8]
	}
	vethHost := "veth" + shortID
	vethPeer := "vpeer" + shortID

	// 1. Create Veth pair
	if err := runIP("link", "add", vethHost, "type", "veth", "peer", "name", vethPeer); err != nil {
		return "", fmt.Errorf("failed to create veth pair: %w", err)
	}

	// 2. Attach host side to bridge
	if err := runIP("link", "set", vethHost, "master", BridgeName); err != nil {
		return "", fmt.Errorf("failed to attach veth to bridge: %w", err)
	}
	if err := runIP("link", "set", vethHost, "up"); err != nil {
		return "", fmt.Errorf("failed to set veth up: %w", err)
	}

	// 3. Move peer to container namespace
	// We need the PID of the container process
	if err := runIP("link", "set", vethPeer, "netns", fmt.Sprintf("%d", pid)); err != nil {
		return "", fmt.Errorf("failed to move veth to ns: %w", err)
	}

	// 4. Configure container side (inside the namespace)
	// We can't easily run 'ip' inside the namespace from here without 'nsenter'
	// But we can use 'nsenter' to run 'ip' commands inside the namespace
	
	// Calculate IP based on PID (simple hack for now)
	// 172.18.X.Y
	// We'll just use a random IP or hash
	// For simplicity, let's just pick one. In a real system we'd have an allocator.
	// Let's use the last 2 bytes of the PID?
	ipOctet3 := (pid >> 8) & 0xFF
	ipOctet4 := pid & 0xFF
	if ipOctet4 == 0 { ipOctet4 = 100 } // Avoid .0 and .1
	containerIP := fmt.Sprintf("172.18.%d.%d/16", ipOctet3, ipOctet4)
	
	// Rename vpeer -> eth0 inside NS
	if err := runNsIP(pid, "link", "set", vethPeer, "name", "eth0"); err != nil {
		return "", fmt.Errorf("failed to rename veth in ns: %w", err)
	}
	
	// Set IP
	if err := runNsIP(pid, "addr", "add", containerIP, "dev", "eth0"); err != nil {
		return "", fmt.Errorf("failed to set IP in ns: %w", err)
	}
	
	// Up lo and eth0
	if err := runNsIP(pid, "link", "set", "lo", "up"); err != nil {
		return "", fmt.Errorf("failed to set lo up: %w", err)
	}
	if err := runNsIP(pid, "link", "set", "eth0", "up"); err != nil {
		return "", fmt.Errorf("failed to set eth0 up: %w", err)
	}
	
	// Set Default Gateway
	gateway := strings.Split(BridgeIP, "/")[0]
	if err := runNsIP(pid, "route", "add", "default", "via", gateway); err != nil {
		return "", fmt.Errorf("failed to set default route: %w", err)
	}

	return containerIP, nil
}

func runIP(args ...string) error {
	cmd := exec.Command("ip", args...)
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("ip %v failed: %s: %w", args, string(out), err)
	}
	return nil
}

func runNsIP(pid int, args ...string) error {
	// nsenter -t <pid> -n ip ...
	nsArgs := append([]string{"-t", fmt.Sprintf("%d", pid), "-n", "ip"}, args...)
	cmd := exec.Command("nsenter", nsArgs...)
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("nsenter ip %v failed: %s: %w", args, string(out), err)
	}
	return nil
}
