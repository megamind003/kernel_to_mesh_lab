use core_affinity::set_for_current;
use tracing::{info, warn};

pub fn pin_to_core(core_id: usize) -> bool {
    let core_ids = core_affinity::get_core_ids().unwrap_or_default();
    
    if core_id >= core_ids.len() {
        warn!("Core {} not available, only {} cores", core_id, core_ids.len());
        return false;
    }

    let success = set_for_current(core_ids[core_id]);
    
    if success {
        info!("Thread pinned to core {}", core_id);
    } else {
        warn!("Failed to pin thread to core {}", core_id);
    }
    
    success
}

pub fn get_num_cores() -> usize {
    core_affinity::get_core_ids()
        .map(|ids| ids.len())
        .unwrap_or_else(|| num_cpus::get())
}
