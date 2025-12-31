"""
缓冲池可视化 - 实现任务书第5部分
可视化显示内存缓冲状态并动态刷新
"""

from tkinter import *

class BufferVisualizer:
    """缓冲池可视化器"""
    
    def __init__(self, parent, buffer_manager, page_count=8):
        self.parent = parent
        self.buffer = buffer_manager
        self.page_count = page_count
        self.cards = []
        self.create_ui()
    
    def create_ui(self):
        """创建UI"""
        main_frame = Frame(self.parent, bg='#1e1e2e')
        main_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        cards_frame = Frame(main_frame, bg='#1e1e2e')
        cards_frame.pack(fill=BOTH, expand=True)
        
        for i in range(self.page_count):
            row = i // 4
            col = i % 4
            card = self.create_page_card(cards_frame, i)
            card.grid(row=row, column=col, padx=8, pady=8, sticky='nsew')
            self.cards.append(card)
        
        for i in range(4):
            cards_frame.columnconfigure(i, weight=1)
        for i in range(2):
            cards_frame.rowconfigure(i, weight=1)
        
        stats_frame = Frame(main_frame, bg='#313244', relief=RIDGE, borderwidth=1)
        stats_frame.pack(fill=X, pady=(10, 0))
        
        self.stats_label = Label(stats_frame, text="📊 统计信息准备中...",
                                font=('Consolas', 11),
                                bg='#313244', fg='#cdd6f4', pady=12)
        self.stats_label.pack(fill=X)
    
    def create_page_card(self, parent, index):
        """创建缓冲页卡片"""
        card = Frame(parent, bg='#313244', relief=FLAT, borderwidth=0)
        
        title = Label(card, text=f"PAGE #{index}",
                     font=('Segoe UI', 10, 'bold'),
                     bg='#45475a', fg='#89b4fa')
        title.pack(fill=X)
        
        content = Frame(card, bg='#313244', padx=10, pady=10)
        content.pack(fill=BOTH, expand=True)
        
        status = Label(content, text="IDLE",
                      font=('Microsoft YaHei', 10, 'bold'),
                      bg='#313244', fg='#6b7280')
        status.pack(pady=2)
        
        block_label = Label(content, text="Block: --",
                           font=('Consolas', 9),
                           bg='#313244', fg='#a6adc8')
        block_label.pack()
        
        owner_label = Label(content, text="Owner: None",
                           font=('Microsoft YaHei', 8),
                           bg='#313244', fg='#9399b2')
        owner_label.pack()
        
        card.main_content = content
        card.status_label = status
        card.block_label = block_label
        card.owner_label = owner_label
        card.title_label = title
        
        return card
    
    def update(self):
        """动态刷新显示"""
        try:
            status = self.buffer.get_status()
            pages_data = status.get('pages', [])
            
            for i in range(min(len(self.cards), len(pages_data))):
                card = self.cards[i]
                data = pages_data[i]
                
                block_id = data.get('block_id', -1)
                is_dirty = data.get('is_dirty', False)
                owner = data.get('owner', "None")
                
                if block_id == -1:
                    bg_color = '#313244'
                    card.config(bg=bg_color)
                    card.main_content.config(bg=bg_color)
                    card.title_label.config(bg='#45475a', fg='#89b4fa')
                    card.status_label.config(text="IDLE", fg='#585b70', bg=bg_color)
                    card.block_label.config(text="Block: --", fg='#585b70', bg=bg_color)
                    card.owner_label.config(text="Owner: None", fg='#585b70', bg=bg_color)
                else:
                    active_bg = '#f38ba8' if is_dirty else '#a6e3a1'
                    text_color = '#1e1e2e'
                    
                    card.config(bg=active_bg)
                    card.main_content.config(bg=active_bg)
                    card.title_label.config(bg='#11111b', fg='#f5c2e7')
                    
                    status_text = "DIRTY 🔴" if is_dirty else "CLEAN 🟢"
                    card.status_label.config(text=status_text, fg=text_color, bg=active_bg)
                    card.block_label.config(text=f"Block: #{block_id}", fg=text_color, bg=active_bg)
                    
                    display_owner = owner if owner else "SYSTEM"
                    card.owner_label.config(text=f"Owner: {display_owner}", fg='#45475a', bg=active_bg)
            
            s = status.get('statistics', {})
            stats_str = (f"🎯 命中: {s.get('hit',0)}  |  "
                        f"❓ 缺页: {s.get('miss',0)}  |  "
                        f"♻️ 淘汰: {s.get('evict',0)}  |  "
                        f"💾 回写: {s.get('writeback',0)}  |  "
                        f"📈 命中率: {s.get('hit_ratio','0%')}")
            self.stats_label.config(text=stats_str)
            
        except Exception as e:
            print(f"[BufferVisualizer] Update Error: {e}")
