"""桌面窗口入口。先运行 server.py，再点击本文件的 Run。"""
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from api_client import ApiClient


class LearningApp:
    def __init__(self, root):
        self.root = root
        self.api = ApiClient()
        self.user = None
        self.busy = False
        self.results = queue.Queue()
        self.rows = {}
        root.title('红色文化学习打卡系统 · 联网客户端')
        root.geometry('1100x740')
        root.minsize(850, 620)
        style = ttk.Style()
        style.configure('Treeview', rowheight=30)
        style.configure('Title.TLabel', font=('', 20, 'bold'), foreground='#9e2929')
        style.configure('TButton', padding=(10, 6))
        self.body = ttk.Frame(root, padding=20)
        self.body.pack(fill='both', expand=True)
        self.status = tk.StringVar(value='请先启动服务端，再登录。')
        ttk.Label(root, textvariable=self.status, padding=8).pack(fill='x')
        self.show_login()
        self.root.after(80, self.poll)

    def clear(self):
        for child in self.body.winfo_children():
            child.destroy()
        self.rows = {}

    def request(self, action, data, callback):
        # 耗时联网放在线程中，窗口更新只在主线程执行。
        if self.busy:
            messagebox.showinfo('稍等', '上一项操作正在处理中。', parent=self.root)
            return
        self.busy = True
        self.status.set('正在连接服务器……')
        def work():
            try:
                self.results.put((callback, self.api.call(action, data), None))
            except Exception as error:
                self.results.put((callback, None, str(error)))
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            callback, result, error = self.results.get_nowait()
            self.busy = False
            if error:
                self.status.set(error)
                messagebox.showerror('操作未完成', error, parent=self.root)
            else:
                self.status.set('操作完成')
                callback(result)
        except queue.Empty:
            pass
        finally:
            self.root.after(80, self.poll)

    def show_login(self):
        self.clear()
        self.user = None
        self.api.token = ''
        frame = ttk.Frame(self.body, padding=25)
        frame.pack(expand=True)
        ttk.Label(frame, text='红色文化学习打卡', style='Title.TLabel').pack(pady=18)
        fields = {}
        for key, label, default in [('address', '服务端地址', self.api.base_url), ('username', '用户名', ''), ('password', '密码', '')]:
            ttk.Label(frame, text=label).pack(anchor='w', pady=(10, 4))
            entry = ttk.Entry(frame, width=40, show='*' if key == 'password' else '')
            entry.insert(0, default)
            entry.pack(fill='x')
            fields[key] = entry
        def login():
            address = fields['address'].get().strip()
            if not address.startswith(('http://', 'https://')):
                messagebox.showerror('地址错误', '地址应以 http:// 或 https:// 开头')
                return
            self.api.base_url = address.rstrip('/')
            self.request('login', {k: fields[k].get() for k in ('username', 'password')}, self.logged_in)
        ttk.Button(frame, text='登录', command=login).pack(fill='x', pady=(20, 8))
        ttk.Button(frame, text='注册新用户', command=lambda: self.register(fields['address'].get())).pack(fill='x')
        ttk.Label(frame, text='同机演示使用默认地址；跨电脑时填写服务端电脑的局域网 IP。', wraplength=420).pack(pady=20)

    def register(self, address):
        self.api.base_url = address.strip().rstrip('/')
        self.form('注册用户', [('username', '用户名', ''), ('password', '密码', ''),
                  ('confirm_password', '确认密码', '')], 'register', {}, lambda: None)

    def logged_in(self, result):
        self.api.token = result['token']
        self.user = result['user']
        self.show_home()

    def show_home(self):
        self.clear()
        header = ttk.Frame(self.body)
        header.pack(fill='x', pady=(0, 16))
        ttk.Label(header, text='红色文化学习打卡', style='Title.TLabel').pack(side='left')
        self.profile_text = tk.StringVar()
        self.update_header()
        ttk.Label(header, textvariable=self.profile_text).pack(side='left', padx=22)
        ttk.Button(header, text='退出登录', command=lambda: self.request('logout', {}, lambda _: self.show_login())).pack(side='right')
        tabs = ttk.Notebook(self.body)
        tabs.pack(fill='both', expand=True)
        self.tables = {}
        self.filters = {}
        self.details = {}
        for kind, title, columns in [
            ('places', '景点与打卡', [('id', '编号'), ('name', '景点名'), ('location', '位置'), ('checkins', '打卡次数'), ('is_hot', '热门')]),
            ('hot', '热门排行榜', [('id', '编号'), ('name', '景点名'), ('location', '位置'), ('checkins', '打卡次数')]),
            ('notices', '公告', [('id', '编号'), ('title', '标题'), ('published_at', '发布日期'), ('remark', '备注')]),
            ('records', '我的学习记录', [('id', '记录编号'), ('place_id', '景点编号'), ('name', '景点名'), ('created_at', '打卡时间')])]:
            frame = ttk.Frame(tabs, padding=12)
            tabs.add(frame, text=title)
            self.build_list(frame, kind, columns)
        profile = ttk.Frame(tabs, padding=25)
        tabs.add(profile, text='个人信息')
        ttk.Label(profile, textvariable=self.profile_text, font=('', 16)).pack(anchor='w', pady=10)
        ttk.Label(profile, text='密码：******（系统不显示原密码）').pack(anchor='w', pady=10)
        ttk.Button(profile, text='修改用户名和密码', command=self.edit_profile).pack(anchor='w', pady=10)
        if self.user['role'] == 'admin':
            frame = ttk.Frame(tabs, padding=12)
            tabs.add(frame, text='用户列表')
            self.build_list(frame, 'users', [('id', '编号'), ('username', '用户名'), ('role', '身份'), ('points', '积分')])
        tabs.bind('<<NotebookTabChanged>>', lambda _: self.load_current(tabs))
        self.load('places')

    def update_header(self):
        role = '管理员' if self.user['role'] == 'admin' else '用户'
        self.profile_text.set(f"{self.user['username']}  |  {role}  |  学习积分：{self.user['points']}")

    def load_current(self, tabs):
        if self.busy:
            return
        names = ['places', 'hot', 'notices', 'records', None, 'users']
        kind = names[tabs.index(tabs.select())]
        if kind:
            self.load(kind)

    def build_list(self, frame, kind, columns):
        bar = ttk.Frame(frame)
        bar.pack(fill='x', pady=(0, 10))
        fields = {}
        if kind != 'users':
            for key, label in ([('id', '记录编号'), ('place_id', '景点编号')] if kind == 'records' else [('id', '编号'), ('keyword', '标题' if kind == 'notices' else '景点名')]):
                ttk.Label(bar, text=label).pack(side='left', padx=(0, 5))
                entry = ttk.Entry(bar, width=14)
                entry.pack(side='left', padx=(0, 12))
                fields[key] = entry
        if kind == 'records':
            order = ttk.Combobox(bar, values=['最新在前', '最早在前', '按景点编号'], state='readonly', width=12)
            order.current(0)
            order.pack(side='left', padx=8)
            fields['sort'] = order
        self.filters[kind] = fields
        ttk.Button(bar, text='查询 / 刷新', command=lambda: self.load(kind)).pack(side='left')
        box = ttk.Frame(frame)
        box.pack(fill='both', expand=True)
        table = ttk.Treeview(box, columns=[c[0] for c in columns], show='headings', selectmode='browse')
        for key, label in columns:
            table.heading(key, text=label)
            table.column(key, width=90 if key in ('id', 'place_id', 'checkins', 'is_hot') else 180, minwidth=60)
        scroll = ttk.Scrollbar(box, orient='vertical', command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        table.pack(side='left', fill='both', expand=True)
        scroll.pack(side='right', fill='y')
        self.tables[kind] = table
        detail = tk.Text(frame, height=6, wrap='word', padx=10, pady=10, state='disabled')
        detail.pack(fill='x', pady=10)
        self.details[kind] = detail
        table.bind('<<TreeviewSelect>>', lambda _: self.show_detail(kind))
        actions = ttk.Frame(frame)
        actions.pack(fill='x')
        if kind in ('places', 'hot'):
            ttk.Button(actions, text='给选中景点打卡', command=lambda: self.checkin(kind)).pack(side='left')
        if kind == 'records':
            ttk.Button(actions, text='修改心得', command=self.edit_record).pack(side='left')
            ttk.Button(actions, text='删除记录', command=lambda: self.delete('records', 'delete_record')).pack(side='left', padx=8)
        if self.user['role'] == 'admin' and kind in ('places', 'notices'):
            ttk.Button(actions, text='新增', command=lambda: self.edit_content(kind, False)).pack(side='left', padx=8)
            ttk.Button(actions, text='修改选中项', command=lambda: self.edit_content(kind, True)).pack(side='left')
            action = 'delete_place' if kind == 'places' else 'delete_notice'
            ttk.Button(actions, text='删除选中项', command=lambda: self.delete(kind, action)).pack(side='left', padx=8)

    def load(self, kind):
        data = {key: widget.get() for key, widget in self.filters[kind].items()}
        if kind == 'records':
            data['sort'] = {'最新在前': 'newest', '最早在前': 'oldest', '按景点编号': 'place'}[data['sort']]
        action = {'places': 'list_places', 'hot': 'hot_places', 'notices': 'list_notices', 'records': 'list_records', 'users': 'list_users'}[kind]
        self.request(action, data, lambda rows: self.fill(kind, rows))

    def fill(self, kind, rows):
        table = self.tables[kind]
        table.delete(*table.get_children())
        self.rows[kind] = {str(row['id']): row for row in rows}
        for row in rows:
            values = [('是' if row[key] else '否') if key == 'is_hot' else row[key] for key in table['columns']]
            table.insert('', 'end', iid=str(row['id']), values=values)
        self.set_detail(kind, '选中一行查看完整内容。' if rows else '暂无符合条件的数据。')
        self.status.set(f'已显示 {len(rows)} 条数据')

    def selected(self, kind):
        selection = self.tables[kind].selection()
        if not selection:
            messagebox.showinfo('请选择', '请先选中一行。', parent=self.root)
            return None
        return self.rows[kind][selection[0]]

    def set_detail(self, kind, text):
        widget = self.details[kind]
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', text)
        widget.configure(state='disabled')

    def show_detail(self, kind):
        selection = self.tables[kind].selection()
        if not selection:
            return
        row = self.rows[kind][selection[0]]
        if kind in ('places', 'hot'):
            content = f"{row['name']}\n位置：{row['location']}\n红色历史：{row['history']}"
        elif kind == 'notices':
            content = f"{row['title']}\n{row['content']}\n备注：{row['remark']}"
        elif kind == 'records':
            content = f"{row['name']}（{row['location']}）\n景点介绍：{row['history']}\n打卡心得：{row['reflection']}"
        else:
            content = f"用户名：{row['username']}\n身份：{row['role']}\n积分：{row['points']}"
        self.set_detail(kind, content)

    def form(self, title, fields, action, extra, after):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry('540x560')
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill='both', expand=True)
        widgets = {}
        for key, label, value in fields:
            ttk.Label(frame, text=label).pack(anchor='w', pady=(8, 4))
            if key in ('reflection', 'history', 'content'):
                widget = tk.Text(frame, height=6, wrap='word')
                widget.insert('1.0', str(value))
            else:
                widget = ttk.Entry(frame, show='*' if 'password' in key else '')
                widget.insert(0, str(value))
            widget.pack(fill='x')
            widgets[key] = widget
        def saved(result):
            dialog.destroy()
            self.status.set(result.get('message', '保存成功'))
            after()
        def submit():
            data = dict(extra)
            for key, widget in widgets.items():
                data[key] = widget.get('1.0', 'end-1c') if isinstance(widget, tk.Text) else widget.get()
            self.request(action, data, saved)
        ttk.Button(frame, text='提交', command=submit).pack(pady=20)

    def refresh_points(self, kind=None):
        def done(user):
            self.user = user
            self.update_header()
            if kind:
                self.load(kind)
        self.request('profile', {}, done)

    def checkin(self, kind):
        row = self.selected(kind)
        if row:
            self.form('打卡：' + row['name'], [('reflection', '学习心得（最多3000字）', '')],
                      'checkin', {'place_id': row['id']}, lambda: self.refresh_points(kind))

    def edit_record(self):
        row = self.selected('records')
        if row:
            self.form('修改打卡心得', [('reflection', '学习心得', row['reflection'])],
                      'update_record', {'id': row['id']}, lambda: self.load('records'))

    def edit_profile(self):
        self.form('修改个人信息', [('username', '用户名', self.user['username']), ('old_password', '原密码', ''),
                  ('password', '新密码', ''), ('confirm_password', '确认新密码', '')],
                  'update_profile', {}, self.show_login)

    def edit_content(self, kind, edit):
        row = self.selected(kind) if edit else {}
        if row is None:
            return
        fields = [('name', '景点名'), ('location', '地理位置'), ('history', '红色历史')] if kind == 'places' else [('title', '公告标题'), ('content', '公告内容'), ('remark', '备注')]
        self.form('修改内容' if edit else '新增内容', [(key, label, row.get(key, '')) for key, label in fields],
                  'save_place' if kind == 'places' else 'save_notice',
                  {'id': row['id']} if edit else {}, lambda: self.load(kind))

    def delete(self, kind, action):
        row = self.selected(kind)
        if row and messagebox.askyesno('确认删除', '确定删除选中项？删除学习记录会扣除1积分。', parent=self.root):
            def done(result):
                self.status.set(result['message'])
                if kind == 'records':
                    # 先移除当前行，再从服务端读取最新积分。
                    self.tables[kind].delete(str(row['id']))
                    self.set_detail(kind, '记录已删除。')
                    self.refresh_points()
                else:
                    self.load(kind)
            self.request(action, {'id': row['id']}, done)


if __name__ == '__main__':
    root = tk.Tk()
    LearningApp(root)
    root.mainloop()
