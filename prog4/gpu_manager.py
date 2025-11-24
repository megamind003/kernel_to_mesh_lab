import subprocess
import re
from typing import Optional, Dict


class GPUManager:
    """Monitors GPU usage and manages VRAM allocation."""
    
    def __init__(self, vram_limit_mb: int = 9500):
        self.vram_limit_mb = vram_limit_mb
        self.gpu_available = self._check_gpu_available()
    
    def _check_gpu_available(self) -> bool:
        try:
            result = subprocess.run(
                ['nvidia-smi'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def get_vram_usage(self) -> Optional[Dict[str, float]]:
        if not self.gpu_available:
            return None
        
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return None
            
            used, total = map(float, result.stdout.strip().split(','))
            
            return {
                'used_mb': used,
                'total_mb': total,
                'available_mb': total - used,
                'usage_percent': (used / total) * 100 if total > 0 else 0
            }
        except Exception as e:
            print(f"Failed to get VRAM usage: {e}")
            return None
    
    def is_vram_available(self, required_mb: int) -> bool:
        if not self.gpu_available:
            return False
        
        usage = self.get_vram_usage()
        if usage is None:
            return False
        
        return usage['available_mb'] >= required_mb
    
    def should_offload(self) -> bool:
        if not self.gpu_available:
            return False
        
        usage = self.get_vram_usage()
        if usage is None:
            return False
        
        return usage['used_mb'] > self.vram_limit_mb
    
    def get_recommendation(self) -> str:
        if not self.gpu_available:
            return "CPU_ONLY"
        
        usage = self.get_vram_usage()
        if usage is None:
            return "CPU_ONLY"
        
        if usage['used_mb'] < 4000:
            return "FULL_GPU"
        elif usage['used_mb'] < self.vram_limit_mb:
            return "PARTIAL_GPU"
        else:
            return "OFFLOAD_TO_RAM"
