"""
内存缓冲页模块
作者: [你的名字]
版本: 1.0

模块功能:
- 实现M×K大小的内存缓冲池
- 使用LRU页面置换算法
- 提供脏页回写机制
- 支持性能统计和可视化

主要类:
- BufferManager: 缓冲管理器
- BufferPage: 缓冲页数据结构
- BufferStatistics: 性能统计
"""

from .buffer_manager import BufferManager, BufferPage, BufferStatistics

__all__ = ["BufferManager", "BufferPage", "BufferStatistics"]
__version__ = "1.0"
__author__ = "[你的名字]"
