import os
import time
import threading
import mmap
import datetime
import json
from typing import Dict, List, Optional, Tuple
import platform
import sys
import multiprocessing.shared_memory as shm


# ==============================
# 🔷 文件控制块（保持不变）
# ==============================
class FCB:
    def __init__(self, name: str, size: int = 0, start_block: int = -1):
        self.name = name
        self.size = size
        self.start_block = start_block
        self.create_time = datetime.datetime.now()
        self.permissions = 'rw-r--r--'

    def to_bytes(self) -> bytes:
        try:
            data_dict = {
                'name': self.name,
                'size': self.size,
                'start_block': self.start_block,
                'create_time': self.create_time.isoformat(),
                'permissions': self.permissions
            }
            json_str = json.dumps(data_dict, ensure_ascii=False)
            if len(json_str) > 62:
                truncated_data = {
                    'name': self.name[:10] + '...' if len(self.name) > 10 else self.name,
                    'size': self.size,
                    'start_block': self.start_block
                }
                json_str = json.dumps(truncated_data, ensure_ascii=False)
            padded_str = json_str.ljust(63, '\0') + '\0'
            return padded_str.encode('utf-8')[:64]
        except Exception as e:
            return b'\0' * 64

    @classmethod
    def from_bytes(cls, data_input):
        try:
            if not data_input or len(data_input) < 4:
                return None
            null_pos = data_input.find(b'\0')
            if null_pos == -1:
                null_pos = len(data_input)
            json_bytes = data_input[:null_pos]
            if not json_bytes:
                return None
            json_str = json_bytes.decode('utf-8', errors='ignore').strip()
            if not json_str:
                return None
            try:
                json_data = json.loads(json_str)
            except json.JSONDecodeError:
                if json_str.endswith('"') and not json_str.endswith('}'):
                    json_str += '}'
                try:
                    json_data = json.loads(json_str)
                except:
                    return None
            fcb = cls(
                json_data.get('name', 'unknown'),
                json_data.get('size', 0),
                json_data.get('start_block', -1)
            )
            if 'create_time' in json_data:
                try:
                    fcb.create_time = datetime.datetime.fromisoformat(json_data['create_time'])
                except:
                    fcb.create_time = datetime.datetime.now()
            fcb.permissions = json_data.get('permissions', 'rw-r--r--')
            return fcb
        except Exception as e:
            return None


# ==============================
# 📡 共享内存接口（保留）
# ==============================
class SharedMemoryInterface:
    def __init__(self, name: str = "fat_cmd", size: int = 65536):
        self.name = name
        self.size = size
        self.shm = None
        self._connected = False

    def create(self):
        try:
            self.shm = shm.SharedMemory(name=self.name)
            self._connected = True
        except FileNotFoundError:
            self.shm = shm.SharedMemory(name=self.name, create=True, size=self.size)
            self._connected = True

    def write(self, data: bytes):
        if not self._connected:
            raise RuntimeError("call create() first")
        if len(data) > self.shm.size:
            raise ValueError(f"data too large: {len(data)} > {self.shm.size}")
        self.shm.buf[:len(data)] = data
        self.shm.buf[len(data):] = b'\0' * (self.shm.size - len(data))

    def read(self) -> bytes:
        if not self._connected:
            raise RuntimeError("call create() first")
        data = bytes(self.shm.buf)
        null_pos = data.find(b'\x00')
        return data[:null_pos] if null_pos != -1 else data

    def close(self):
        if self.shm:
            self.shm.close()
            self._connected = False

    def unlink(self):
        if self.shm:
            self.shm.close()
            try:
                self.shm.unlink()
            except:
                pass
            self._connected = False

    def __enter__(self):
        self.create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ==============================
# 🧱 磁盘管理器（保持不变）
# ==============================
class DiskManager:
    def __init__(self, disk_path: str, block_size: int = 64, block_count: int = 1024):
        self.disk_path = disk_path
        self.block_size = block_size
        self.block_count = block_count
        self.total_size = block_size * block_count
        self._initialize_disk()
        self._map_disk()

    def _initialize_disk(self):
        if not os.path.exists(self.disk_path):
            with open(self.disk_path, 'wb') as f:
                f.seek(self.total_size - 1)
                f.write(b'\0')

    def _map_disk(self):
        self.fd = open(self.disk_path, 'r+b')
        self.mmap = mmap.mmap(self.fd.fileno(), 0)

    def read_block(self, block_index: int) -> bytes:
        if block_index < 0 or block_index >= self.block_count:
            raise ValueError(f"无效的块索引: {block_index}")
        start = block_index * self.block_size
        end = start + self.block_size
        return self.mmap[start:end]

    def write_block(self, block_index: int, data: bytes):
        if block_index < 0 or block_index >= self.block_count:
            raise ValueError(f"无效的块索引: {block_index}")
        if len(data) > self.block_size:
            data = data[:self.block_size]
        elif len(data) < self.block_size:
            data = data.ljust(self.block_size, b'\0')
        start = block_index * self.block_size
        self.mmap[start:start + self.block_size] = data

    def close(self):
        try:
            self.mmap.flush()
            self.mmap.close()
            self.fd.close()
        except Exception:
            pass


