import time
import threading
from utils import logger
from config import SystemConfig

class BufferPage:
    def __init__(self, page_id: int):
        self.page_id = page_id
        self.block_id = -1
        self.data = bytearray(64)
        self.is_dirty = False
        self.last_access = 0
        self.owner = None

class BufferManager:
    def __init__(self, disk, capacity: int = 8):
        self.disk = disk
        self.capacity = capacity
        self.pool = [BufferPage(i) for i in range(capacity)]
        self.lock = threading.RLock()
        self.stats = {'hit': 0, 'miss': 0, 'evict': 0, 'writeback': 0}

    def read_page(self, block_id: int, owner: str = None) -> bytes:
        with self.lock:
            # 1. 查找是否命中
            for page in self.pool:
                if page.block_id == block_id:
                    page.last_access = time.time()
                    page.owner = owner
                    self.stats['hit'] += 1
                    return bytes(page.data)
            
            # 2. 缺页逻辑
            self.stats['miss'] += 1
            time.sleep(0.001) # 任务书延时
            
            raw_data = self.disk.read_block(block_id)
            
            # 3. 置换算法 (LRU)
            target = None
            for p in self.pool:
                if p.block_id == -1: target = p; break
            
            if not target:
                target = min(self.pool, key=lambda p: p.last_access)
                if target.is_dirty:
                    self.disk.write_block(target.block_id, bytes(target.data))
                    self.stats['writeback'] += 1
                self.stats['evict'] += 1

            # 4. 更新缓冲内容
            target.block_id = block_id
            target.data = bytearray(raw_data)
            target.is_dirty = False
            target.last_access = time.time()
            target.owner = owner or "SYS"
            return bytes(target.data)

    def write_page(self, block_id: int, data: bytes, owner: str = None):
        with self.lock:
            # 规范化数据长度为 64B
            buf_data = data[:64].ljust(64, b'\0')
            
            target = None
            for p in self.pool:
                if p.block_id == block_id: target = p; break
            
            if not target:
                # 如果没命中，先调用 read_page 建立页面映射
                self.read_page(block_id, owner)
                for p in self.pool:
                    if p.block_id == block_id: target = p; break
            
            if target:
                target.data[:] = buf_data
                target.is_dirty = True
                target.last_access = time.time()
                target.owner = owner

    def flush_all(self):
        with self.lock:
            for p in self.pool:
                if p.block_id != -1 and p.is_dirty:
                    self.disk.write_block(p.block_id, bytes(p.data))
                    p.is_dirty = False
            self.disk.flush()

    def invalidate(self, block_id: int):
        with self.lock:
            for p in self.pool:
                if p.block_id == block_id:
                    p.block_id = -1
                    p.is_dirty = False

    def get_status(self):
        total = self.stats['hit'] + self.stats['miss']
        hr = (self.stats['hit']/total*100) if total > 0 else 0
        return {
            'pages': [{'page_id': p.page_id, 'block_id': p.block_id, 'is_dirty': p.is_dirty, 'owner': p.owner} for p in self.pool],
            'statistics': {**self.stats, 'hit_ratio': f"{hr:.1f}%"}
        }
    
