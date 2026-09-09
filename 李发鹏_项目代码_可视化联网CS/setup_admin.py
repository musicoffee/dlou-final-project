import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from service import LearningService


def main():
    service = LearningService()
    root = tk.Tk()
    root.title('首次设置管理员')
    root.geometry('420x340')
    frame = ttk.Frame(root, padding=25)
    frame.pack(fill='both', expand=True)
    if service.has_admin():
        ttk.Label(frame, text='管理员已设置。\n请运行 server.py，再运行 client.py。').pack(pady=30)
        ttk.Button(frame, text='关闭', command=root.destroy).pack()
    else:
        entries = []
        for label in ['管理员用户名', '密码（至少6位）', '确认密码']:
            ttk.Label(frame, text=label).pack(anchor='w', pady=(10, 4))
            entry = ttk.Entry(frame, show='' if not entries else '*')
            entry.pack(fill='x')
            entries.append(entry)
        def save():
            username, password, confirm = [entry.get() for entry in entries]
            if password != confirm:
                messagebox.showerror('无法保存', '两次密码不一致', parent=root)
                return
            try:
                service.create_admin(username, password)
            except (ValueError, sqlite3.IntegrityError):
                messagebox.showerror('无法保存', '请检查用户名和密码长度，或确认管理员是否已存在。', parent=root)
                return
            messagebox.showinfo('设置成功', '现在请运行 server.py，再运行 client.py。', parent=root)
            root.destroy()
        ttk.Button(frame, text='保存管理员', command=save).pack(pady=20)
    root.mainloop()


if __name__ == '__main__':
    main()
