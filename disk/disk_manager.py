"""
磁盘管理器 - 实现任务书要求的内存映射文件方式
采用 mmap 实现对模拟磁盘的直接内存映射操作
"""

import os
import mmap
from config import SystemConfig
from utils import logger
from .super_block import SuperBlock

class DiskManager:
    """
    块设备管理器
    实现任务书1-(4)：文件操作采用内存映射文件方式
    """
    
    def __init__(self, disk_path: str):
        self.disk_path = disk_path
        self.block_size = SystemConfig.BLOCK_SIZE
        self.block_count = SystemConfig.TOTAL_BLOCKS
        self.total_size = self.block_size * self.block_count
        
        self.fd = None
        self.disk_mmap = None
        
        self._initialize_or_load()
        self._map_disk()
        
        logger.info(f"💾 磁盘管理器初始化: {disk_path} [{self.block_count}块]")
    
    def _initialize_or_load(self):
        """初始化模拟磁盘文件"""
        is_new = not os.path.exists(self.disk_path)
        
        if is_new:
            logger.info(f"✨ 创建磁盘镜像: {self.disk_path}")
            with open(self.disk_path, 'wb') as f:
                f.write(b'\0' * self.total_size)
            
            with open(self.disk_path, 'r+b') as f:
                sb = SuperBlock()
                f.write(sb.to_bytes())
            
            logger.info("✅ 超级块初始化完成(块#0)")
        else:
            current_size = os.path.getsize(self.disk_path)
            if current_size != self.total_size:
                logger.warning(f"⚠️ 磁盘大小不匹配")
    
    def _map_disk(self):
        """
        【关键实现】内存映射文件
        将磁盘文件映射到进程虚拟地址空间
        """
        try:
            self.fd = open(self.disk_path, 'r+b')
            self.disk_mmap = mmap.mmap(self.fd.fileno(), self.total_size)
            logger.info("🚀 内存映射(mmap)建立成功")
        except Exception as e:
            logger.error(f"❌ 内存映射失败: {e}")
            raise
    
    def read_block(self, block_index: int) -> bytes:
        """读取物理块"""
        if not (0 <= block_index < self.block_count):
            raise ValueError(f"块索引越界: {block_index}")
        
        start = block_index * self.block_size
        end = start + self.block_size
        return bytes(self.disk_mmap[start:end])
    
    def write_block(self, block_index: int, data: bytes):
        """写入物理块"""
        if not (0 <= block_index < self.block_count):
            raise ValueError(f"块索引越界: {block_index}")
        
        if len(data) > self.block_size:
            data = data[:self.block_size]
        elif len(data) < self.block_size:
            data = data.ljust(self.block_size, b'\0')
        
        start = block_index * self.block_size
        self.disk_mmap[start:start + self.block_size] = data
        self.disk_mmap.flush(start, self.block_size)
    
    def flush(self):
        """强制同步到磁盘"""
        if self.disk_mmap:
            self.disk_mmap.flush()
    
    def close(self):
        """安全关闭"""
        try:
            if self.disk_mmap:
                self.disk_mmap.flush()
                self.disk_mmap.close()
            if self.fd:
                self.fd.close()
            logger.info("✅ 磁盘管理器已关闭")
        except Exception as e:
            logger.error(f"关闭错误: {e}")
