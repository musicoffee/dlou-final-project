"""先运行本文件，再运行 client.py。浏览器根地址用于查看服务状态。"""
import getpass
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from service import LearningService


def make_server(service, host='127.0.0.1', port=8765):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # 不记录请求体或登录凭据。

        def reply(self, status, payload):
            raw = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def reply_home(self):
            # 这里仅显示服务状态，系统的实际操作界面仍由 client.py 提供。
            page = '''<!doctype html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>红色文化学习打卡系统</title>
    <style>
        body { font-family: sans-serif; background: #f5f5f5; margin: 0; }
        main { max-width: 620px; margin: 100px auto; padding: 36px;
               background: white; border-radius: 12px; box-shadow: 0 4px 18px #ddd; }
        h1 { color: #9e2929; }
        code { background: #f0f0f0; padding: 3px 7px; border-radius: 4px; }
    </style>
</head>
<body>
    <main>
        <h1>服务端运行正常</h1>
        <p>红色文化学习打卡系统的服务端已经启动。</p>
        <p>本项目是 C/S 桌面程序，请保持 server.py 运行，再运行
           <code>client.py</code> 打开登录和管理界面。</p>
        <p>接口健康检查：<a href="/health">/health</a></p>
    </main>
</body>
</html>'''
            raw = page.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path == '/':
                self.reply_home()
            elif self.path == '/health':
                self.reply(200, {'ok': True, 'data': '红色文化学习服务端运行中'})
            else:
                self.reply(404, {'ok': False, 'message': '接口不存在'})

        def do_POST(self):
            if self.path != '/api':
                self.reply(404, {'ok': False, 'message': '接口不存在'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 65536:
                    raise ValueError('请求体大小无效')
                self.connection.settimeout(10)
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict) or not isinstance(payload.get('action'), str):
                    raise ValueError('需要 action 字符串和 data 对象')
                token = self.headers.get('Authorization', '').removeprefix('Bearer ')
                result = service.handle(payload['action'], payload.get('data', {}), token)
                self.reply(200, {'ok': True, 'data': result})
            except PermissionError as error:
                self.reply(401, {'ok': False, 'message': str(error)})
            except (ValueError, TypeError) as error:
                self.reply(400, {'ok': False, 'message': str(error)})
            except Exception:
                self.reply(500, {'ok': False, 'message': '服务端处理失败，请稍后重试'})
    return ThreadingHTTPServer((host, port), Handler)


def main():
    service = LearningService()
    if not service.has_admin():
        print('首次启动，请设置唯一管理员（密码不会显示）。')
        while True:
            username = input('管理员用户名：').strip()
            password = getpass.getpass('管理员密码（至少6位）：')
            confirm = getpass.getpass('确认密码：')
            if password != confirm:
                print('两次密码不一致，请重新输入。')
                continue
            try:
                service.create_admin(username, password)
                break
            except ValueError as error:
                print(error)
    host = os.environ.get('LEARNING_HOST', '127.0.0.1')
    port = int(os.environ.get('LEARNING_PORT', '8765'))
    server = make_server(service, host, port)
    print(f'服务端已启动：http://{host}:{port}，现在可以运行 client.py。')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n服务端已停止。')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