# ==============================
# FAT管理器（保持不变）
# ==============================
class FATManager:
    def __init__(self, disk: DiskManager, fat_start_block: int = 1, fat_blocks: int = 16):
        self.disk = disk
        self.fat_start_block = fat_start_block
        self.fat_blocks = fat_blocks
        self.fat_entries_per_block = disk.block_size // 4
        self.total_fat_entries = self.fat_entries_per_block * fat_blocks
        self._initialize_fat()

    def _initialize_fat(self):
        fat_buffer = bytearray(self.disk.block_size * self.fat_blocks)
        fat_buffer[0:4] = b'\xF8\xFF\xFF\xFF'
        fat_buffer[4:8] = b'\xFF\xFF\xFF\xFF'
        max_block_to_init = min(self.total_fat_entries, self.disk.block_count)
        for i in range(2, max_block_to_init):
            offset = i * 4
            if offset + 4 <= len(fat_buffer):
                fat_buffer[offset:offset + 4] = b'\xFF\xFF\xFF\xFF'
        for i in range(self.fat_blocks):
            start = i * self.disk.block_size
            end = start + self.disk.block_size
            block_data = fat_buffer[start:end]
            if len(block_data) < self.disk.block_size:
                block_data += b'\0' * (self.disk.block_size - len(block_data))
            self.disk.write_block(self.fat_start_block + i, block_data)

    def _read_fat_entry(self, entry_index: int) -> int:
        if entry_index < 0 or entry_index >= self.total_fat_entries:
            raise ValueError(f"FAT项索引 {entry_index} 超出范围")
        block_offset = entry_index // self.fat_entries_per_block
        entry_offset = (entry_index % self.fat_entries_per_block) * 4
        block_data = self.disk.read_block(self.fat_start_block + block_offset)
        return int.from_bytes(block_data[entry_offset:entry_offset + 4], 'little')

    def _write_fat_entry(self, entry_index: int, value: int):
        if entry_index < 0 or entry_index >= self.total_fat_entries:
            raise ValueError(f"FAT项索引 {entry_index} 超出范围")
        block_offset = entry_index // self.fat_entries_per_block
        entry_offset = (entry_index % self.fat_entries_per_block) * 4
        block_data = bytearray(self.disk.read_block(self.fat_start_block + block_offset))
        block_data[entry_offset:entry_offset + 4] = value.to_bytes(4, 'little')
        self.disk.write_block(self.fat_start_block + block_offset, block_data)

    def allocate_block(self) -> int:
        max_block = min(self.total_fat_entries, self.disk.block_count)
        for i in range(2, max_block):
            if i in [0, 1]: continue
            if self._read_fat_entry(i) == 0xFFFFFFFF:
                self._write_fat_entry(i, 0xFFFFFFFE)
                return i
        return -1

    def free_block(self, block_index: int):
        if block_index < 2 or block_index >= self.total_fat_entries:
            return
        self._write_fat_entry(block_index, 0xFFFFFFFF)

    def get_free_blocks(self) -> List[int]:
        free_blocks = []
        max_block = min(self.total_fat_entries, self.disk.block_count)
        for i in range(2, max_block):
            if self._read_fat_entry(i) == 0xFFFFFFFF:
                free_blocks.append(i)
        return free_blocks

    def get_file_blocks(self, start_block: int) -> List[int]:
        if start_block < 0 or start_block >= self.total_fat_entries:
            raise ValueError(f"起始块 {start_block} 超出范围")
        blocks = []
        current = start_block
        while current != 0xFFFFFFFF and current != 0xFFFFFFFE and current != -1:
            if current < 0 or current >= self.total_fat_entries:
                break
            blocks.append(current)
            if len(blocks) > self.total_fat_entries:
                break
            next_block = self._read_fat_entry(current)
            if next_block == current:
                break
            current = next_block
        return blocks


