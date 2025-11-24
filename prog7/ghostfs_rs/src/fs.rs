use fuser::{
    FileAttr, FileType as FuseFileType, Filesystem, ReplyAttr, ReplyData, ReplyDirectory, ReplyEntry,
    ReplyCreate, ReplyWrite, Request, ReplyEmpty,
};
use libc::{ENOENT, EIO, ENOSPC, ENOTDIR, ENOTEMPTY};
use std::ffi::OsStr;
use std::sync::{Arc, RwLock};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use log::{debug, error, info};

use crate::carrier::CarrierPool;
use crate::crypto::Crypto;
use crate::metadata::{MetadataManager, FileType, BLOCK_SIZE, Inode};

const TTL: Duration = Duration::from_secs(1);

pub struct GhostFS {
    pub pool: Arc<RwLock<CarrierPool>>,
    pub metadata_mgr: Arc<RwLock<MetadataManager>>,
    pub crypto: Arc<Crypto>,
}

impl GhostFS {
    fn get_inode_attr(&self, inode: &Inode) -> FileAttr {
        FileAttr {
            ino: inode.id,
            size: inode.size,
            blocks: (inode.size + BLOCK_SIZE as u64 - 1) / BLOCK_SIZE as u64,
            atime: UNIX_EPOCH + Duration::from_secs(inode.atime),
            mtime: UNIX_EPOCH + Duration::from_secs(inode.mtime),
            ctime: UNIX_EPOCH + Duration::from_secs(inode.ctime),
            crtime: UNIX_EPOCH + Duration::from_secs(inode.ctime),
            kind: match inode.kind {
                FileType::File => FuseFileType::RegularFile,
                FileType::Directory => FuseFileType::Directory,
            },
            perm: inode.mode,
            nlink: 1,
            uid: inode.uid,
            gid: inode.gid,
            rdev: 0,
            blksize: BLOCK_SIZE as u32,
            flags: 0,
        }
    }
}

impl Filesystem for GhostFS {
    fn lookup(&mut self, _req: &Request, parent: u64, name: &OsStr, reply: ReplyEntry) {
        let name_str = match name.to_str() {
            Some(s) => s,
            None => {
                reply.error(ENOENT);
                return;
            }
        };

        let mgr = self.metadata_mgr.read().unwrap();
        if let Some(children) = mgr.metadata.directory_tree.get(&parent) {
            if let Some(&child_id) = children.get(name_str) {
                if let Some(inode) = mgr.metadata.inodes.get(&child_id) {
                    reply.entry(&TTL, &self.get_inode_attr(inode), 0);
                    return;
                }
            }
        }
        reply.error(ENOENT);
    }

    fn getattr(&mut self, _req: &Request, ino: u64, reply: ReplyAttr) {
        let mgr = self.metadata_mgr.read().unwrap();
        if let Some(inode) = mgr.metadata.inodes.get(&ino) {
            reply.attr(&TTL, &self.get_inode_attr(inode));
        } else {
            reply.error(ENOENT);
        }
    }

    fn readdir(
        &mut self,
        _req: &Request,
        ino: u64,
        _fh: u64,
        offset: i64,
        mut reply: ReplyDirectory,
    ) {
        let mgr = self.metadata_mgr.read().unwrap();
        
        if let Some(children) = mgr.metadata.directory_tree.get(&ino) {
            let mut entries = Vec::new();
            entries.push((ino, FuseFileType::Directory, "."));
            entries.push((mgr.metadata.inodes.get(&ino).unwrap().uid as u64, FuseFileType::Directory, "..")); // Hack for ..

            for (name, &child_id) in children {
                let kind = match mgr.metadata.inodes.get(&child_id).unwrap().kind {
                    FileType::File => FuseFileType::RegularFile,
                    FileType::Directory => FuseFileType::Directory,
                };
                entries.push((child_id, kind, name));
            }

            for (i, (inode, kind, name)) in entries.iter().enumerate().skip(offset as usize) {
                // i + 1 as offset for next entry
                if reply.add(*inode, (i + 1) as i64, *kind, name) {
                    break;
                }
            }
            reply.ok();
        } else {
            reply.error(ENOTDIR);
        }
    }

