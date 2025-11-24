use std::os::unix::io::AsRawFd;
use std::path::Path;
use std::fs::File;
use anyhow::Result;
use tokio::io::AsyncWriteExt;

pub async fn sendfile_response(
    file_path: &Path,
    stream: &mut tokio::net::TcpStream,
) -> Result<usize> {
    let file = File::open(file_path)?;
    let metadata = file.metadata()?;
    let file_size = metadata.len() as usize;
    
    let file_fd = file.as_raw_fd();
    let socket_fd = stream.as_raw_fd();
    
    let mut offset = 0i64;
    let mut total_sent = 0usize;
    
    loop {
        let sent = unsafe {
            libc::sendfile(
                socket_fd,
                file_fd,
                &mut offset as *mut i64,
                file_size - total_sent,
            )
        };
        
        if sent < 0 {
            return Err(std::io::Error::last_os_error().into());
        }
        
        if sent == 0 {
            break;
        }
        
        total_sent += sent as usize;
        
        if total_sent >= file_size {
            break;
        }
    }
    
    Ok(total_sent)
}

pub fn supports_sendfile() -> bool {
    cfg!(target_os = "linux")
}
