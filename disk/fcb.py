"""
文件控制块(FCB) - 实现任务书1-(1)目录要求
存储：文件名、创建时间、基本权限、盘块信息
"""

import datetime
import struct

class FCB:
    """
    文件控制块(64字节)
    
    布局:
    0-31:   文件名(32B)
    32-35:  文件大小(4B)
    36-39:  起始块号(4B)
    40-47:  创建时间戳(8B)
    48-55:  修改时间戳(8B)
    56:     是否目录(1B) - 0:文件, 1:目录
    57-63:  保留(7B)
    """
    
    def __init__(self, name: str, size: int = 0, start_block: int = -1, is_directory: bool = False):
        if len(name) > 32:
            raise ValueError(f"文件名过长: {name}")
        
        self.name = name
        self.size = size
        self.start_block = start_block
        self.is_directory = is_directory
        self.create_time = datetime.datetime.now()
        self.modify_time = datetime.datetime.now()
        self.permissions = 'rw-r--r--'  # 基本权限/保护模式
    
    def to_bytes(self) -> bytes:
        """序列化"""
        name_bytes = self.name.encode('utf-8')[:32].ljust(32, b'\0')
        size_bytes = struct.pack('<I', self.size)
        block_bytes = struct.pack('<i', self.start_block)
        create_ts = struct.pack('<d', self.create_time.timestamp())
        modify_ts = struct.pack('<d', self.modify_time.timestamp())
        is_dir_bytes = struct.pack('<?', self.is_directory)
        reserved = b'\0' * 7
        
        result = name_bytes + size_bytes + block_bytes + create_ts + modify_ts + is_dir_bytes + reserved
        assert len(result) == 64
        return result
    
    @classmethod
    def from_bytes(cls, data: bytes):
        """反序列化"""
        if len(data) < 64:
            return None
        
        # 检查是否全0(空FCB)
        if all(b == 0 for b in data):
            return None
        
        try:
            name_raw = data[0:32]
            first_null = name_raw.find(b'\0')
            if first_null != -1:
                name_raw = name_raw[:first_null]
            
            name = name_raw.decode('utf-8', errors='ignore').strip()
            if not name:
                return None
            
            size = struct.unpack('<I', data[32:36])[0]
            start_block = struct.unpack('<i', data[36:40])[0]
            create_ts = struct.unpack('<d', data[40:48])[0]
            modify_ts = struct.unpack('<d', data[48:56])[0]
            is_directory = struct.unpack('<?', data[56:57])[0]
            
            fcb = cls(name, size, start_block, is_directory)
            
            try:
                fcb.create_time = datetime.datetime.fromtimestamp(create_ts)
                fcb.modify_time = datetime.datetime.fromtimestamp(modify_ts)
            except:
                pass
            
            return fcb
        except:
            return None