# ==============================
# 目录管理器（保持不变）
# ==============================
class DirectoryManager:
    def __init__(self, disk: DiskManager, dir_start_block: int = 17, dir_blocks: int = 16, dir_mode: str = 'single'):
        self.disk = disk
        self.dir_start_block = dir_start_block
        self.dir_blocks = dir_blocks
        self.dir_mode = dir_mode
        self.max_files = dir_blocks * (disk.block_size // 64)
        self._initialize_directory()

    def _initialize_directory(self):
        for i in range(self.dir_blocks):
            self.disk.write_block(self.dir_start_block + i, b'\0' * self.disk.block_size)

    def _normalize_name(self, filename: str) -> str:
        if self.dir_mode == 'single':
            return os.path.basename(filename.replace('\\', '/'))
        return filename.replace('\\', '/')

    def add_file(self, fcb: FCB) -> bool:
        name = self._normalize_name(fcb.name)
        for block_idx in range(self.dir_blocks):
            block_data = bytearray(self.disk.read_block(self.dir_start_block + block_idx))
            for entry_idx in range(self.disk.block_size // 64):
                offset = entry_idx * 64
                entry_data = block_data[offset:offset + 64]
                if all(b == 0 for b in entry_data):
                    fcb.name = name
                    fcb_data = fcb.to_bytes()
                    block_data[offset:offset + 64] = fcb_data
                    self.disk.write_block(self.dir_start_block + block_idx, block_data)
                    return True
        return False

    def find_file(self, filename: str) -> Optional[FCB]:
        name = self._normalize_name(filename)
        for block_idx in range(self.dir_blocks):
            block_data = self.disk.read_block(self.dir_start_block + block_idx)
            for entry_idx in range(self.disk.block_size // 64):
                offset = entry_idx * 64
                entry_data = block_data[offset:offset + 64]
                if all(b == 0 for b in entry_data):
                    continue
                fcb = FCB.from_bytes(entry_data)
                if fcb and fcb.name == name:
                    return fcb
        return None

    def list_files(self) -> List[FCB]:
        files = []
        for block_idx in range(self.dir_blocks):
            block_data = self.disk.read_block(self.dir_start_block + block_idx)
            for entry_idx in range(self.disk.block_size // 64):
                offset = entry_idx * 64
                entry_data = block_data[offset:offset + 64]
                if all(b == 0 for b in entry_data):
                    continue
                fcb = FCB.from_bytes(entry_data)
                if fcb:
                    files.append(fcb)
        return files

    def remove_file(self, filename: str) -> bool:
        name = self._normalize_name(filename)
        for block_idx in range(self.dir_blocks):
            block_data = bytearray(self.disk.read_block(self.dir_start_block + block_idx))
            for entry_idx in range(self.disk.block_size // 64):
                offset = entry_idx * 64
                entry_data = block_data[offset:offset + 64]
                if not all(b == 0 for b in entry_data):
                    fcb = FCB.from_bytes(entry_data)
                    if fcb and fcb.name == name:
                        block_data[offset:offset + 64] = b'\0' * 64
                        self.disk.write_block(self.dir_start_block + block_idx, block_data)
                        return True
        return False


# ==============================
# 🎯 文件系统（集成缓冲 - 最小改动）
# ==============================
class FileSystem:
    """FAT 文件系统核心"""

    def __init__(self, disk_path: str = 'simulated_disk.img', dir_mode: str = 'single'):
        # 🔧 动态导入缓冲模块（避免循环依赖）
        try:
            from buffer import BufferManager
            self._buffer_available = True
        except ImportError:
            self._buffer_available = False
        
        assert dir_mode in ('single', 'multi'), "dir_mode must be 'single' or 'multi'"
        self.BLOCK_SIZE = 64
        self.TOTAL_BLOCKS = 1024
        self.DIR_BLOCKS = 16

        entries_per_block = self.BLOCK_SIZE // 4
        required_fat_blocks = (self.TOTAL_BLOCKS + entries_per_block - 1) // entries_per_block
        fat_start_block = 1
        dir_start_block = fat_start_block + required_fat_blocks
        data_start_block = dir_start_block + self.DIR_BLOCKS

        self.disk = DiskManager(disk_path, self.BLOCK_SIZE, self.TOTAL_BLOCKS)
        self.fat = FATManager(self.disk, fat_start_block, required_fat_blocks)
        self.directory = DirectoryManager(self.disk, dir_start_block, self.DIR_BLOCKS, dir_mode=dir_mode)
        self.data_start_block = data_start_block

        # 🆕 初始化缓冲管理器（如果可用）
        if self._buffer_available:
            self.buffer = BufferManager(self.disk, capacity=8)
        else:
            self.buffer = None

        self._lock = threading.RLock()
        self._mark_system_blocks_as_used()

    def _mark_system_blocks_as_used(self):
        fat_start = self.fat.fat_start_block
        fat_end = fat_start + self.fat.fat_blocks - 1
        for i in range(fat_start, fat_end + 1):
            if 0 <= i < self.fat.total_fat_entries:
                self.fat._write_fat_entry(i, 0xFFFFFF01)

        dir_start = self.directory.dir_start_block
        dir_end = dir_start + self.directory.dir_blocks - 1
        for i in range(dir_start, dir_end + 1):
            if 0 <= i < self.fat.total_fat_entries:
                self.fat._write_fat_entry(i, 0xFFFFFF02)

        if 0 < self.fat.total_fat_entries:
            self.fat._write_fat_entry(0, 0xFFFFFF03)

    def create_file(self, filename: str, content: bytes = b'') -> bool:
        if self.directory.find_file(filename):
            return False
        start_block = self.fat.allocate_block()
        if start_block == -1:
            return False
        fcb = FCB(filename, len(content), start_block)
        if content:
            self._write_file_content(fcb, content)
        return self.directory.add_file(fcb)

    def _write_file_content(self, fcb: FCB, content: bytes):
        current_block = fcb.start_block
        remaining = content
        while remaining:
            write_size = min(len(remaining), self.disk.block_size)
            chunk = remaining[:write_size]
            
            # 🆕 使用缓冲（如果可用）
            if self.buffer:
                self.buffer.write_page(current_block, chunk)
            else:
                self.disk.write_block(current_block, chunk)
            
            remaining = remaining[write_size:]
            if remaining:
                next_block = self.fat.allocate_block()
                if next_block == -1:
                    break
                self.fat._write_fat_entry(current_block, next_block)
                current_block = next_block
        fcb.size = len(content) - len(remaining)

    def read_file_block(self, filename: str, block_index: int) -> bytes:
        fcb = self.directory.find_file(filename)
        blocks = self.fat.get_file_blocks(fcb.start_block)
        if block_index >= len(blocks):
            raise IndexError(f"块索引越界")
        
        # 🆕 使用缓冲（如果可用）
        if self.buffer:
            return self.buffer.read_page(blocks[block_index])
        else:
            return self.disk.read_block(blocks[block_index])

    def write_file_block(self, filename: str, block_index: int, data: bytes):
        with self._lock:
            fcb = self.directory.find_file(filename)
            blocks = self.fat.get_file_blocks(fcb.start_block)
            if block_index >= len(blocks):
                raise IndexError(f"块索引越界")
            
            # 🆕 使用缓冲（如果可用）
            if self.buffer:
                self.buffer.write_page(blocks[block_index], data)
            else:
                self.disk.write_block(blocks[block_index], data)

    def get_file_blocks(self, filename: str) -> List[int]:
        fcb = self.directory.find_file(filename)
        return self.fat.get_file_blocks(fcb.start_block)

    def read_file(self, filename: str) -> Optional[bytes]:
        fcb = self.directory.find_file(filename)
        if not fcb or fcb.start_block == -1:
            return None
        content = bytearray()
        blocks = self.fat.get_file_blocks(fcb.start_block)
        
        for block_idx in blocks:
            # 🆕 使用缓冲
            if self.buffer:
                content.extend(self.buffer.read_page(block_idx))
            else:
                content.extend(self.disk.read_block(block_idx))
        
        return bytes(content[:fcb.size])

    def delete_file(self, filename: str) -> bool:
        fcb = self.directory.find_file(filename)
        if not fcb:
            return False
        blocks = self.fat.get_file_blocks(fcb.start_block)
        
        for block in blocks:
            # 🆕 使缓冲失效
            if self.buffer:
                self.buffer.invalidate(block)
            self.fat.free_block(block)
        
        return self.directory.remove_file(filename)

    def get_free_blocks(self) -> List[int]:
        return self.fat.get_free_blocks()

    def get_system_info(self) -> Dict:
        total_managed = min(self.fat.total_fat_entries, self.disk.block_count)
        unmanaged = max(0, self.disk.block_count - self.fat.total_fat_entries)
        free = len(self.get_free_blocks())
        used = total_managed - free - 2
        
        result = {
            'total_blocks': self.disk.block_count,
            'managed_blocks': total_managed,
            'unmanaged_blocks': unmanaged,
            'block_size': self.disk.block_size,
            'free_blocks': free,
            'used_blocks': used,
            'reserved_blocks': 2,
            'files_count': len(self.directory.list_files()),
            'fat_blocks': self.fat.fat_blocks,
            'dir_blocks': self.directory.dir_blocks,
            'data_blocks': self.disk.block_count - (1 + self.fat.fat_blocks + self.directory.dir_blocks),
        }
        
        # 🆕 添加缓冲状态（如果可用）
        if self.buffer:
            result['buffer_status'] = self.buffer.get_status()
        
        return result
    
    def shutdown(self):
        """🆕 安全关闭"""
        if self.buffer:
            self.buffer.flush_all()
        self.disk.close()
