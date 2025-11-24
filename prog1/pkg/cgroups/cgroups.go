package cgroups

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
)

const cgroupRoot = "/sys/fs/cgroup"

type Manager struct {
	Path string
}

func NewManager(name string) (*Manager, error) {
	path := filepath.Join(cgroupRoot, name)
	if err := os.MkdirAll(path, 0755); err != nil {
		return nil, fmt.Errorf("failed to create cgroup directory: %w", err)
	}
	return &Manager{Path: path}, nil
}

func (m *Manager) SetMemoryLimit(limitBytes int) error {
	path := filepath.Join(m.Path, "memory.max")
	return os.WriteFile(path, []byte(strconv.Itoa(limitBytes)), 0644)
}

func (m *Manager) SetPidsLimit(max int) error {
	path := filepath.Join(m.Path, "pids.max")
	return os.WriteFile(path, []byte(strconv.Itoa(max)), 0644)
}

func (m *Manager) AddPid(pid int) error {
	path := filepath.Join(m.Path, "cgroup.procs")
	return os.WriteFile(path, []byte(strconv.Itoa(pid)), 0644)
}

func (m *Manager) Remove() error {
	return os.Remove(m.Path)
}
