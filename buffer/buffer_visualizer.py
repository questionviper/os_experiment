"""
缓冲区可视化组件
提供可复用的UI组件用于在Tkinter中显示缓冲状态
"""

from tkinter import *
from tkinter import ttk

class BufferVisualizer:
    """
    缓冲区可视化组件
    
    可以嵌入到任何Tkinter窗口中，实时显示缓冲池状态
    """
    
    def __init__(self, parent_frame, buffer_manager, page_count: int = 8):
        """
        初始化可视化组件
        
        Args:
            parent_frame: 父容器
            buffer_manager: BufferManager实例
            page_count: 要显示的页面数量
        """
        self.parent = parent_frame
        self.buffer = buffer_manager
        self.page_count = page_count
        self.page_widgets = []
        
        self._create_widgets()
    
    def _create_widgets(self):
        """创建UI组件"""
        # 统计信息标签
        self.stats_label = Label(
            self.parent,
            text="",
            font=('Courier', 10),
            justify=LEFT,
            bg='#2c3e50',
            fg='#2ecc71'
        )
        self.stats_label.pack(fill=X, padx=10, pady=10)
        
        # 页面容器
        pages_frame = Frame(self.parent, bg='#34495e')
        pages_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        # 创建页面卡片
        for i in range(self.page_count):
            card_frame = Frame(
                pages_frame,
                bg='#95a5a6',
                width=110,
                height=140,
                relief=RAISED,
                borderwidth=2
            )
            card_frame.pack_propagate(False)
            card_frame.grid(row=0, column=i, padx=5, pady=5)
            
            # 标题
            title_label = Label(
                card_frame,
                text=f"Slot {i}",
                bg='#7f8c8d',
                fg='white',
                font=('Arial', 9, 'bold')
            )
            title_label.pack(fill=X)
            
            # 信息
            info_label = Label(
                card_frame,
                text="Empty",
                bg='#95a5a6',
                fg='black',
                font=('Courier', 8),
                justify=LEFT,
                wraplength=100
            )
            info_label.pack(fill=BOTH, expand=True, padx=3, pady=3)
            
            self.page_widgets.append((card_frame, title_label, info_label))
    
    def update(self):
        """更新显示"""
        status = self.buffer.get_status()
        stats = status['statistics']
        pages = status['pages']
        
        # 更新统计信息
        stats_text = f"""使用: {status['used']}/{status['capacity']} | 命中率: {stats['hit_ratio']} | 淘汰: {stats['evict']} 次"""
        self.stats_label.config(text=stats_text)
        
        # 更新页面卡片
        for i, (card, title, info) in enumerate(self.page_widgets):
            if i < len(pages):
                page = pages[i]
                
                # 颜色：脏页=红色，干净页=绿色
                color = '#e74c3c' if page['is_dirty'] else '#2ecc71'
                
                card.config(bg=color, highlightbackground=color, highlightthickness=3)
                title.config(bg=color, fg='white', text=f"Block {page['block_id']}")
                
                info_text = f"访问: {page['last_access']}\n"
                info_text += f"{'🔴 脏页' if page['is_dirty'] else '🟢 干净'}\n"
                info_text += f"数据: {page['data_preview'][:20]}..."
                
                info.config(text=info_text, bg=color, fg='white')
            else:
                # 空槽位
                card.config(bg='#95a5a6', highlightthickness=0)
                title.config(bg='#7f8c8d', fg='white', text=f"Slot {i}")
                info.config(text="Empty", bg='#95a5a6', fg='black')
