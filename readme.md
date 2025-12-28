
# FAT 文件系统模拟器 – 全类成员与函数速查表


---

## 1. 跨进程通信

### `SharedMemoryInterface`
| 成员 | 作用 |
|------|------|
| `name: str` | 共享内存段名称 |
| `size: int` | 段长度（默认 64 KiB） |
| `shm: SharedMemory` | 底层共享内存对象 |
| `_connected: bool` | 连接状态 |

| 函数 | 作用 |
|------|------|
| `create()` | 创建或打开共享内存段 |
| `write(data: bytes)` | 写入数据并补 `\0` |
| `read() -> bytes` | 读取有效数据（遇 `\0` 截断） |
| `close()` | 关闭映射（不删文件） |
| `unlink()` | 关闭并删除系统对象 |
| `__enter__ / __exit__` | 上下文管理协议 |

---

## 2. 磁盘块设备

### `DiskManager`
| 成员 | 作用 |
|------|------|
| `disk_path: str` | 模拟磁盘文件路径 |
| `block_size / block_count / total_size` | 块大小、块数、总字节 |
| `fd` | 文件句柄 |
| `mmap` | 内存映射对象 |

| 函数 | 作用 |
|------|------|
| `_initialize_disk()` | 磁盘文件不存在则创建并预分配空格 |
| `_map_disk()` | 打开文件并 mmap |
| `read_block(idx: int) -> bytes` | 读取指定块 |
| `write_block(idx: int, data: bytes)` | 写入指定块（不足补 `\0`，超长截断） |
| `close()` | flush、munmap、close(fd) |

---

## 3. FAT 表管理

### `FATManager`
| 成员 | 作用 |
|------|------|
| `disk: DiskManager` | 关联磁盘 |
| `fat_start_block / fat_blocks` | FAT 起始块号与占用块数 |
| `fat_entries_per_block / total_fat_entries` | 每块项数、总项数 |

| 函数 | 作用 |
|------|------|
| `_initialize_fat()` | 初始化 FAT 表：保留块、空闲链 |
| `_read_fat_entry(idx: int) -> int` | 读单条 FAT 项（4 B 小端） |
| `_write_fat_entry(idx: int, val: int)` | 写单条 FAT 项 |
| `allocate_block() -> int` | 分配空闲块（返回块号，-1=满） |
| `free_block(idx: int)` | 回收块 |
| `get_free_blocks_count() -> int` | 统计空闲块数量 |
| `get_free_blocks() -> List[int]` | 返回空闲块号列表（供 UI） |
| `get_file_blocks(start: int) -> List[int]` | 顺着 FAT 链收集所有块号，带循环保护 |

---

## 4. 文件控制块（目录项）

### `FCB`
| 成员 | 作用 |
|------|------|
| `name: str` | 文件名 |
| `size: int` | 文件字节数 |
| `start_block: int` | 起始块号 |
| `create_time: datetime` | 创建时间 |
| `permissions: str` | 权限串（如 `rw-r--r--`） |

| 函数 | 作用 |
|------|------|
| `to_bytes() -> bytes` | 64 B 定长：JSON → UTF-8 → 左补 `\0` |
| `from_bytes(data_input: bytes) -> Optional[FCB]` | 反向解析，容错截断、补括号、忽略乱码 |

---

## 5. 目录区管理

### `DirectoryManager`
| 成员 | 作用 |
|------|------|
| `disk: DiskManager` | 关联磁盘 |
| `dir_start_block / dir_blocks` | 目录起始块号与占用块数 |
| `dir_mode: str` | `'single'` 或 `'multi'` |
| `max_files: int` | 最大文件数 = 目录块数 × (块大小/64) |

| 函数 | 作用 |
|------|------|
| `_initialize_directory()` | 目录区全部写 0 |
| `_normalize_name(fn: str) -> str` | 单级模式只保留 basename |
| `add_file(fcb: FCB) -> bool` | 找空槽写入 FCB |
| `find_file(fn: str) -> Optional[FCB]` | 按名查找 |
| `list_files() -> List[FCB]` | 线性扫描返回全部文件 |
| `list_files_as_tree() -> dict` | 多级模式生成嵌套字典供 UI 树形展示 |
| `remove_file(fn: str) -> bool` | 删除目录项 |

---

## 6. 高层文件系统

### `FileSystem`
| 成员 | 作用 |
|------|------|
| `BLOCK_SIZE / TOTAL_BLOCKS / DIR_BLOCKS` | 类常量 64 B、1024 块、16 目录块 |
| `disk / fat / directory` | 聚合三大底层管理器 |
| `data_start_block: int` | 数据区起始块号 |
| `file_in_use: Set[str]` | 正在被使用的文件名（防删） |

| 函数 | 作用 |
|------|------|
| `_mark_system_blocks_as_used()` | 把保留/FAT/目录块在 FAT 里标特殊值 |
| `create_file(name: str, content: bytes = b'') -> bool` | 创建文件（含分配+写数据） |
| `_write_file_content(fcb: FCB, content: bytes)` | 按块拆分内容并链 FAT |
| `read_file(name: str) -> Optional[bytes]` | 读整个文件 |
| `read_file_block(name: str, idx: int) -> bytes` | 读文件内第 idx 块 |
| `write_file_block(name: str, idx: int, data: bytes)` | 写文件内第 idx 块 |
| `get_file_blocks(name: str) -> List[int]` | 返回文件所有块号 |
| `get_file_block_count(name: str) -> int` | 返回文件占块数 |
| `delete_file(name: str) -> bool` | 回收 FAT 链并删目录项 |
| `get_free_blocks() -> List[int]` | 透传 FATManager |
| `get_system_info() -> Dict` | 返回总块、已用、空闲、文件数等统计信息 |

---


## 7. 极简调试 UI（系统概览 + 磁盘可视化）

### `FATFileSystemSimulator`
| 成员 | 作用 |
|------|------|
| `root: Tk` | 主窗口句柄 |
| `filesystem: FileSystem` | 被监视的文件系统实例 |
| `info_text: ScrolledText` | “系统概览”页只读文本框 |
| `block_canvas: Canvas` | “磁盘可视化”页画布 |

| 函数 | 作用 |
|------|------|
| `__init__(root)` | 构造 1000×700 暗色主题窗口，初始化 Notebook 两页 |
| `create_system_tab(parent)` | 生成“系统概览”页：标题 + 只读详情文本框 |
| `create_disk_tab(parent)` | 生成“磁盘可视化”页：颜色图例 + 自适应画布 |
| `on_canvas_resize(event)` | 画布尺寸变化时重绘磁盘块 |
| `refresh_all_views()` | 一次性刷新系统信息与磁盘图 |
| `update_system_info()` | 调用 `get_system_info()` 并格式化输出到文本框 |
| `update_disk_visualization()` | 1024 块 64×16 方阵，按 FAT/目录/已用/空闲/未管理五色绘制 |


---

## 8. 线程与并发

- 所有磁盘 IO 操作（创建、删除、演示）均通过 `threading.Thread` 在后台执行，避免阻塞 GUI。  
- 子线程通过 `message_queue` 把日志传回主线程，主线程使用 `after(100, self.process_messages)` 周期性消费。

