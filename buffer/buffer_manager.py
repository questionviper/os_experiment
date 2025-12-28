"""
缓冲管理器核心实现
包含BufferPage、BufferStatistics、BufferManager三个核心类
"""

import time
import threading
from typing import Dict, List, Optional, Callable

# ==============================
# 📄 缓冲页数据结构
# ==============================
class BufferPage:
    """
    缓冲页数据结构
    
    对应任务书要求：记录每个缓冲页的所有者、访问时间、是否修改等信息
    
    属性:
        block_id (int): 对应的磁盘块号
        data (bytearray): 页面数据内容（可修改）
        is_dirty (bool): 脏位标志，True表示已被修改需要写回
        last_access_time (float): 最后访问时间戳（用于LRU算法）
        owner (str): 所有者进程标识
        ref_count (int): 引用计数（可选，防止正在使用的页被淘汰）
    """
    
    def __init__(self, block_id: int, data: bytes):
        """
        初始化缓冲页
        
        Args:
            block_id: 磁盘块号
            data: 初始数据
        """
        self.block_id = block_id
        self.data = bytearray(data)
        self.is_dirty = False
        self.last_access_time = time.time()
        self.owner = "system"
        self.ref_count = 0
    
    def touch(self):
        """更新访问时间（每次访问时调用）"""
        self.last_access_time = time.time()
    
    def acquire(self):
        """增加引用计数"""
        self.ref_count += 1
        self.touch()
    
    def release(self):
        """减少引用计数"""
        self.ref_count = max(0, self.ref_count - 1)


# ==============================
# 📊 性能统计模块
# ==============================
class BufferStatistics:
    """
    缓冲区性能统计
    
    用于记录和展示缓冲池的运行效果，包括命中率、淘汰次数等关键指标
    """
    
    def __init__(self):
        """初始化统计计数器"""
        self.hit_count = 0          # 缓存命中次数
        self.miss_count = 0         # 缺页次数
        self.evict_count = 0        # 页面淘汰次数
        self.writeback_count = 0    # 脏页回写次数
        self._lock = threading.Lock()  # 线程安全锁
    
    def record_hit(self):
        """记录一次缓存命中"""
        with self._lock:
            self.hit_count += 1
    
    def record_miss(self):
        """记录一次缺页"""
        with self._lock:
            self.miss_count += 1
    
    def record_eviction(self, was_dirty: bool):
        """
        记录一次页面淘汰
        
        Args:
            was_dirty: 被淘汰的页面是否为脏页
        """
        with self._lock:
            self.evict_count += 1
            if was_dirty:
                self.writeback_count += 1
    
    def get_hit_ratio(self) -> float:
        """
        计算缓存命中率
        
        Returns:
            命中率（0.0-1.0之间）
        """
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else 0.0
    
    def get_summary(self) -> dict:
        """
        返回统计摘要
        
        Returns:
            包含所有统计信息的字典
        """
        return {
            'hit': self.hit_count,
            'miss': self.miss_count,
            'evict': self.evict_count,
            'writeback': self.writeback_count,
            'hit_ratio': f"{self.get_hit_ratio() * 100:.1f}%",
            'total_access': self.hit_count + self.miss_count
        }
    
    def reset(self):
        """重置所有统计计数器"""
        with self._lock:
            self.hit_count = 0
            self.miss_count = 0
            self.evict_count = 0
            self.writeback_count = 0


