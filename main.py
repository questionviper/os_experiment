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

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=BOTH, expand=True, padx=5, pady=5)

        system_frame = ttk.Frame(notebook)
        notebook.add(system_frame, text="系统概览")
        self.create_system_tab(system_frame)

        file_frame = ttk.Frame(notebook)
        notebook.add(file_frame, text="目录结构")
        self.create_file_tab(file_frame)

        disk_frame = ttk.Frame(notebook)
        notebook.add(disk_frame, text="磁盘可视化")
        self.create_disk_tab(disk_frame)

        self.filesystem = FileSystem('simulated_disk.img', dir_mode='single')
        self.refresh_all_views()

    def create_system_tab(self, parent):
        title_font = Font(family='Arial', size=14, weight='bold')
        Label(parent, text="系统信息", font=title_font,
              bg='#34495e', fg='white').pack(pady=8)

        info_frame = LabelFrame(parent, text="详情", bg='#34495e', fg='white')
        info_frame.pack(fill=BOTH, expand=True, padx=15, pady=8)

        self.info_text = scrolledtext.ScrolledText(
            info_frame, bg='#2c3e50', fg='white',
            font=('Courier', 10), wrap=WORD
        )
        self.info_text.pack(fill=BOTH, expand=True, padx=8, pady=8)
        self.info_text.config(state=DISABLED)

        Button(parent, text="🔄 刷新", command=self.refresh_all_views,
               bg='#3498db', fg='white').pack(pady=10)

    def create_file_tab(self, parent):
        mode_frame = Frame(parent, bg='#34495e')
        mode_frame.pack(pady=5)
        Label(mode_frame, text="目录模式:", bg='#34495e', fg='white').pack(side=LEFT)
        self.dir_mode_var = StringVar(value='single')
        Radiobutton(mode_frame, text="单级", variable=self.dir_mode_var, value='single',
                   bg='#34495e', fg='white', selectcolor='#2c3e50', state='disabled').pack(side=LEFT, padx=2)
        Radiobutton(mode_frame, text="多级", variable=self.dir_mode_var, value='multi',
                   bg='#34495e', fg='white', selectcolor='#2c3e50', state='disabled').pack(side=LEFT, padx=2)

        tree_frame = LabelFrame(parent, text="目录结构", bg='#34495e', fg='white')
        tree_frame.pack(fill=BOTH, expand=True, padx=15, pady=8)

        columns = ('size', 'start_block', 'create_time')
        self.file_tree = ttk.Treeview(tree_frame, columns=columns, show='tree headings')
        self.file_tree.heading('#0', text='名称')
        self.file_tree.heading('size', text='大小(B)')
        self.file_tree.heading('start_block', text='起始块')
        self.file_tree.heading('create_time', text='创建时间')
        self.file_tree.column('#0', width=280, anchor=W)
        self.file_tree.column('size', width=70, anchor=E)
        self.file_tree.column('start_block', width=80, anchor=CENTER)
        self.file_tree.column('create_time', width=140, anchor=W)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.file_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.file_tree.xview)
        self.file_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.file_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.file_tree.tag_configure('dir', background='#34495e', foreground='lightgray')
        self.file_tree.tag_configure('file', background='', foreground='white')

    def create_disk_tab(self, parent):
        legend_frame = Frame(parent, bg='#34495e')
        legend_frame.pack(pady=3)
        Label(legend_frame, text="图例: ", bg='#34495e', fg='white').pack(side=LEFT)
        for text, color in [
            ("FAT", '#3498db'),
            ("目录", '#2ecc71'),
            ("已用", '#e74c3c'),
            ("空闲", '#95a5a6'),
            ("未管理", '#f39c12')
        ]:
            Label(legend_frame, text="  ", bg=color, width=2).pack(side=LEFT)
            Label(legend_frame, text=text, bg='#34495e', fg='white', padx=1).pack(side=LEFT)

        block_frame = Frame(parent, bg='#34495e')
        block_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        self.block_canvas = Canvas(block_frame, bg='#2c3e50')
        self.block_canvas.pack(fill=BOTH, expand=True)
        self.block_canvas.bind('<Configure>', self.on_canvas_resize)

    def on_canvas_resize(self, event=None):
        self.update_disk_visualization()

    def refresh_all_views(self):
        self.update_system_info()
        self.update_file_tree()
        self.update_disk_visualization()

    def update_system_info(self):
        info = self.filesystem.get_system_info()
        info_text = f"""
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
        self.dir_mode_var.set(self.filesystem.directory.dir_mode)

    def update_file_tree(self):
        self.file_tree.delete(*self.file_tree.get_children())
        fcbs = self.filesystem.directory.list_files()
        dir_mode = self.filesystem.directory.dir_mode

        if dir_mode == 'single':
            for fcb in fcbs:
                ct = fcb.create_time.strftime('%Y-%m-%d %H:%M:%S')
                self.file_tree.insert('', 'end', text=f"📄 {fcb.name}",
                                      values=(fcb.size, fcb.start_block, ct),
                                      tags=('file',))
        else:
            tree = defaultdict(list)
            for fcb in fcbs:
                parts = [p for p in fcb.name.strip('/').split('/') if p]
                if not parts:
                    continue
                path = ''
                for i, part in enumerate(parts[:-1]):
                    next_path = (path + '/' + part).strip('/')
                    tree[path].append(('dir', part, next_path))
                    path = next_path
                tree[path].append(('file', parts[-1], fcb))

            def insert_children(parent_path, parent_id):
                children = tree.get(parent_path, [])
                for item_type, name, data in sorted(children, key=lambda x: (x[0] != 'dir', x[1])):
                    if item_type == 'dir':
                        node_id = self.file_tree.insert(
                            parent_id, 'end', text=f"📁 {name}",
                            values=('', '', ''), tags=('dir',)
                        )
                        insert_children(data, node_id)
                    else:
                        fcb = data
                        ct = fcb.create_time.strftime('%Y-%m-%d %H:%M:%S')
                        self.file_tree.insert(
                            parent_id, 'end', text=f"📄 {name}",
                            values=(fcb.size, fcb.start_block, ct),
                            tags=('file',)
                        )

            insert_children('', '')

    def update_disk_visualization(self):
        canvas = self.block_canvas
        canvas.delete('all')
        cw = max(640, canvas.winfo_width())
        ch = max(320, canvas.winfo_height())
        total = 1024
        blocks_per_row, rows = 64, 16
        bw, bh = cw // blocks_per_row, ch // rows

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