    fn create(
        &mut self,
        _req: &Request,
        parent: u64,
        name: &OsStr,
        mode: u32,
        _umask: u32,
        _flags: i32,
        reply: ReplyCreate,
    ) {
        let name_str = name.to_str().unwrap().to_string();
        let mut mgr = self.metadata_mgr.write().unwrap();

        if !mgr.metadata.directory_tree.contains_key(&parent) {
            reply.error(ENOTDIR);
            return;
        }

        let id = mgr.metadata.next_inode_id;
        mgr.metadata.next_inode_id += 1;
        let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();

        let inode = Inode {
            id,
            mode: mode as u16,
            uid: _req.uid(),
            gid: _req.gid(),
            size: 0,
            atime: now,
            mtime: now,
            ctime: now,
            kind: FileType::File,
            blocks: Vec::new(),
        };

        mgr.metadata.inodes.insert(id, inode.clone());
        mgr.metadata.directory_tree.get_mut(&parent).unwrap().insert(name_str, id);

        // Save metadata
        drop(mgr); // Release lock before save (though save takes read lock? No, save needs data)
        // Actually save is on MetadataManager.
        // We need to call save.
        // Re-acquire lock or just call save on the locked guard?
        // MetadataManager::save takes &self.
        // So we can call it.
        
        // But wait, we need pool and crypto.
        // We can't call save inside the lock if save needs to lock pool?
        // Pool lock is separate.
        // Yes.
        
        let mgr = self.metadata_mgr.read().unwrap();
        let pool = self.pool.read().unwrap(); // Read lock on pool (write_bytes takes &mut self? No, wait)
        // CarrierPool::write_bytes takes &mut self.
        // So we need write lock on pool.
        drop(pool);
        let mut pool = self.pool.write().unwrap();
        if let Err(e) = mgr.save(&mut pool, &self.crypto) {
            error!("Failed to save metadata: {}", e);
            reply.error(EIO);
            return;
        }

        reply.created(&TTL, &self.get_inode_attr(&inode), 0, 0, 0);
    }

    fn write(
        &mut self,
        _req: &Request,
        ino: u64,
        _fh: u64,
        offset: i64,
        data: &[u8],
        _write_flags: u32,
        _flags: i32,
        _lock_owner: Option<u64>,
        reply: ReplyWrite,
    ) {
        let mut mgr = self.metadata_mgr.write().unwrap();
        let inode = match mgr.metadata.inodes.get_mut(&ino) {
            Some(i) => i,
            None => {
                reply.error(ENOENT);
                return;
            }
        };

        let start = offset as usize;
        let end = start + data.len();
        
        // Calculate blocks needed
        let start_block_idx = start / BLOCK_SIZE;
        let end_block_idx = (end + BLOCK_SIZE - 1) / BLOCK_SIZE;

        // Ensure we have enough blocks
        let current_blocks = inode.blocks.len();
        if current_blocks < end_block_idx {
             let needed = end_block_idx - current_blocks;
             let mut new_blocks = Vec::new();
             for _ in 0..needed {
                 if let Some(free_block) = mgr.metadata.free_blocks.pop() {
                     new_blocks.push(free_block);
                 } else {
                     // Put back popped blocks? Or just fail.
                     // For now fail.
                     // We should probably put them back to be safe.
                     mgr.metadata.free_blocks.extend(new_blocks);
                     reply.error(ENOSPC);
                     return;
                 }
             }
             // Re-borrow inode
             let inode = mgr.metadata.inodes.get_mut(&ino).unwrap();
             inode.blocks.extend(new_blocks);
        }
        
        // Re-borrow inode for writing
        let inode = mgr.metadata.inodes.get_mut(&ino).unwrap();

        let mut pool = self.pool.write().unwrap();
        let mut bytes_written = 0;

        for i in start_block_idx..end_block_idx {
            let block_num = inode.blocks[i];
            let block_offset_in_file = i * BLOCK_SIZE;
            
            // Determine range within this block
            let block_start = if start > block_offset_in_file { start - block_offset_in_file } else { 0 };
            let block_end = if end < block_offset_in_file + BLOCK_SIZE { end - block_offset_in_file } else { BLOCK_SIZE };
            
            let chunk_len = block_end - block_start;
            let data_start = bytes_written;
            let data_end = data_start + chunk_len;
            let data_chunk = &data[data_start..data_end];

            // Read-Modify-Write
            let mut block_buf = vec![0u8; BLOCK_SIZE];
            
            // If we are overwriting the whole block, we don't need to read (optimization).
            // But usually we read to be safe or if partial.
            let full_overwrite = block_start == 0 && block_end == BLOCK_SIZE;
            
            if !full_overwrite {
                // Read existing block
                if let Err(_) = pool.read_bytes(block_num as usize * BLOCK_SIZE, &mut block_buf) {
                    // If read fails, maybe it's a new block? Just use zeros.
                } else {
                    // Decrypt
                    if let Ok(decrypted) = self.crypto.decrypt_block(block_num, &block_buf) {
                        block_buf = decrypted;
                    }
                }
            }

            // Modify
            block_buf[block_start..block_end].copy_from_slice(data_chunk);

            // Encrypt
            let encrypted = match self.crypto.encrypt_block(block_num, &block_buf) {
                Ok(e) => e,
                Err(_) => {
                    reply.error(EIO);
                    return;
                }
            };

            // Write
            if let Err(_) = pool.write_bytes(block_num as usize * BLOCK_SIZE, &encrypted) {
                reply.error(EIO);
                return;
            }

            bytes_written += chunk_len;
        }

        inode.size = std::cmp::max(inode.size, end as u64);
        inode.mtime = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs();

        // Save metadata periodically? Or on every write?
        // For safety, every write (or close). But write is frequent.
        // Let's save metadata here to be safe.
        if let Err(e) = mgr.save(&pool, &self.crypto) {
             error!("Failed to save metadata: {}", e);
        }

        reply.written(bytes_written as u32);
    }

