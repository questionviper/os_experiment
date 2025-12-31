"""
系统配置文件 - 符合任务书要求
M = 64B (块大小)
N = 1024 (块数量)
K = 8 (缓冲页数量)
"""

class SystemConfig:
    """系统配置类"""
    
    # ========== 任务书要求参数 ==========
    BLOCK_SIZE = 64              # M: 每个盘块大小(字节)
    TOTAL_BLOCKS = 1024          # N: 盘块数量
    BUFFER_CAPACITY = 8          # K: 缓冲页数量
    
    # 磁盘标识
    DISK_MAGIC = b'FATFS'
    VERSION = 1
    
    # ========== 磁盘分区布局 ==========
    # 前部：元数据区
    SUPER_BLOCK = 1              # 超级块(块#0)
    FAT_BLOCKS = 64              # FAT表占用块数
    DIR_BLOCKS = 32              # 根目录区占用块数 (仅用于根目录)
    
    # 计算起始位置
    FAT_START = SUPER_BLOCK      # FAT表起始块号
    DIR_START = FAT_START + FAT_BLOCKS    # 目录区起始块号
    DATA_START = DIR_START + DIR_BLOCKS   # 数据区起始块号
    
    # ========== 文件系统限制 ==========
    MAX_FILENAME_LENGTH = 32
    # 最大文件大小取决于数据区剩余空间
    MAX_FILE_SIZE = (TOTAL_BLOCKS - DATA_START) * BLOCK_SIZE
    
    # ========== FAT表特殊值 ==========
    FAT_FREE = 0xFFFFFFFF        # 空闲块标记
    FAT_EOF = 0xFFFFFFFE         # 文件结束标记
    FAT_BAD = 0xFFFFFFFD         # 坏块标记
    FAT_RESERVED = 0xFFFFFF00    # 保留块基值
    
    # ========== UI配置 ==========
    AUTO_REFRESH_INTERVAL = 2000  # 自动刷新间隔(毫秒)
    IO_DELAY = 0.1               # I/O延时(秒) - 用于可视化观察
    
    @classmethod
    def validate(cls):
        """验证配置合理性"""
        assert cls.BLOCK_SIZE > 0, "块大小必须>0"
        assert cls.TOTAL_BLOCKS > cls.DATA_START, "数据区必须有空间"
        assert cls.DATA_START == cls.SUPER_BLOCK + cls.FAT_BLOCKS + cls.DIR_BLOCKS
        return True

SystemConfig.validate()
