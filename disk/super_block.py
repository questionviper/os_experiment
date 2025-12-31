"""
超级块 - 存储文件系统元数据
"""

import struct
from config import SystemConfig

class SuperBlock:
    """超级块(64字节)"""
    
    def __init__(self):
        self.magic = SystemConfig.DISK_MAGIC
        self.version = SystemConfig.VERSION
        self.block_size = SystemConfig.BLOCK_SIZE
        self.total_blocks = SystemConfig.TOTAL_BLOCKS
        self.fat_start = SystemConfig.FAT_START
        self.fat_blocks = SystemConfig.FAT_BLOCKS
        self.dir_start = SystemConfig.DIR_START
        self.dir_blocks = SystemConfig.DIR_BLOCKS
        self.data_start = SystemConfig.DATA_START
    
    def to_bytes(self) -> bytes:
        """序列化为64字节"""
        data = struct.pack(
            '<5sB H I I B I B I',
            self.magic, self.version, self.block_size,
            self.total_blocks, self.fat_start, self.fat_blocks,
            self.dir_start, self.dir_blocks, self.data_start
        )
        return data.ljust(64, b'\0')
    
    @classmethod
    def from_bytes(cls, data: bytes):
        """反序列化"""
        if len(data) < 26:
            raise ValueError("超级块数据不足")
        
        unpacked = struct.unpack('<5sB H I I B I B I', data[:26])
        sb = cls()
        sb.magic = unpacked[0]
        sb.version = unpacked[1]
        sb.block_size = unpacked[2]
        sb.total_blocks = unpacked[3]
        sb.fat_start = unpacked[4]
        sb.fat_blocks = unpacked[5]
        sb.dir_start = unpacked[6]
        sb.dir_blocks = unpacked[7]
        sb.data_start = unpacked[8]
        return sb
