"""
缓冲管理器独立演示程序
展示缓冲池的工作原理和LRU置换算法
"""

import sys
import os

# 添加父目录到路径以便导入disk模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tkinter import *
from tkinter import messagebox
from disk import FileSystem
from buffer import BufferManager
from buffer.buffer_visualizer import BufferVisualizer
import threading
import time
import random

class BufferDemo:
    """缓冲管理器演示主窗口"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("内存缓冲页演示程序 - LRU置换算法")
        self.root.geometry("1050x700")
        self.root.configure(bg='#1e1e1e')
        
        # 初始化文件系统
        self.fs = FileSystem('simulated_disk.img')
        self.buffer = self.fs.buffer
        
        self.create_ui()
        self.auto_refresh()
    
    def create_ui(self):
        """创建用户界面"""
        # 标题
        title = Label(
            self.root,
            text="🧠 内存缓冲池实时监控",
            bg='#1e1e1e',
            fg='white',
            font=('Arial', 18, 'bold')
        )
        title.pack(pady=15)
        
        # 说明文字
        desc = Label(
            self.root,
            text="展示内存缓冲池的工作原理 | 绿色=干净页 | 红色=脏页 | LRU置换算法",
            bg='#1e1e1e',
            fg='#95a5a6',
            font=('Arial', 10)
        )
        desc.pack()
        
        # 可视化容器
        viz_frame = Frame(self.root, bg='#2c3e50', relief=RIDGE, borderwidth=3)
        viz_frame.pack(fill=BOTH, expand=True, padx=30, pady=20)
        
        # 使用可视化组件
        self.visualizer = BufferVisualizer(viz_frame, self.buffer, page_count=8)
        
        # 控制面板
        self.create_control_panel()
        
        # 日志面板
        self.create_log_panel()
    
    def create_control_panel(self):
        """创建控制按钮面板"""
        control_frame = Frame(self.root, bg='#2d2d30', relief=RIDGE, borderwidth=2)
        control_frame.pack(fill=X, padx=30, pady=10)
        
        Label(
            control_frame,
            text="测试操作:",
            bg='#2d2d30',
            fg='white',
            font=('Arial', 12, 'bold')
        ).pack(side=LEFT, padx=15)
        
        buttons = [
            ("写入随机块", self.write_random, '#0e639c'),
            ("读取随机块", self.read_random, '#106ebe'),
            ("批量测试(LRU)", self.batch_test, '#f1fa8c'),
            ("刷新脏页", self.flush_all, '#50fa7b'),
            ("重置统计", self.reset_stats, '#ff5555'),
        ]
        
        for text, command, color in buttons:
            Button(
                control_frame,
                text=text,
                command=command,
                bg=color,
                fg='white' if color == '#ff5555' else 'black',
                font=('Arial', 10),
                padx=10
            ).pack(side=LEFT, padx=5, pady=10)
    
    def create_log_panel(self):
        """创建日志面板"""
        log_frame = Frame(self.root, bg='#2d2d30')
        log_frame.pack(fill=X, padx=30, pady=(0, 15))
        
        Label(
            log_frame,
            text="操作日志:",
            bg='#2d2d30',
            fg='white',
            font=('Arial', 10, 'bold')
        ).pack(anchor=W, padx=10, pady=5)
        
        self.log_text = Text(
            log_frame,
            height=6,
            bg='#0c0c0c',
            fg='#00ff00',
            font=('Consolas', 9),
            wrap=WORD
        )
        self.log_text.pack(fill=BOTH, padx=10, pady=(0, 10))
    
    def log(self, message: str):
        """添加日志"""
        timestamp = time.strftime('%H:%M:%S')
        self.log_text.insert(END, f"[{timestamp}] {message}\n")
        self.log_text.see(END)
    
    def write_random(self):
        """写入随机块"""
        block_id = random.randint(50, 100)
        data = f"Written at {time.strftime('%H:%M:%S')}".encode()
        
        self.buffer.write_page(block_id, data)
        self.log(f"写入块 {block_id}（标记为脏页）")
        self.visualizer.update()
    
    def read_random(self):
        """读取随机块"""
        block_id = random.randint(50, 100)
        
        before_hits = self.buffer.stats.hit_count
        self.buffer.read_page(block_id)
        after_hits = self.buffer.stats.hit_count
        
        is_hit = after_hits > before_hits
        self.log(f"读取块 {block_id} - {'✅ 缓存命中' if is_hit else '❌ 缺页加载'}")
        self.visualizer.update()
    
    def batch_test(self):
        """批量测试（触发LRU置换）"""
        def task():
            self.log("开始批量测试：写入15个块（缓冲池只有8个位置）")
            for i in range(15):
                block_id = 50 + i
                data = f"Batch test {i}".encode()
                self.buffer.write_page(block_id, data)
                
                self.root.after(0, lambda: self.log(f"写入块 {50 + i}"))
                time.sleep(0.25)
                self.root.after(0, self.visualizer.update)
            
            self.root.after(0, lambda: self.log("批量测试完成！观察LRU置换过程"))
        
        threading.Thread(target=task, daemon=True).start()
    
    def flush_all(self):
        """刷新所有脏页"""
        dirty_count = sum(1 for page in self.buffer.buffer_pool.values() if page.is_dirty)
        
        if dirty_count == 0:
            messagebox.showinfo("提示", "当前没有脏页需要刷新")
            return
        
        self.buffer.flush_all()
        self.log(f"刷新了 {dirty_count} 个脏页到磁盘")
        messagebox.showinfo("完成", f"所有脏页已写回磁盘（共{dirty_count}页）")
        self.visualizer.update()
    
    def reset_stats(self):
        """重置统计"""
        self.buffer.stats.reset()
        self.log("统计信息已重置")
        messagebox.showinfo("完成", "统计信息已重置")
        self.visualizer.update()
    
    def auto_refresh(self):
        """自动刷新显示"""
        self.visualizer.update()
        self.root.after(1000, self.auto_refresh)
    
    def on_closing(self):
        """窗口关闭处理"""
        self.fs.shutdown()
        self.root.destroy()

if __name__ == "__main__":
    root = Tk()
    app = BufferDemo(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
