use anyhow::{Context, Result};
use image::{GenericImageView, RgbaImage};
use std::fs;
use std::path::{Path, PathBuf};
use log::{info, warn};

pub struct Carrier {
    pub path: PathBuf,
    pub image: RgbaImage,
    pub capacity_bits: usize,
    pub capacity_bytes: usize,
}

pub struct CarrierPool {
    pub carriers: Vec<Carrier>,
    pub total_capacity_bytes: usize,
}

impl CarrierPool {
    pub fn new(host_dir: &Path) -> Result<Self> {
        let mut carriers = Vec::new();
        let mut total_capacity_bits = 0;

        info!("Scanning {} for PNG carriers...", host_dir.display());

        for entry in fs::read_dir(host_dir)? {
            let entry = entry?;
            let path = entry.path();
            if path.extension().and_then(|s| s.to_str()) == Some("png") {
                match image::open(&path) {
                    Ok(img) => {
                        let rgba = img.to_rgba8();
                        let (w, h) = rgba.dimensions();
                        // 3 bits per pixel (R, G, B channels, ignore Alpha)
                        let cap_bits = (w as usize) * (h as usize) * 3;
                        let cap_bytes = cap_bits / 8;
                        
                        carriers.push(Carrier {
                            path,
                            image: rgba,
                            capacity_bits: cap_bits,
                            capacity_bytes: cap_bytes,
                        });
                        total_capacity_bits += cap_bits;
                    }
                    Err(e) => {
                        warn!("Failed to load image {:?}: {}", path, e);
                    }
                }
            }
        }

        // Sort carriers by path to ensure deterministic order
        carriers.sort_by(|a, b| a.path.cmp(&b.path));

        info!("Loaded {} carriers. Total capacity: {} MB", 
              carriers.len(), total_capacity_bits / 8 / 1024 / 1024);

        if carriers.is_empty() {
            anyhow::bail!("No valid PNG carriers found in {}", host_dir.display());
        }

        Ok(CarrierPool {
            carriers,
            total_capacity_bytes: total_capacity_bits / 8,
        })
    }

    pub fn read_bytes(&self, addr: usize, buf: &mut [u8]) -> Result<()> {
        if addr + buf.len() > self.total_capacity_bytes {
            anyhow::bail!("Read out of bounds");
        }

        let mut current_addr = 0;
        let mut buf_offset = 0;
        let mut remaining = buf.len();

        for carrier in &self.carriers {
            if remaining == 0 {
                break;
            }

            let carrier_end = current_addr + carrier.capacity_bytes;

            if addr < carrier_end {
                // We need to read from this carrier
                let start_in_carrier = if addr > current_addr { addr - current_addr } else { 0 };
                let available_in_carrier = carrier.capacity_bytes - start_in_carrier;
                let to_read = std::cmp::min(remaining, available_in_carrier);

                CarrierPool::read_from_carrier(carrier, start_in_carrier, &mut buf[buf_offset..buf_offset + to_read]);

                buf_offset += to_read;
                remaining -= to_read;
            }

            current_addr += carrier.capacity_bytes;
        }

        Ok(())
    }

    pub fn write_bytes(&mut self, addr: usize, buf: &[u8]) -> Result<()> {
        if addr + buf.len() > self.total_capacity_bytes {
            anyhow::bail!("Write out of bounds");
        }

        let mut current_addr = 0;
        let mut buf_offset = 0;
        let mut remaining = buf.len();

        for carrier in &mut self.carriers {
            if remaining == 0 {
                break;
            }

            let carrier_end = current_addr + carrier.capacity_bytes;

            if addr < carrier_end {
                // We need to write to this carrier
                let start_in_carrier = if addr > current_addr { addr - current_addr } else { 0 };
                let available_in_carrier = carrier.capacity_bytes - start_in_carrier;
                let to_write = std::cmp::min(remaining, available_in_carrier);

                CarrierPool::write_to_carrier(carrier, start_in_carrier, &buf[buf_offset..buf_offset + to_write]);

                buf_offset += to_write;
                remaining -= to_write;
            }

            current_addr += carrier.capacity_bytes;
        }

        Ok(())
    }

    fn read_from_carrier(carrier: &Carrier, start_byte: usize, buf: &mut [u8]) {
        let width = carrier.image.width() as usize;
        let start_bit = start_byte * 8;
        
        for (i, byte) in buf.iter_mut().enumerate() {
            let mut val = 0u8;
            for bit in 0..8 {
                let global_bit_idx = start_bit + i * 8 + bit;
                let pixel_idx = global_bit_idx / 3;
                let channel_idx = global_bit_idx % 3;

                let x = (pixel_idx % width) as u32;
                let y = (pixel_idx / width) as u32;

                let pixel = carrier.image.get_pixel(x, y);
                let channel_val = pixel[channel_idx]; // 0=R, 1=G, 2=B

                if (channel_val & 1) != 0 {
                    val |= 1 << bit;
                }
            }
            *byte = val;
        }
    }

    fn write_to_carrier(carrier: &mut Carrier, start_byte: usize, buf: &[u8]) {
        let width = carrier.image.width() as usize;
        let start_bit = start_byte * 8;

        for (i, &byte) in buf.iter().enumerate() {
            for bit in 0..8 {
                let bit_val = (byte >> bit) & 1;
                let global_bit_idx = start_bit + i * 8 + bit;
                let pixel_idx = global_bit_idx / 3;
                let channel_idx = global_bit_idx % 3;

                let x = (pixel_idx % width) as u32;
                let y = (pixel_idx / width) as u32;

                let pixel = carrier.image.get_pixel_mut(x, y);
                let mut channel_val = pixel[channel_idx]; // 0=R, 1=G, 2=B

                // Clear LSB
                channel_val &= !1;
                // Set LSB
                if bit_val != 0 {
                    channel_val |= 1;
                }
                
                pixel[channel_idx] = channel_val;
            }
        }
    }

    pub fn sync(&self) -> Result<()> {
        info!("Syncing carriers to disk...");
        for carrier in &self.carriers {
            carrier.image.save(&carrier.path)
                .with_context(|| format!("Failed to save carrier {:?}", carrier.path))?;
        }
        info!("Sync complete.");
        Ok(())
    }
}
