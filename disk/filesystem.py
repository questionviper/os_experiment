# disk/filesystem.py
import threading
import datetime
from config import SystemConfig
from utils import logger
from .disk_manager import DiskManager
from .fat_manager import FATManager
from .directory_manager import DirectoryManager
from .fcb import FCB
from process import CommandTask,TaskScheduler

class FileSystem:
    def __init__(self, disk_path: str = 'os_course_disk.img'):
        self.disk = DiskManager(disk_path)
        
        # 1. 先初始化 BufferManager (它需要 disk)
        from buffer.buffer_manager import BufferManager
        self.buffer = BufferManager(self.disk, capacity=SystemConfig.BUFFER_CAPACITY)
        
        # 2. 将 buffer 传递给 FAT 和 Directory 管理器
        # 注意：这里我们传入 buffer 而不仅仅是 disk
        self.fat = FATManager(self.disk, self.buffer) 
        self.directory = DirectoryManager(self.disk, self.buffer, self.fat)
        
        self.opened_files = set()
        self._lock = threading.RLock()
        
        self.scheduler = TaskScheduler()
        # 标记系统块
        self.fat.mark_system_blocks()

    def _get_parent_and_name(self, full_path: str):
        full_path = full_path.strip('/')
        if '/' not in full_path:
            return '/', full_path
        parts = full_path.rsplit('/', 1)
        return parts[0], parts[1]

    def create_directory(self, path: str) -> bool:
        with self._lock:
            parent_path, dir_name = self._get_parent_and_name(path)
            
            parent_fcb, target = self.directory.resolve_path(path)
            if target: return False
            
            # 分配目录数据块
            start_block = self.fat.allocate_block()
            if start_block == -1: return False
            
            # 初始化目录块全0
            self.disk.write_block(start_block, b'\0' * SystemConfig.BLOCK_SIZE)
            
            new_fcb = FCB(dir_name, size=0, start_block=start_block, is_directory=True)
            return self.directory.add_entry(parent_path, new_fcb)

    def create_file(self, path: str, content: bytes = b'') -> bool:
        with self._lock:
            parent_path, filename = self._get_parent_and_name(path)
            _, existing = self.directory.resolve_path(path)
            if existing: return False
            
            start_block = -1
            if len(content) > 0:
                start_block = self.fat.allocate_block()
                if start_block == -1: return False
                
                curr = start_block
                rem = content
                while len(rem) > 0:
                    chunk = rem[:64]
                    self.buffer.write_page(curr, chunk, owner=filename)
                    rem = rem[64:]
                    if len(rem) > 0:
                        nxt = self.fat.allocate_block()
                        if nxt == -1: break
                        self.fat._write_entry(curr, nxt)
                        curr = nxt
                    else:
                        self.fat._write_entry(curr, SystemConfig.FAT_EOF)
            
            fcb = FCB(filename, len(content), start_block)
            return self.directory.add_entry(parent_path, fcb)

    def read_file(self, path: str) -> bytes:
        with self._lock:
            _, fcb = self.directory.resolve_path(path)
            if not fcb or fcb.is_directory or fcb.start_block == -1: return b''
            
            blocks = self.fat.get_file_blocks(fcb.start_block)
            res = bytearray()
            for b_idx in blocks:
                res.extend(self.buffer.read_page(b_idx, owner=fcb.name))
            return bytes(res[:fcb.size])

    def write_file(self, path: str, content: bytes) -> bool:
        """
        核心优化：智能链式复用写入
        """
        with self._lock:
            parent_path, filename = self._get_parent_and_name(path)
            parent_fcb, fcb = self.directory.resolve_path(path)
            
            if not fcb or fcb.is_directory: return False
            
            if len(content) == 0:
                needed_blocks = 0
            else:
                needed_blocks = (len(content) + SystemConfig.BLOCK_SIZE - 1) // SystemConfig.BLOCK_SIZE

            current_blocks = self.fat.get_file_blocks(fcb.start_block)
            current_count = len(current_blocks)
            final_block_list = []

            if needed_blocks == 0:
                for b in current_blocks:
                    self.buffer.invalidate(b)
                    self.fat.free_block(b)
                fcb.start_block = -1
                final_block_list = []

            elif needed_blocks > current_count:
                final_block_list = list(current_blocks)
                if current_count == 0:
                     first = self.fat.allocate_block()
                     if first == -1: return False
                     fcb.start_block = first
                     final_block_list.append(first)
                     current_count = 1
                
                last_block = final_block_list[-1]
                to_add = needed_blocks - current_count
                for _ in range(to_add):
                    new_b = self.fat.allocate_block()
                    if new_b == -1: return False
                    self.fat._write_entry(last_block, new_b)
                    last_block = new_b
                    final_block_list.append(new_b)
                
                self.fat._write_entry(last_block, SystemConfig.FAT_EOF)

            elif needed_blocks < current_count:
                final_block_list = current_blocks[:needed_blocks]
                blocks_to_free = current_blocks[needed_blocks:]
                for b in blocks_to_free:
                    self.buffer.invalidate(b)
                    self.fat.free_block(b)
                if final_block_list:
                    self.fat._write_entry(final_block_list[-1], SystemConfig.FAT_EOF)
            else:
                final_block_list = current_blocks

            rem = content
            for b_idx in final_block_list:
                chunk = rem[:64]
                self.buffer.write_page(b_idx, chunk, owner=filename)
                rem = rem[64:]

            fcb.size = len(content)
            fcb.modify_time = datetime.datetime.now()

            self.buffer.flush_all()

            if needed_blocks > 0 and fcb.start_block == -1:
                fcb.start_block = final_block_list[0]   # 第一次写内容时补上首块
            return self.directory.update_entry(parent_fcb, fcb)

    def read_file_block(self, path: str, block_offset: int) -> bytes:
        _, fcb = self.directory.resolve_path(path)
        if not fcb or fcb.is_directory: return None
        blocks = self.fat.get_file_blocks(fcb.start_block)
        if block_offset >= len(blocks): return None
        return self.buffer.read_page(blocks[block_offset], owner=fcb.name)

    def write_file_block(self, path: str, block_offset: int, data: bytes) -> bool:
        with self._lock:
            _, fcb = self.directory.resolve_path(path)
            if not fcb: return False
            blocks = self.fat.get_file_blocks(fcb.start_block)
            if block_offset >= len(blocks): return False
            self.buffer.write_page(blocks[block_offset], data, owner=fcb.name)
            return True

    def delete_file(self, path: str) -> bool:
        if path in self.opened_files: return False
        
        _, fcb = self.directory.resolve_path(path)
        if not fcb: return False
        
        if self.directory.remove_entry(path):
            for b in self.fat.get_file_blocks(fcb.start_block):
                self.buffer.invalidate(b)
                self.fat.free_block(b)
            return True
        return False

    def list_files(self, path='/'): 
        try:
            return self.directory.list_directory(path)
        except:
            return []

    def lock_file(self, n): self.opened_files.add(n)
    def unlock_file(self, n): self.opened_files.discard(n)
    
    def get_file_info(self, path: str) -> dict:
        _, fcb = self.directory.resolve_path(path)
        if not fcb: return None
        blocks = self.fat.get_file_blocks(fcb.start_block)
        return {
            'name': fcb.name, 'size': fcb.size, 'blocks': len(blocks),
            'block_list': blocks,
            'create_time': fcb.create_time.strftime('%Y-%m-%d %H:%M:%S'),
            'modify_time': fcb.modify_time.strftime('%Y-%m-%d %H:%M:%S'),
            'is_dir': fcb.is_directory
        }

    def get_system_info(self) -> dict:
        free_blocks = self.fat.get_free_blocks()
        managed = min(self.fat.total_entries, 1024)
        return {
            'total_blocks': 1024,
            'managed_blocks': managed,
            'used_blocks': managed - len(free_blocks) - SystemConfig.DATA_START,
            'free_blocks': len(free_blocks),
            'files_count': len(self.directory.list_directory('/')),
            'buffer_status': self.buffer.get_status()
        }

    def shutdown(self):
        self.buffer.flush_all()
        self.disk.close()
    

    def submit(self, func, *args, **kwargs):
        """
        核心提交接口：接收一个函数和它的参数
        例如：fs.submit(fs.read_file, "/test.txt")
        """
        task = CommandTask(func, *args, **kwargs)
        self.scheduler.task_queue.put(task)
        
        # 等待任务完成并返回结果 (这使得同步调用原函数的地方不需要大幅改动)
        task.done_event.wait()
        
        if task.error:
            raise Exception(task.error)
        return task.result