# ==============================
# 🧠 缓冲管理器核心
# ==============================
class BufferManager:
    """
    内存缓冲管理器
    
    核心功能：
    1. 管理M×K大小的缓冲池（M=块大小，K=页面数量）
    2. 实现LRU（最近最少使用）页面置换算法
    3. 处理脏页回写机制
    4. 提供缓存命中率统计
    5. 支持线程安全操作
    
    使用示例:
        >>> buffer = BufferManager(disk_manager, capacity=8)
        >>> 
        >>> # 读取（自动缓存）
        >>> data = buffer.read_page(block_id)
        >>> 
        >>> # 写入（标记脏页）
        >>> buffer.write_page(block_id, new_data)
        >>> 
        >>> # 关闭前刷新
        >>> buffer.flush_all()
    """
    
    def __init__(self, disk_manager, capacity: int = 8, enable_logging: bool = False):
        """
        初始化缓冲管理器
        
        Args:
            disk_manager: 磁盘管理器对象（需实现read_block和write_block方法）
            capacity: 缓冲池容量（页面数量），默认8页
            enable_logging: 是否启用日志记录
        """
        self.disk = disk_manager
        self.capacity = capacity
        self.buffer_pool: Dict[int, BufferPage] = {}  # 核心数据结构
        self.stats = BufferStatistics()
        self.enable_logging = enable_logging
        self._lock = threading.RLock()  # 可重入锁
        
        if self.enable_logging:
            self._log("BufferManager initialized", f"capacity={capacity}")
    
    def _log(self, event: str, detail: str = ""):
        """内部日志方法"""
        if self.enable_logging:
            timestamp = time.strftime('%H:%M:%S')
            print(f"[{timestamp}] [BUFFER] {event}: {detail}")
    
    def read_page(self, block_id: int, callback: Optional[Callable] = None) -> bytes:
        """
        读取页面（核心方法）
        
        工作流程:
            1. 检查缓冲池中是否存在该页（缓存命中）
            2. 如果命中，更新访问时间并返回数据
            3. 如果未命中（缺页），从磁盘加载
            4. 如果缓冲池已满，执行LRU置换算法
        
        Args:
            block_id: 要读取的磁盘块号
            callback: 可选的回调函数，用于通知UI更新
            
        Returns:
            块的数据内容（bytes类型）
            
        Raises:
            ValueError: 如果块号无效
        """
        with self._lock:
            # 情况1：缓存命中
            if block_id in self.buffer_pool:
                page = self.buffer_pool[block_id]
                page.touch()
                self.stats.record_hit()
                
                if callback:
                    callback(block_id, is_hit=True)
                
                self._log("Cache HIT", f"block={block_id}")
                return bytes(page.data)
            
            # 情况2：缓存未命中（缺页）
            self.stats.record_miss()
            self._log("Cache MISS", f"block={block_id}")
            
            # 检查缓冲池是否已满
            if len(self.buffer_pool) >= self.capacity:
                self._evict_lru()
            
            # 从磁盘读取数据
            if callback:
                callback(block_id, is_hit=False)
            
            disk_data = self.disk.read_block(block_id)
            
            # 创建新页面并加入缓冲池
            new_page = BufferPage(block_id, disk_data)
            self.buffer_pool[block_id] = new_page
            
            return bytes(new_page.data)
    
    def write_page(self, block_id: int, data: bytes):
        """
        写入页面（核心方法）
        
        工作流程:
            1. 确保页面在缓冲池中（如果不在则先加载）
            2. 更新页面数据
            3. 标记为脏页（稍后需要写回磁盘）
        
        Args:
            block_id: 要写入的块号
            data: 新数据
        """
        with self._lock:
            # 如果页面不在缓冲中，先读取进来（Write Allocation策略）
            if block_id not in self.buffer_pool:
                self.read_page(block_id)
            
            page = self.buffer_pool[block_id]
            
            # 数据规范化（对齐块大小）
            if len(data) > self.disk.block_size:
                data = data[:self.disk.block_size]
            elif len(data) < self.disk.block_size:
                data = data.ljust(self.disk.block_size, b'\0')
            
            # 更新数据并标记为脏
            page.data = bytearray(data)
            page.is_dirty = True
            page.touch()
            
            self._log("Page WRITE", f"block={block_id}, dirty=True")
    
    def _evict_lru(self):
        """
        LRU页面置换算法（核心算法）
        
        算法流程:
            1. 遍历缓冲池，找到last_access_time最小的页面（最久未使用）
            2. 检查该页面的引用计数（避免淘汰正在使用的页）
            3. 如果该页是脏页，先写回磁盘
            4. 从缓冲池中移除该页面
        
        注意:
            这个方法只在缓冲池满时由read_page内部调用
        """
        # 找到可淘汰的页面（引用计数为0）
        candidates = {
            bid: page for bid, page in self.buffer_pool.items()
            if page.ref_count == 0
        }
        
        if not candidates:
            # 极端情况：所有页都被锁定
            self._log("Eviction FAILED", "All pages are locked")
            raise RuntimeError("缓冲池已满且所有页面都被占用")
        
        # 选择最久未使用的
        victim_block_id = min(
            candidates.keys(),
            key=lambda bid: candidates[bid].last_access_time
        )
        
        victim_page = self.buffer_pool[victim_block_id]
        
        # 脏页回写
        if victim_page.is_dirty:
            self.disk.write_block(victim_block_id, bytes(victim_page.data))
            self.stats.record_eviction(was_dirty=True)
            self._log("Eviction DIRTY", f"block={victim_block_id} (written back)")
        else:
            self.stats.record_eviction(was_dirty=False)
            self._log("Eviction CLEAN", f"block={victim_block_id} (discarded)")
        
        # 从缓冲池删除
        del self.buffer_pool[victim_block_id]
    
    def flush_all(self):
        """
        刷新所有脏页到磁盘
        
        应用场景:
            - 系统正常关闭时
            - 用户手动同步时
            - 确保数据持久化时
        """
        with self._lock:
            dirty_count = 0
            for block_id, page in list(self.buffer_pool.items()):
                if page.is_dirty:
                    self.disk.write_block(block_id, bytes(page.data))
                    page.is_dirty = False
                    dirty_count += 1
            
            self._log("Flush ALL", f"{dirty_count} dirty pages written")
    
    def invalidate(self, block_id: int):
        """
        使某个页面失效（如文件删除时调用）
        
        流程:
            1. 检查页面是否在缓冲池中
            2. 如果是脏页，先写回磁盘
            3. 从缓冲池删除
        
        Args:
            block_id: 要失效的块号
        """
        with self._lock:
            if block_id in self.buffer_pool:
                page = self.buffer_pool[block_id]
                
                if page.is_dirty:
                    self.disk.write_block(block_id, bytes(page.data))
                    self._log("Invalidate DIRTY", f"block={block_id} (written back)")
                else:
                    self._log("Invalidate CLEAN", f"block={block_id} (discarded)")
                
                del self.buffer_pool[block_id]
    
    def get_status(self) -> dict:
        """
        获取缓冲区状态（供UI显示）
        
        Returns:
            包含以下信息的字典:
                - capacity: 缓冲池总容量
                - used: 当前使用的页面数
                - free: 剩余容量
                - pages: 页面详情列表（按访问时间排序）
                - statistics: 统计信息
        """
        with self._lock:
            # 按访问时间排序（最新的在前）
            sorted_pages = sorted(
                self.buffer_pool.values(),
                key=lambda p: p.last_access_time,
                reverse=True
            )
            
            pages_info = []
            for page in sorted_pages:
                pages_info.append({
                    'block_id': page.block_id,
                    'is_dirty': page.is_dirty,
                    'ref_count': page.ref_count,
                    'last_access': time.strftime('%H:%M:%S', time.localtime(page.last_access_time)),
                    'data_preview': str(bytes(page.data[:10]))
                })
            
            return {
                'capacity': self.capacity,
                'used': len(self.buffer_pool),
                'free': self.capacity - len(self.buffer_pool),
                'pages': pages_info,
                'statistics': self.stats.get_summary()
            }
    
    def clear(self):
        """
        清空缓冲池（需先刷新脏页）
        
        Warning:
            这会丢失所有未写回的数据！正常情况下应先调用flush_all()
        """
        with self._lock:
            self.flush_all()
            self.buffer_pool.clear()
            self._log("Buffer CLEARED", "")
