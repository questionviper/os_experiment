"""
目录管理器 (多级目录增强版)
实现任务书1-(1): 支持多级目录形式
"""

from config import SystemConfig
from utils import logger
from .fcb import FCB

class DirectoryManager:
    """
    目录管理器
    支持多级目录：
    - 根目录: 存放在固定盘块 (DIR_START - DIR_START+DIR_BLOCKS)
    - 子目录: 存放在数据区，由 FAT 链连接，内部结构同根目录
    """
    
    def __init__(self, disk, buffer_manager, fat_manager): # 接收 buffer
        self.disk = disk
        self.buffer = buffer_manager # 保存引用
        self.fat = fat_manager
        
        self.root_start_block = SystemConfig.DIR_START
        self.root_blocks_count = SystemConfig.DIR_BLOCKS
        self.entries_per_block = SystemConfig.BLOCK_SIZE // 64
        
        self._initialize_root_dir()
    
    def _initialize_root_dir(self):
        """初始化根目录区"""
        first_block = self.disk.read_block(self.root_start_block)
        # 检查是否已初始化
        pass 
        logger.info("目录管理器初始化完成")
        
    def resolve_path(self, path: str) -> tuple:
        """
        解析路径
        Args:
            path: 如 "/home/user/doc.txt"
        Returns:
            (parent_fcb, target_fcb)
        """
        if not path or path == '/':
            return None, None # Root self
        
        parts = [p for p in path.split('/') if p]
        if not parts:
            return None, None
        
        current_dir_fcb = None # Start at Root
        
        # 遍历路径部件，直到倒数第二个
        for i in range(len(parts) - 1):
            part = parts[i]
            # 在当前目录下寻找 part
            found = self._find_in_dir(current_dir_fcb, part)
            
            if not found:
                raise FileNotFoundError(f"目录不存在: {part}")
            
            if not found.is_directory:
                raise NotADirectoryError(f"不是目录: {part}")
            
            current_dir_fcb = found
        
        # 查找最后一个部件
        target_name = parts[-1]
        target_fcb = self._find_in_dir(current_dir_fcb, target_name)
        
        return current_dir_fcb, target_fcb

    def list_directory(self, path: str) -> list:
        """列出指定路径下的所有文件"""
        if path == '/' or path == '':
            parent_fcb = None
        else:
            parent_fcb, target_fcb = self.resolve_path(path)
            # 如果路径指向某个特定的文件夹，则 target_fcb 就是我们要列出的对象
            if target_fcb:
                if not target_fcb.is_directory:
                    raise NotADirectoryError(f"{path} 不是目录")
                parent_fcb = target_fcb
            elif parent_fcb is None and len([p for p in path.split('/') if p]) > 0:
                 raise FileNotFoundError(f"路径不存在: {path}")

        return self._read_dir_entries(parent_fcb)

    def add_entry(self, parent_path: str, fcb: FCB) -> bool:
        """在指定目录下添加FCB"""
        if parent_path == '/' or parent_path == '':
            parent_fcb = None
        else:
            _, parent_fcb = self.resolve_path(parent_path)
            if parent_fcb and not parent_fcb.is_directory:
                raise NotADirectoryError(f"{parent_path} 不是目录")
            if parent_fcb is None:
                 if len([p for p in parent_path.split('/') if p]) > 0:
                     raise FileNotFoundError(f"父目录不存在: {parent_path}")
        
        return self._write_fcb_to_dir(parent_fcb, fcb)

    def remove_entry(self, path: str) -> bool:
        """删除指定路径的文件/目录"""
        parent_fcb, target_fcb = self.resolve_path(path)
        
        if not target_fcb:
            return False
        
        # 如果是目录，必须为空才能删除
        if target_fcb.is_directory:
            children = self._read_dir_entries(target_fcb)
            if children:
                logger.warning("不能删除非空目录")
                return False
        
        return self._delete_fcb_from_dir(parent_fcb, target_fcb.name)
    
    def update_entry(self, parent_dir_fcb, fcb: FCB):
        """更新FCB信息"""
        blocks = self._get_dir_blocks(parent_dir_fcb)
        fcb_bytes = fcb.to_bytes()
        
        for blk_idx in blocks:
            # [修改点] 走缓冲读取
            data = bytearray(self.buffer.read_page(blk_idx, owner="DIR"))
            modified = False
            for i in range(self.entries_per_block):
                offset = i * 64
                entry = data[offset : offset + 64]
                if all(b == 0 for b in entry): continue
                
                curr = FCB.from_bytes(entry)
                if curr and curr.name == fcb.name:
                    data[offset : offset + 64] = fcb_bytes
                    modified = True
                    break
            
            if modified:
                # [修改点] 走缓冲写入
                self.buffer.write_page(blk_idx, bytes(data), owner="DIR")
                return True
        return False

    # ================= 内部辅助方法 =================

    def _get_dir_blocks(self, dir_fcb: FCB) -> list:
        """获取目录占用的所有物理块号"""
        if dir_fcb is None:
            # 根目录：固定区域
            return list(range(self.root_start_block, self.root_start_block + self.root_blocks_count))
        else:
            # 子目录：通过FAT获取链
            if dir_fcb.start_block == -1:
                return []
            return self.fat.get_file_blocks(dir_fcb.start_block)

    def _read_dir_entries(self, dir_fcb: FCB) -> list:
        """读取目录下的所有FCB"""
        blocks = self._get_dir_blocks(dir_fcb)
        entries = []
        
        for blk_idx in blocks:
            # [修改点] 走缓冲
            data = self.buffer.read_page(blk_idx, owner="DIR")
            for i in range(self.entries_per_block):
                offset = i * 64
                fcb = FCB.from_bytes(data[offset : offset + 64])
                if fcb:
                    entries.append(fcb)
        return entries

    def _find_in_dir(self, dir_fcb: FCB, name: str) -> FCB:
        """在指定目录查找名字"""
        entries = self._read_dir_entries(dir_fcb)
        for e in entries:
            if e.name == name:
                return e
        return None

    def _write_fcb_to_dir(self, dir_fcb: FCB, new_fcb: FCB) -> bool:
        """将FCB写入目录"""
        blocks = self._get_dir_blocks(dir_fcb)
        fcb_bytes = new_fcb.to_bytes()
        
        # 1. 尝试在现有块中找空位
        for blk_idx in blocks:
            # [修改点]
            data = bytearray(self.buffer.read_page(blk_idx, owner="DIR"))
            for i in range(self.entries_per_block):
                offset = i * 64
                if all(b == 0 for b in data[offset : offset + 64]):
                    data[offset : offset + 64] = fcb_bytes
                    # [修改点]
                    self.buffer.write_page(blk_idx, bytes(data), owner="DIR")
                    return True
        
        # 2. 如果是根目录且满了 -> 失败
        if dir_fcb is None:
            logger.error("根目录已满")
            return False
            
        # 3. 如果是子目录且满了 -> 分配新块 (目录扩容)
        new_block = self.fat.allocate_block()
        if new_block == -1:
            logger.error("磁盘已满，无法扩容目录")
            return False
        
        # 链接FAT
        if blocks:
            last_block = blocks[-1]
            self.fat._write_entry(last_block, new_block)
        else:
            pass

        data = bytearray(SystemConfig.BLOCK_SIZE)
        data[0:64] = fcb_bytes
        self.buffer.write_page(new_block, bytes(data), owner="DIR")
        return True

    def _delete_fcb_from_dir(self, dir_fcb: FCB, name: str) -> bool:
        """从目录中逻辑删除FCB"""
        blocks = self._get_dir_blocks(dir_fcb)
        for blk_idx in blocks:
            data = bytearray(self.buffer.read_page(blk_idx, owner="DIR"))
            modified = False
            for i in range(self.entries_per_block):
                offset = i * 64
                entry = data[offset : offset + 64]
                if all(b == 0 for b in entry): continue
                
                curr = FCB.from_bytes(entry)
                if curr and curr.name == name:
                    data[offset : offset + 64] = b'\0' * 64
                    modified = True
                    break
            if modified:
                self.buffer.write_page(blk_idx, bytes(data), owner="DIR")
                return True
        return False
