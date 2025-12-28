from disk import FileSystem
from tkinter import *
from tkinter import ttk, scrolledtext
from tkinter.font import Font
# ==============================
# 🖼️ 极简 UI（仅调试：系统概览 + 磁盘可视化）
# ==============================
class FATFileSystemSimulator:
    def __init__(self, root):
        self.root = root
        self.root.title("FAT文件系统模拟器 - Debug View")
        self.root.geometry("1000x700")
        self.root.configure(bg='#2c3e50')

        # 创建 notebook
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=BOTH, expand=True, padx=5, pady=5)

        # ✅ 系统概览页（只读）
        system_frame = ttk.Frame(notebook)
        notebook.add(system_frame, text="系统概览")
        self.create_system_tab(system_frame)

        # ✅ 磁盘可视化页（只读）
        disk_frame = ttk.Frame(notebook)
        notebook.add(disk_frame, text="磁盘可视化")
        self.create_disk_tab(disk_frame)

        # 初始化文件系统（默认 single）
        self.filesystem = FileSystem('simulated_disk.img', dir_mode='single')
        self.refresh_all_views()

    def create_system_tab(self, parent):
        title_font = Font(family='Arial', size=14, weight='bold')
        Label(parent, text="系统信息", font=title_font, bg='#34495e', fg='white').pack(pady=8)

        info_frame = LabelFrame(parent, text="详情", bg='#34495e', fg='white', font=('Arial', 10, 'bold'))
        info_frame.pack(fill=BOTH, expand=True, padx=15, pady=8)

        self.info_text = scrolledtext.ScrolledText(info_frame, height=20,
                                                   bg='#2c3e50', fg='white',
                                                   font=('Courier', 10), wrap=WORD)
        self.info_text.pack(fill=BOTH, expand=True, padx=8, pady=8)
        self.info_text.config(state=DISABLED)

    def create_disk_tab(self, parent):
        legend_frame = Frame(parent, bg='#34495e')
        legend_frame.pack(pady=5)
        Label(legend_frame, text="图例:  ", bg='#34495e', fg='white').pack(side=LEFT)
        for text, color in [
            ("FAT", '#3498db'),
            ("目录", '#2ecc71'),
            ("已用", '#e74c3c'),
            ("空闲", '#95a5a6'),
            ("未管理", '#f39c12')
        ]:
            Label(legend_frame, text="  ", bg=color, width=2).pack(side=LEFT, padx=1)
            Label(legend_frame, text=text, bg='#34495e', fg='white', padx=3).pack(side=LEFT)

        block_frame = Frame(parent, bg='#34495e')
        block_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        self.block_canvas = Canvas(block_frame, bg='#2c3e50')
        self.block_canvas.pack(fill=BOTH, expand=True)
        self.block_canvas.bind('<Configure>', self.on_canvas_resize)

    def on_canvas_resize(self, event=None):
        self.update_disk_visualization()

    def refresh_all_views(self):
        self.update_system_info()
        self.update_disk_visualization()

    def update_system_info(self):
        info = self.filesystem.get_system_info()
        info_text =f"""
磁盘总块数: {info['total_blocks']} × {info['block_size']}B = {info['total_blocks'] * info['block_size']}B
已管理块数: {info['managed_blocks']}（FAT可追踪）
未管理块数: {info['unmanaged_blocks']}

区域分布:
    FAT表: {info['fat_blocks']} 块
    目录: {info['dir_blocks']} 块
    数据区: {info['data_blocks']} 块

使用情况:
    空闲块: {info['free_blocks']}
    已用数据块: {info['used_blocks']}
    文件数量: {info['files_count']}
"""
        self.info_text.config(state=NORMAL)
        self.info_text.delete(1.0, END)
        self.info_text.insert(END, info_text)
        self.info_text.config(state=DISABLED)

    def update_disk_visualization(self):
        canvas = self.block_canvas
        canvas.delete('all')
        cw = max(640, canvas.winfo_width())
        ch = max(320, canvas.winfo_height())
        total = 1024
        blocks_per_row, rows = 64, 16
        bw, bh = cw // blocks_per_row, ch // rows

        # 获取状态
        status = ['free'] * total
        status[0] = status[1] = 'reserved'
        fat_start = self.filesystem.fat.fat_start_block
        fat_end = min(fat_start + self.filesystem.fat.fat_blocks - 1, 1023)
        for i in range(fat_start, fat_end + 1): status[i] = 'fat'
        dir_start = self.filesystem.directory.dir_start_block
        dir_end = min(dir_start + self.filesystem.directory.dir_blocks - 1, 1023)
        for i in range(dir_start, dir_end + 1): status[i] = 'dir'
        data_start = self.filesystem.data_start_block
        max_managed = min(self.filesystem.fat.total_fat_entries, 1024)
        for i in range(data_start, max_managed):
            if self.filesystem.fat._read_fat_entry(i) != 0xFFFFFFFF:
                status[i] = 'used'
        for i in range(max_managed, 1024):
            status[i] = 'unmanaged'

        # 绘制
        color_map = {'reserved': '#8e44ad', 'fat': '#3498db', 'dir': '#2ecc71',
                     'used': '#e74c3c', 'free': '#95a5a6', 'unmanaged': '#f39c12'}
        for idx in range(1024):
            r, c = divmod(idx, 64)
            x1, y1 = c * bw, r * bh
            x2, y2 = x1 + bw, y1 + bh
            color = color_map.get(status[idx], '#95a5a6')
            canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline='#34495e', width=1)


if __name__ == "__main__":
    root = Tk()
    app = FATFileSystemSimulator(root)
    root.mainloop()