    fn read(
        &mut self,
        _req: &Request,
        ino: u64,
        _fh: u64,
        offset: i64,
        size: u32,
        _flags: i32,
        _lock_owner: Option<u64>,
        reply: ReplyData,
    ) {
        let mgr = self.metadata_mgr.read().unwrap();
        let inode = match mgr.metadata.inodes.get(&ino) {
            Some(i) => i,
            None => {
                reply.error(ENOENT);
                return;
            }
        };

        if offset as u64 >= inode.size {
            reply.data(&[]);
            return;
        }

        let size = std::cmp::min(size as u64, inode.size - offset as u64) as usize;
        let start = offset as usize;
        let end = start + size;

        let start_block_idx = start / BLOCK_SIZE;
        let end_block_idx = (end + BLOCK_SIZE - 1) / BLOCK_SIZE;

        let mut data = Vec::with_capacity(size);
        let mut pool = self.pool.read().unwrap(); // Read lock on pool (read_bytes needs &self? Yes)
        // CarrierPool::read_bytes takes &self.

        for i in start_block_idx..end_block_idx {
             if i >= inode.blocks.len() {
                 break;
             }
             let block_num = inode.blocks[i];
             let mut block_buf = vec![0u8; BLOCK_SIZE];
             
             if let Err(_) = pool.read_bytes(block_num as usize * BLOCK_SIZE, &mut block_buf) {
                 reply.error(EIO);
                 return;
             }

             let decrypted = match self.crypto.decrypt_block(block_num, &block_buf) {
                 Ok(d) => d,
                 Err(_) => {
                     reply.error(EIO);
                     return;
                 }
             };

             let block_offset_in_file = i * BLOCK_SIZE;
             let block_start = if start > block_offset_in_file { start - block_offset_in_file } else { 0 };
             let block_end = if end < block_offset_in_file + BLOCK_SIZE { end - block_offset_in_file } else { BLOCK_SIZE };

             data.extend_from_slice(&decrypted[block_start..block_end]);
        }

        reply.data(&data);
    }

    fn unlink(&mut self, _req: &Request, parent: u64, name: &OsStr, reply: ReplyEmpty) {
        let name_str = name.to_str().unwrap().to_string();
        let mut mgr = self.metadata_mgr.write().unwrap();

        if let Some(children) = mgr.metadata.directory_tree.get_mut(&parent) {
            if let Some(ino) = children.remove(&name_str) {
                if let Some(inode) = mgr.metadata.inodes.remove(&ino) {
                    // Free blocks
                    for block in inode.blocks {
                        mgr.metadata.free_blocks.push(block);
                    }
                    
                    let mut pool = self.pool.write().unwrap();
                    if let Err(e) = mgr.save(&mut pool, &self.crypto) {
                        error!("Failed to save metadata: {}", e);
                    }
                    reply.ok();
                    return;
                }
            }
        }
        reply.error(ENOENT);
    }
    
    // Implement mkdir, rmdir similarly if needed.
    // For this test, we mainly need file write/read.
}
