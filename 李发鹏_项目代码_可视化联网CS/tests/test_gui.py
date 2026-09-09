"""桌面流程冒烟测试：真实 Tk 窗口 + 临时 HTTP 服务，无正式数据。"""
from pathlib import Path
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk
from unittest.mock import patch
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from client import LearningApp
from service import LearningService
from server import make_server


class GuiTest(unittest.TestCase):
    def test_desktop_flow(self):
        with tempfile.TemporaryDirectory() as folder:
            service = LearningService(Path(folder) / 'gui.db')
            service.create_admin('gui_admin', 'testpass1')
            token = service.handle('login', {'username': 'gui_admin', 'password': 'testpass1'})['token']
            service.handle('save_place', {'name': '界面测试景点', 'location': '测试位置', 'history': '界面测试内容'}, token)
            server = make_server(service, port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            root = tk.Tk()
            app = LearningApp(root)
            app.api.base_url = f'http://127.0.0.1:{server.server_port}'
            errors = []
            root.report_callback_exception = lambda kind, value, trace: errors.append(str(value))
            def wait():
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    root.update()
                    if not app.busy:
                        break
                    time.sleep(0.02)
                self.assertFalse(app.busy, '网络请求超时')
                self.assertEqual(errors, [])
            def descendants(widget):
                result = []
                for child in widget.winfo_children():
                    result.append(child)
                    result.extend(descendants(child))
                return result
            try:
                with patch('client.messagebox.showerror', side_effect=lambda title, text, **kw: errors.append(text)), patch('client.messagebox.askyesno', return_value=True):
                    app.request('login', {'username': 'gui_admin', 'password': 'testpass1'}, app.logged_in)
                    wait()
                    self.assertEqual(len(app.tables['places'].get_children()), 1)
                    self.assertIn('学习积分：0', app.profile_text.get())
                    app.tables['places'].selection_set('1')
                    root.update()
                    app.checkin('places')
                    root.update()
                    dialog = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
                    fields = descendants(dialog)
                    next(w for w in fields if isinstance(w, tk.Text)).insert('1.0', '我通过窗口提交的测试心得')
                    next(w for w in fields if isinstance(w, ttk.Button) and w.cget('text') == '提交').invoke()
                    wait()
                    self.assertIn('学习积分：1', app.profile_text.get())
                    self.assertEqual(app.rows['places']['1']['checkins'], 1)
                    app.load('records')
                    wait()
                    self.assertEqual(len(app.tables['records'].get_children()), 1)
                    app.tables['records'].selection_set('1')
                    app.delete('records', 'delete_record')
                    wait()
                    self.assertEqual(len(app.tables['records'].get_children()), 0)
                    self.assertIn('学习积分：0', app.profile_text.get())
            finally:
                root.destroy()
                server.shutdown()
                server.server_close()
                thread.join()


if __name__ == '__main__':
    unittest.main(verbosity=2)
