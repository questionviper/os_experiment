from tkinter import *
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import threading
import time
from disk import FileSystem
from config import SystemConfig
from process import CommandTask
try:
    from buffer.buffer_visualizer import BufferVisualizer
    BUFFER_AVAILABLE = True
except:
    BUFFER_AVAILABLE = False

class OSCourseDesignGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("操作系统课程设计 - FAT文件系统 (完全增强版)")
        self.root.geometry("1400x900")
        self.bg_color = '#1e1e2e'
        self.root.configure(bg=self.bg_color)
        
        # 初始化文件系统
        self.filesystem = FileSystem('os_course_disk.img')
        
        self.current_path = "/" # 当前路径
        
        self.create_header()
        self.create_tabs()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.auto_refresh()

    def create_header(self):
        header = Frame(self.root, bg='#313244', height=80)
        header.pack(fill=X)
        header.pack_propagate(False)
        
        title_f = Frame(header, bg='#313244')
        title_f.pack(side=LEFT, padx=20)
        Label(title_f, text="🖥️ 操作系统课程设计 - FAT文件系统", 
              font=('Microsoft YaHei', 18, 'bold'), bg='#313244', fg='#89b4fa').pack(anchor=W)
        
        self.stat_labels = {}
        for l, c in [("💾 磁盘使用", "#89b4fa"), ("📁 根目录文件", "#a6e3a1"), ("🧠 命中率", "#f9e2af")]:
            f = Frame(header, bg='#313244')
            f.pack(side=RIGHT, padx=15)
            val = Label(f, text="0", bg='#313244', fg=c, font=('Arial', 14, 'bold'))
            val.pack()
            Label(f, text=l, bg='#313244', fg='#a6adc8').pack()
            self.stat_labels[l] = val

    def create_tabs(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        tab_f = Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(tab_f, text=" 📂 文件管理 ")
        self.create_file_tab(tab_f)
        
        tab_d = Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(tab_d, text=" 💾 磁盘可视化 ")
        self.create_disk_tab(tab_d)
        
        tab_b = Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(tab_b, text=" 🧠 内存缓冲 ")
        self.create_buffer_tab(tab_b)
        
        tab_m = Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(tab_m, text=" 📊 系统监控 ")
        self.create_monitor_tab(tab_m)

    def create_file_tab(self, parent):
        top_bar = Frame(parent, bg='#313244')
        top_bar.pack(fill=X, padx=10, pady=5)
        
        # 路径导航条
        Label(top_bar, text="当前路径:", bg='#313244', fg='#cdd6f4').pack(side=LEFT, padx=5)
        self.path_entry = Entry(top_bar, width=60, bg='#181825', fg='white', relief=FLAT)
        self.path_entry.insert(0, "/")
        self.path_entry.config(state='readonly')
        self.path_entry.pack(side=LEFT, padx=5, pady=5)
        
        Button(top_bar, text="⬆️ 上一级", command=self.go_up, bg='#89b4fa', relief=FLAT).pack(side=LEFT, padx=5)

        toolbar = Frame(parent, bg='#313244', height=40)
        toolbar.pack(fill=X, padx=10, pady=0)
        
        btn_set = [
            ("➕ 文件", self.create_file_async, '#a6e3a1'),
            ("➕ 目录", self.create_dir_async, '#94e2d5'),
            ("📝 编辑", self.edit_file, '#89b4fa'),
            ("🔍 块检查", self.inspect_file_blocks, '#cba6f7'),
            ("👁️ 查看", self.view_file, '#f9e2af'),
            ("🗑️ 删除", self.delete_entry, '#f38ba8'),
            ("🔄 刷新", self.refresh_files, '#b4befe')
        ]
        for t, cmd, c in btn_set:
            Button(toolbar, text=t, command=cmd, bg=c, relief=FLAT, width=10).pack(side=LEFT, padx=5, pady=5)
        
        # 修改：增加 'start' (起始块号) 和 'perms' (权限)
        cols = ('type', 'name', 'size', 'start', 'perms', 'blocks', 'create')
        self.file_tree = ttk.Treeview(parent, columns=cols, show='headings')
        self.file_tree.heading('type', text='类型')
        self.file_tree.heading('name', text='名称')
        self.file_tree.heading('size', text='大小')
        self.file_tree.heading('start', text='起始块')  # 新增
        self.file_tree.heading('perms', text='权限')    # 新增
        self.file_tree.heading('blocks', text='盘块数')
        self.file_tree.heading('create', text='创建时间')
        
        self.file_tree.column('type', width=50, anchor=CENTER)
        self.file_tree.column('name', width=200)
        self.file_tree.column('start', width=80, anchor=CENTER)
        self.file_tree.column('perms', width=100, anchor=CENTER)
        
        self.file_tree.pack(fill=BOTH, expand=True, padx=10)
        self.file_tree.bind("<Double-1>", self.on_double_click)


    
    

    def _join_path(self, name):
        if self.current_path == '/':
            return f"/{name}"
        return f"{self.current_path}/{name}"

    def go_up(self):
        if self.current_path == '/': return
        self.current_path = self.current_path.rsplit('/', 1)[0] or '/'
        if self.current_path == '': self.current_path = '/'
        self.refresh_files()

    def on_double_click(self, event):
        item = self.file_tree.selection()
        if not item: return
        vals = self.file_tree.item(item[0], "values")
        if vals[0] == 'DIR':
            self.current_path = self._join_path(vals[1])
            self.refresh_files()

    def view_file(self):
        sel = self.file_tree.selection()
        if not sel: return
        vals = self.file_tree.item(sel[0])['values']
        if vals[0] == 'DIR': return
        
        fname = vals[1]
        full_path = self._join_path(fname)
        #content = self.filesystem.read_file(full_path)
        content = self.filesystem.submit(self.filesystem.read_file,full_path)
        if content is None:
            messagebox.showerror("错误", "读取文件失败")
            return

        win = Toplevel(self.root)
        win.title(f"查看: {fname}")
        win.geometry("600x450")
        
        txt = scrolledtext.ScrolledText(win, bg='#1e1e2e', fg='#cdd6f4', 
                                       insertbackground='white', font=('Consolas', 11))
        txt.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        display_text = content.decode('utf-8', errors='replace').rstrip('\x00')
        txt.insert(END, display_text)
        txt.config(state=DISABLED)

    def inspect_file_blocks(self):
        sel = self.file_tree.selection()
        if not sel: return
        
        vals = self.file_tree.item(sel[0])['values']
        fname = vals[1]
        is_dir = (vals[0] == 'DIR')
        full_path = self._join_path(fname)
        
        info = self.filesystem.get_file_info(full_path)
        if not info or not info.get('block_list'):
            messagebox.showinfo("提示", "未分配盘块")
            return
        
        win = Toplevel(self.root)
        win.geometry("550x450")
        win.title(f"块级检查 - {full_path}")
        win.configure(bg=self.bg_color)
        
        Label(win, text=f"📂 路径: {full_path} [{'目录' if is_dir else '文件'}]", bg=self.bg_color, fg='#cba6f7', font=('Arial', 11, 'bold')).pack(pady=10)
        
        combo = ttk.Combobox(win, values=[f"逻辑块 {i} (物理#{b})" for i, b in enumerate(info['block_list'])], state="readonly")
        combo.current(0)
        combo.pack(pady=5)
        
        box = Text(win, height=12, bg='#313244', fg='#a6e3a1', font=('Consolas', 11))
        box.pack(padx=20, pady=10, fill=X)
        
        def do_read():
            data = self.filesystem.read_file_block(full_path, combo.current())
            box.delete(1.0, END)
            if data:
                if is_dir:
                    box.insert(END, data.hex())
                else:
                    box.insert(END, data.decode('utf-8', errors='replace'))
        
        def do_write():
            if is_dir:
                messagebox.showwarning("警告", "直接修改目录块极为危险，仅允许读")
                return
            d = box.get(1.0, "end-1c").encode('utf-8')
            if len(d) > 64:
                messagebox.showwarning("警告", "内容超过64字节，将被截断")
            if self.filesystem.write_file_block(full_path, combo.current(), d):
                messagebox.showinfo("成功", "块原地更新成功，缓冲页已变红(脏页)")
        
        f = Frame(win, bg=self.bg_color)
        f.pack(pady=10)
        Button(f, text="📥 读取当前块", command=do_read, bg='#89b4fa', width=12).pack(side=LEFT, padx=30)
        Button(f, text="💾 修改并存回", command=do_write, bg='#f38ba8', width=12).pack(side=RIGHT, padx=30)
        do_read()

    def create_dir_async(self):
        new_name = simpledialog.askstring("新建目录", "输入目录名称:")
        if new_name:
            full_path = self._join_path(new_name)
            # if self.filesystem.create_directory(full_path):
            if self.filesystem.submit(self.filesystem.create_directory,full_path):
                self.refresh_files()
            else:
                messagebox.showerror("错误", "创建失败 (可能重名或磁盘满)")

    def create_file_async(self):
        win = Toplevel(self.root)
        win.title("新建文件")
        win.geometry("400x300")
        win.configure(bg=self.bg_color)

        Label(win, text="文件名:", bg=self.bg_color, fg='#cdd6f4').pack(pady=5)
        e = Entry(win, bg='#313244', fg='white', insertbackground='white')
        e.pack(pady=5, padx=20, fill=X)
        
        Label(win, text="内容:", bg=self.bg_color, fg='#cdd6f4').pack(pady=5)
        t = Text(win, height=8, bg='#313244', fg='white', insertbackground='white')
        t.pack(pady=5, padx=20, fill=BOTH, expand=True)

        def sub():
            fname = e.get().strip()
            if not fname: return
            content = t.get(1.0, "end-1c").encode('utf-8')
            full_path = self._join_path(fname)
            # if self.filesystem.create_file(full_path, content):
            if self.filesystem.submit(self.filesystem.create_file, full_path, content):
                self.refresh_files()
                win.destroy()
            else:
                messagebox.showerror("错误", "创建失败")
        Button(win, text="确认创建", command=sub, bg='#a6e3a1').pack(pady=10)

    def edit_file(self):
        sel = self.file_tree.selection()
        if not sel: return
        vals = self.file_tree.item(sel[0])['values']
        if vals[0] == 'DIR': return
        
        fname = vals[1]
        full_path = self._join_path(fname)
        
        self.filesystem.lock_file(full_path)
        # content = self.filesystem.read_file(full_path)
        content = self.filesystem.submit(self.filesystem.read_file,full_path)
        win = Toplevel(self.root)
        win.title(f"编辑: {fname}")
        win.geometry("650x500")
        
        txt = scrolledtext.ScrolledText(win, bg='#1e1e2e', fg='#cdd6f4', insertbackground='white', font=('Consolas', 11))
        txt.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        display_text = content.decode('utf-8', errors='replace').rstrip('\x00')
        txt.insert(END, display_text)
        
        def save():
            new_data = txt.get(1.0, "end-1c").encode('utf-8')
            # if self.filesystem.write_file(full_path, new_data):
            if self.filesystem.submit(self.filesystem.write_file,full_path, new_data):
                self.filesystem.unlock_file(full_path)
                win.destroy()
                self.refresh_files()
            else:
                messagebox.showerror("错误", "保存失败")

        win.protocol("WM_DELETE_WINDOW", lambda: [self.filesystem.unlock_file(full_path), win.destroy()])
        Button(win, text="💾 保存并回写磁盘", command=save, bg='#a6e3a1', height=2).pack(fill=X, padx=10, pady=5)

    def delete_entry(self):
        sel = self.file_tree.selection()
        if not sel: return
        vals = self.file_tree.item(sel[0])['values']
        fname = vals[1]
        full_path = self._join_path(fname)
        
        # if not self.filesystem.delete_file(full_path):
        if not self.filesystem.submit(self.filesystem.delete_file,full_path):
            messagebox.showerror("错误", "删除失败 (可能非空目录或被占用)")
        self.refresh_files()

    def create_disk_tab(self, parent):
        # 增加图例区域
        legend_frame = Frame(parent, bg='#313244', height=40)
        legend_frame.pack(fill=X, padx=20, pady=(20,0))
        
        legends = [
            ("超级块", "#8b5cf6"),
            ("FAT表", "#3b82f6"),
            ("根目录", "#10b981"),
            ("已占用数据", "#ef4444"),
            ("空闲数据", "#6b7280")
        ]
        
        for name, color in legends:
            f = Frame(legend_frame, bg='#313244')
            f.pack(side=LEFT, padx=15, pady=8)
            Label(f, text="  ", bg=color, width=2).pack(side=LEFT)
            Label(f, text=f" {name}", bg='#313244', fg='white').pack(side=LEFT)

        self.disk_canvas = Canvas(parent, bg='#1e1e2e', highlightthickness=0)
        self.disk_canvas.pack(fill=BOTH, expand=True, padx=20, pady=20)

    def create_buffer_tab(self, parent):
        if BUFFER_AVAILABLE:
            self.buffer_viz = BufferVisualizer(parent, self.filesystem.buffer)

    def create_monitor_tab(self, parent):
        self.monitor_text = scrolledtext.ScrolledText(parent, state=DISABLED, font=('Consolas', 10))
        self.monitor_text.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def refresh_files(self):
        for i in self.file_tree.get_children(): self.file_tree.delete(i)
        
        self.path_entry.config(state=NORMAL)
        self.path_entry.delete(0, END)
        self.path_entry.insert(0, self.current_path)
        self.path_entry.config(state='readonly')
        #list files to submit
        files = self.filesystem.submit(self.filesystem.list_files,self.current_path)
        for f in files:
            ftype = 'DIR' if f.is_directory else 'FILE'
            s_blk = f.start_block if f.start_block != -1 else 'N/A'
            
            self.file_tree.insert('', END, values=(
                ftype, f.name, f.size, 
                s_blk, f.permissions, # 这里插入新字段
                len(self.filesystem.fat.get_file_blocks(f.start_block)) if f.start_block != -1 else 0,
                f.create_time.strftime('%H:%M:%S')
            ))

    def update_disk_viz(self):
        if not hasattr(self, 'disk_canvas'): return
        can = self.disk_canvas
        can.delete('all')
        w = can.winfo_width()
        h = can.winfo_height()
        if w < 10: return
        
        cols, rows = 64, 16
        bw, bh = w/cols, h/rows
        
        for i in range(1024):
            color = '#6b7280' # 空闲
            if i == 0: color = '#8b5cf6' # 超级块
            elif SystemConfig.FAT_START <= i < SystemConfig.DIR_START: color = '#3b82f6' # FAT
            elif SystemConfig.DIR_START <= i < SystemConfig.DATA_START: color = '#10b981' # 根目录區
            elif self.filesystem.fat._read_entry(i) != SystemConfig.FAT_FREE: color = '#ef4444' # 已占
            
            r, c = divmod(i, cols)
            can.create_rectangle(c*bw, r*bh, (c+1)*bw-1, (r+1)*bh-1, fill=color, outline='#24273a')

    def update_monitor(self):
        info = self.filesystem.get_system_info()
        txt = f"磁盘利用: {info['used_blocks']}/{info['managed_blocks']} Blocks\n"
        txt += f"根目录文件: {info['files_count']} (仅根目录)\n"
        txt += f"当前浏览: {self.current_path}"
        if 'buffer_status' in info:
            b = info['buffer_status']['statistics']
            txt += f"\n\n缓冲命中率: {b['hit_ratio']}\n脏页淘汰: {b['evict']} | 磁盘回写: {b['writeback']}"
        
        self.monitor_text.config(state=NORMAL)
        self.monitor_text.delete(1.0, END)
        self.monitor_text.insert(END, txt)
        self.monitor_text.config(state=DISABLED)

    def auto_refresh(self):
        """自动刷新定时器"""
        try:
            info = self.filesystem.get_system_info()
            self.stat_labels["💾 磁盘使用"].config(text=f"{(info['used_blocks']/1024*100):.1f}%")
            self.stat_labels["📁 根目录文件"].config(text=str(info['files_count']))
            
            if hasattr(self, 'buffer_viz'):
                self.buffer_viz.update()
            
            if 'buffer_status' in info:
                self.stat_labels["🧠 命中率"].config(text=info['buffer_status']['statistics']['hit_ratio'])
                
            self.update_disk_viz()
            self.update_monitor()
        except Exception as e:
            print(f"Refresh error: {e}")
        
        self.root.after(2000, self.auto_refresh)

    def on_closing(self):
        """退出前强制将缓冲脏页同步至磁盘"""
        self.filesystem.shutdown()
        self.root.destroy()

if __name__ == "__main__":
    root = Tk()
    app = OSCourseDesignGUI(root)
    root.mainloop()
