package container

import (
	"fmt"
	"os"
	"path/filepath"
	"syscall"
)

// OverlayManager manages the overlay filesystem for containers
type OverlayManager struct {
	BaseDir string // Directory where all container data is stored (e.g., /var/lib/titan/containers)
	ImagesDir string // Directory where base images are stored
}

func NewOverlayManager(baseDir, imagesDir string) *OverlayManager {
	return &OverlayManager{
		BaseDir:   baseDir,
		ImagesDir: imagesDir,
	}
}

// Setup creates the overlay directories and mounts the filesystem
// Returns the path to the merged directory (the container's rootfs)
func (om *OverlayManager) Setup(containerID string, baseImage string) (string, error) {
	containerDir := filepath.Join(om.BaseDir, containerID)
	lowerDir := filepath.Join(om.ImagesDir, baseImage)
	upperDir := filepath.Join(containerDir, "upper")
	workDir := filepath.Join(containerDir, "work")
	mergedDir := filepath.Join(containerDir, "merged")

	// Ensure base image exists
	if _, err := os.Stat(lowerDir); os.IsNotExist(err) {
		return "", fmt.Errorf("base image %s not found at %s", baseImage, lowerDir)
	}

	// Create directories
	for _, dir := range []string{upperDir, workDir, mergedDir} {
		if err := os.MkdirAll(dir, 0755); err != nil {
			return "", fmt.Errorf("failed to create directory %s: %w", dir, err)
		}
	}

	// Mount OverlayFS
	// mount -t overlay overlay -o lowerdir=lower,upperdir=upper,workdir=work merged
	opts := fmt.Sprintf("lowerdir=%s,upperdir=%s,workdir=%s", lowerDir, upperDir, workDir)
	if err := syscall.Mount("overlay", mergedDir, "overlay", 0, opts); err != nil {
		return "", fmt.Errorf("failed to mount overlay: %w", err)
	}

	return mergedDir, nil
}

// Cleanup unmounts and removes the container directories
func (om *OverlayManager) Cleanup(containerID string) error {
	containerDir := filepath.Join(om.BaseDir, containerID)
	mergedDir := filepath.Join(containerDir, "merged")

	// Unmount merged
	if err := syscall.Unmount(mergedDir, 0); err != nil {
		// If it's not mounted, that's fine, but if it is and fails, we should know
		// Check if it's mounted? For now just log error if it's not "invalid argument" (not mounted)
		fmt.Printf("Warning: failed to unmount %s: %v\n", mergedDir, err)
	}

	// Remove container directory (recursively removes upper, work, merged)
	// Note: We might want to keep 'upper' for debugging or persistence in future
	return os.RemoveAll(containerDir)
}
