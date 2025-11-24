package container

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"prog1/pkg/cgroups"
	"prog1/pkg/telemetry"
	"syscall"
)

// Config holds the configuration for the container
type Config struct {
	Command     []string
	RootFS      string
	MemoryLimit int
	PidsLimit   int
	OnStart     func(pid int) error
}

// RunParent creates the parent process that will clone into a new namespace
func RunParent(cfg Config) error {
	// Create a pipe for synchronization
	// Parent writes to w, Child reads from r
	r, w, err := os.Pipe()
	if err != nil {
		return fmt.Errorf("failed to create pipe: %w", err)
	}
	defer r.Close()
	defer w.Close()

	// We re-exec ourselves with the "child" command
	// The arguments to the child command will be the user's command
	args := append([]string{"child"}, cfg.Command...)
	
	// /proc/self/exe is a symlink to the current executable
	cmd := exec.Command("/proc/self/exe", args...)

	// Cloneflags:
	// CLONE_NEWUTS: New UTS namespace (hostname)
	// CLONE_NEWPID: New PID namespace (process IDs)
	// CLONE_NEWNS:  New Mount namespace (mount points)
	// CLONE_NEWNET: New Network namespace
	cmd.SysProcAttr = &syscall.SysProcAttr{
		Cloneflags: syscall.CLONE_NEWUTS | syscall.CLONE_NEWPID | syscall.CLONE_NEWNS | syscall.CLONE_NEWNET,
	}

	// Pass the pipe read end to the child via ExtraFiles
	// It will be FD 3 (0, 1, 2 are stdin, stdout, stderr)
	cmd.ExtraFiles = []*os.File{r}

	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	// Pass the RootFS path via environment variable
	cmd.Env = append(os.Environ(), "PROG1_ROOTFS="+cfg.RootFS)

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("failed to start parent process: %w", err)
	}

	// Setup Cgroups
	cg, err := cgroups.NewManager("prog1-container")
	if err != nil {
		// Clean up process if cgroup fails?
		cmd.Process.Kill()
		return fmt.Errorf("failed to create cgroup: %w", err)
	}
	defer cg.Remove()

	if cfg.MemoryLimit > 0 {
		if err := cg.SetMemoryLimit(cfg.MemoryLimit); err != nil {
			fmt.Printf("Warning: failed to set memory limit: %v\n", err)
		}
	}
	if cfg.PidsLimit > 0 {
		if err := cg.SetPidsLimit(cfg.PidsLimit); err != nil {
			fmt.Printf("Warning: failed to set pids limit: %v\n", err)
		}
	}

	// Add child PID to cgroup
	if err := cg.AddPid(cmd.Process.Pid); err != nil {
		cmd.Process.Kill()
		return fmt.Errorf("failed to add pid to cgroup: %w", err)
	}

	// Run OnStart callback (e.g., for networking)
	if cfg.OnStart != nil {
		if err := cfg.OnStart(cmd.Process.Pid); err != nil {
			cmd.Process.Kill()
			return fmt.Errorf("OnStart failed: %w", err)
		}
	}

	// Signal child to proceed
	// We write to the pipe. The content doesn't matter.
	if _, err := w.Write([]byte("OK")); err != nil {
		cmd.Process.Kill()
		return fmt.Errorf("failed to signal child: %w", err)
	}

	// Emit Started Event
	telemetry.Emit(telemetry.EventContainerStarted, "runtime", map[string]interface{}{
		"pid": cmd.Process.Pid,
		"cmd": cfg.Command,
	})

	if err := cmd.Wait(); err != nil {
		return fmt.Errorf("container process failed: %w", err)
	}

	// Emit Stopped Event
	telemetry.Emit(telemetry.EventContainerStopped, "runtime", map[string]interface{}{
		"pid": cmd.Process.Pid,
	})

	return nil
}

// RunChild is the function executed inside the new namespace
func RunChild(args []string) error {
	// 0. Wait for parent to set up Cgroups
	// We read from FD 3 (ExtraFile 0)
	pipe := os.NewFile(3, "pipe")
	if pipe != nil {
		defer pipe.Close()
		buf := make([]byte, 2)
		if _, err := pipe.Read(buf); err != nil {
			return fmt.Errorf("failed to wait for parent: %w", err)
		}
	}

	// 1. Setup Hostname
	if err := syscall.Sethostname([]byte("container")); err != nil {
		return fmt.Errorf("failed to set hostname: %w", err)
	}

	// 2. Setup RootFS (Pivot Root)
	rootfs := os.Getenv("PROG1_ROOTFS")
	if rootfs != "" {
		if err := setupRootFS(rootfs); err != nil {
			return fmt.Errorf("failed to setup rootfs: %w", err)
		}
	} else {
		fmt.Println("Warning: No RootFS provided, skipping pivot_root")
	}

	// 3. Mount /proc
	// We need to mount /proc to see the new PID namespace
	if err := syscall.Mount("proc", "/proc", "proc", 0, ""); err != nil {
		return fmt.Errorf("failed to mount proc: %w", err)
	}

	// 4. Execute the user command
	if len(args) == 0 {
		return fmt.Errorf("no command specified")
	}

	path, err := exec.LookPath(args[0])
	if err != nil {
		return fmt.Errorf("command not found: %w", err)
	}

	// Exec the command, replacing the current process (PID 1 in the container)
	if err := syscall.Exec(path, args, os.Environ()); err != nil {
		return fmt.Errorf("failed to exec user command: %w", err)
	}

	return nil
}

func setupRootFS(rootfs string) error {
	// Make the current root private to avoid propagation issues with pivot_root
	if err := syscall.Mount("", "/", "", syscall.MS_PRIVATE|syscall.MS_REC, ""); err != nil {
		return fmt.Errorf("failed to make root private: %w", err)
	}

	// Ensure rootfs is a mount point (required for pivot_root)
	// We bind mount it to itself to ensure it's a mount point
	if err := syscall.Mount(rootfs, rootfs, "", syscall.MS_BIND|syscall.MS_REC, ""); err != nil {
		return fmt.Errorf("failed to bind mount rootfs: %w", err)
	}

	// Create a directory for the old root
	putOld := filepath.Join(rootfs, "put_old")
	if err := os.MkdirAll(putOld, 0700); err != nil {
		return fmt.Errorf("failed to create put_old: %w", err)
	}

	// Pivot Root
	// new_root = rootfs
	// put_old = rootfs/put_old
	if err := syscall.PivotRoot(rootfs, putOld); err != nil {
		return fmt.Errorf("pivot_root failed: %w", err)
	}

	// Change directory to the new root
	if err := os.Chdir("/"); err != nil {
		return fmt.Errorf("chdir / failed: %w", err)
	}

	// Unmount the old root and remove the temporary directory
	// Note: put_old is now at /put_old inside the new root
	putOldInside := "/put_old"
	if err := syscall.Unmount(putOldInside, syscall.MNT_DETACH); err != nil {
		return fmt.Errorf("unmount put_old failed: %w", err)
	}

	if err := os.Remove(putOldInside); err != nil {
		// Just log error, don't fail?
		// return fmt.Errorf("remove put_old failed: %w", err)
		fmt.Printf("Warning: failed to remove %s: %v\n", putOldInside, err)
	}

	return nil
}
