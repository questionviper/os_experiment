"""
FAT表管理器 - 实现任务书1-(2)(3)
数据组织: FAT显式链接方式
空闲块管理: 直接基于FAT表
"""

from config import SystemConfig
from utils import logger

class FATManager:
    """
    文件分配表管理器
    实现任务书要求的FAT显式链接和空闲块管理
    """
    
    def __init__(self, disk, buffer_manager): # 接收 buffer_manager
        self.disk = disk
        self.buffer = buffer_manager  # 保存引用
        self.fat_start_block = SystemConfig.FAT_START
        self.fat_blocks = SystemConfig.FAT_BLOCKS
        self.entries_per_block = SystemConfig.BLOCK_SIZE // 4
        self.total_entries = self.entries_per_block * self.fat_blocks
        
        self._free_cache = None
        self._initialize_fat()
        logger.info("FAT表管理器初始化完成")
    
    def _initialize_fat(self):
        """初始化FAT表"""
        try:
            first_entry = self._read_entry(0)
            if first_entry == SystemConfig.FAT_RESERVED:
                logger.info("FAT表已存在")
                return
            
            logger.info("初始化FAT表...")
            fat_buffer = bytearray(self.disk.block_size * self.fat_blocks)
            
            # 保留前2项
            fat_buffer[0:4] = SystemConfig.FAT_RESERVED.to_bytes(4, 'little')
            fat_buffer[4:8] = SystemConfig.FAT_RESERVED.to_bytes(4, 'little')
            
            # 其余初始化为FREE
            max_block = min(self.total_entries, SystemConfig.TOTAL_BLOCKS)
            for i in range(2, max_block):
                offset = i * 4
                if offset + 4 <= len(fat_buffer):
                    fat_buffer[offset:offset + 4] = SystemConfig.FAT_FREE.to_bytes(4, 'little')
            
            for i in range(self.fat_blocks):
                start = i * self.disk.block_size
                end = start + self.disk.block_size
                self.disk.write_block(self.fat_start_block + i, fat_buffer[start:end])
            
            logger.info("FAT表初始化完成")
        except Exception as e:
            logger.error(f"FAT初始化失败: {e}")
    
    def _read_entry(self, entry_index: int) -> int:
        """读取FAT表项 - 走缓冲"""
        if entry_index < 0 or entry_index >= self.total_entries:
            raise ValueError(f"FAT索引越界: {entry_index}")
        
        block_offset = entry_index // self.entries_per_block
        entry_offset = (entry_index % self.entries_per_block) * 4
        
        # [修改点] 改为从 buffer 读取，Owner 设为 "FAT"
        block_id = self.fat_start_block + block_offset
        block_data = self.buffer.read_page(block_id, owner="FAT")
        
        return int.from_bytes(block_data[entry_offset:entry_offset + 4], 'little')
    
    def _write_entry(self, entry_index: int, value: int):
        """写入FAT表项 - 走缓冲"""
        if entry_index < 0 or entry_index >= self.total_entries:
            raise ValueError(f"FAT索引越界: {entry_index}")
        
        block_offset = entry_index // self.entries_per_block
        entry_offset = (entry_index % self.entries_per_block) * 4
        block_id = self.fat_start_block + block_offset
        
        # [修改点] 读-改-写 逻辑
        # 1. 从缓冲读取当前块 (bytearray转换以便修改)
        original_data = bytearray(self.buffer.read_page(block_id, owner="FAT"))
        
        # 2. 修改对应位置的4字节
        original_data[entry_offset:entry_offset + 4] = value.to_bytes(4, 'little')
        
        # 3. 写回缓冲 (标记为 Dirty)
        self.buffer.write_page(block_id, bytes(original_data), owner="FAT")
        
        self._free_cache = None
    
    def allocate_block(self) -> int:
        """
        分配空闲块
        实现任务书1-(3): 基于FAT表的空闲块管理
        """
        if self._free_cache is None:
            self._rebuild_free_cache()
        
        if not self._free_cache:
            logger.warning("无空闲块")
            return -1
        
        block_id = self._free_cache.pop(0)
        self._write_entry(block_id, SystemConfig.FAT_EOF)
        logger.debug(f"分配块: {block_id}")
        return block_id
    
    def free_block(self, block_index: int):
        """释放块"""
        if block_index == -1:
            return
        
        if block_index < 2 or block_index >= self.total_entries:
            return
        
        self._write_entry(block_index, SystemConfig.FAT_FREE)
        logger.debug(f"释放块: {block_index}")
    
    def get_file_blocks(self, start_block: int) -> list:
        """
        获取文件块链
        实现任务书1-(2): FAT显式链接
        """
        if start_block == -1:
            return []
        
        if start_block < 0 or start_block >= self.total_entries:
            raise ValueError(f"起始块越界: {start_block}")
        
        blocks = []
        current = start_block
        visited = set()
        max_hops = SystemConfig.TOTAL_BLOCKS * 2
        hops = 0
        
        while current != SystemConfig.FAT_FREE and current != SystemConfig.FAT_EOF:
            if current < 0 or current >= self.total_entries:
                logger.warning(f"块链异常: {current}")
                break
            
            if current in visited:
                logger.warning(f"检测到FAT环路: {current}")
                break
            
            blocks.append(current)
            visited.add(current)
            
            if len(blocks) > self.total_entries or hops > max_hops:
                logger.warning("块链过长，强制中断")
                break
            
            hops += 1
            next_val = self._read_entry(current)
            
            if next_val >= SystemConfig.FAT_EOF:
                break
            
            current = next_val
        
        return blocks
    
    def get_free_blocks(self) -> list:
        """
        获取空闲块列表
        实现任务书1-(3): 查询返回剩余空闲块
        """
        if self._free_cache is None:
            self._rebuild_free_cache()
        return self._free_cache.copy()
    
    def _rebuild_free_cache(self):
        """重建空闲块缓存"""
        free_blocks = []
        max_block = min(self.total_entries, SystemConfig.TOTAL_BLOCKS)
        
        for i in range(SystemConfig.DATA_START, max_block):
            if self._read_entry(i) == SystemConfig.FAT_FREE:
                free_blocks.append(i)
        
        self._free_cache = free_blocks
        logger.debug(f"空闲块: {len(free_blocks)}个")
    
    def mark_system_blocks(self):
        """标记系统保留块"""
        for i in range(self.fat_start_block, self.fat_start_block + self.fat_blocks):
            if i < self.total_entries:
                self._write_entry(i, SystemConfig.FAT_RESERVED + 1)
        
        for i in range(SystemConfig.DIR_START, SystemConfig.DATA_START):
            if i < self.total_entries:
                self._write_entry(i, SystemConfig.FAT_RESERVED + 2)
        
        if 0 < self.total_entries:
            self._write_entry(0, SystemConfig.FAT_RESERVED + 3)
        
        self.buffer.flush_all()
        logger.info("系统块已标记")
    

