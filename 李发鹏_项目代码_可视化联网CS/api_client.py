"""桌面客户端只通过 HTTP 访问服务器，不直接操作数据库。"""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ApiClient:
    def __init__(self, base_url='http://127.0.0.1:8765'):
        self.base_url = base_url.rstrip('/')
        self.token = ''

    def call(self, action, data=None):
        raw = json.dumps({'action': action, 'data': data or {}}).encode('utf-8')
        request = Request(self.base_url + '/api', data=raw, headers={
            'Content-Type': 'application/json', 'Authorization': 'Bearer ' + self.token})
        try:
            with urlopen(request, timeout=10) as response:
                result = json.load(response)
        except HTTPError as error:
            try:
                message = json.load(error).get('message', '请求失败')
            except (ValueError, AttributeError):
                message = f'服务器返回错误：{error.code}'
            finally:
                error.close()
            raise ValueError(message) from None
        except (URLError, TimeoutError, OSError):
            raise ValueError('无法连接服务器，请检查服务端是否启动、地址是否正确') from None
        if not result.get('ok'):
            raise ValueError(result.get('message', '操作失败'))
        return result['data']
