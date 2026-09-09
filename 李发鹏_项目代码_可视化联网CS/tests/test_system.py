"""使用临时数据库与真实 HTTP 服务测试，不修改项目的学习数据。"""
import json
import sqlite3
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from service import LearningService
from server import make_server
from api_client import ApiClient


class SystemTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / 'test.db'
        self.service = LearningService(self.db)
        self.server = make_server(self.service, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.admin = self.login('lfp', '123456')
        self.user = self.register('student')
        self.other = self.register('other')
        self.admin.call('save_place', {'name': '测试景点', 'location': '测试位置', 'history': '仅用于自动化测试'})
        self.place_id = self.admin.call('list_places')[0]['id']

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def login(self, username, password='testpass1'):
        client = ApiClient(self.url)
        client.token = client.call('login', {'username': username, 'password': password})['token']
        return client

    def register(self, username):
        ApiClient(self.url).call('register', {'username': username, 'password': 'testpass1', 'confirm_password': 'testpass1'})
        return self.login(username)

    def test_registration_and_permissions(self):
        self.assertEqual(self.user.call('profile')['points'], 0)
        with self.assertRaisesRegex(ValueError, '已存在'):
            self.register('student')
        with self.assertRaisesRegex(ValueError, '不一致'):
            ApiClient(self.url).call('register', {'username': 'new', 'password': 'abcdef', 'confirm_password': 'xxxxxx'})
        with self.assertRaisesRegex(ValueError, '管理员专用'):
            ApiClient(self.url).call('register', {'username': 'lfp', 'password': 'abcdef', 'confirm_password': 'abcdef'})
        with self.assertRaisesRegex(ValueError, '管理员权限'):
            self.user.call('save_place', {'name': 'bad'})
        with self.assertRaises(ValueError):
            ApiClient(self.url).call('profile')
        with self.assertRaises(ValueError):
            ApiClient(self.url).call('login', {'username': 'student', 'password': 'wrongpass'})
        with self.assertRaisesRegex(ValueError, '用户名或密码错误'):
            self.login('lfp', '654321')
        with self.assertRaisesRegex(ValueError, '管理员不参与'):
            self.admin.call('checkin', {'place_id': self.place_id, 'reflection': '管理员打卡'})
        with self.assertRaisesRegex(ValueError, '账号固定'):
            self.admin.call('update_profile', {'username': 'other', 'old_password': '123456',
                                               'password': 'abcdef', 'confirm_password': 'abcdef'})
        self.assertNotIn('password_hash', self.admin.call('list_users')[0])
        with sqlite3.connect(self.db) as db:
            columns = [row[1] for row in db.execute('PRAGMA table_info(users)')]
            self.assertNotIn('role', columns)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0], 2)

    def test_checkin_score_hot_and_ownership(self):
        for i in range(9):
            self.user.call('checkin', {'place_id': self.place_id, 'reflection': f'心得{i}'})
        self.assertEqual(self.user.call('hot_places'), [])
        self.user.call('checkin', {'place_id': self.place_id, 'reflection': '第十次学习'})
        self.assertEqual(self.user.call('profile')['points'], 10)
        self.assertEqual(self.user.call('hot_places')[0]['checkins'], 10)
        record = self.user.call('list_records')[0]
        with self.assertRaises(ValueError):
            self.other.call('delete_record', {'id': record['id']})
        with self.assertRaises(ValueError):
            self.other.call('update_record', {'id': record['id'], 'reflection': '越权修改'})
        self.assertEqual(self.other.call('list_records'), [])
        self.user.call('update_record', {'id': record['id'], 'reflection': '修改心得', 'place_id': 999})
        updated = self.user.call('list_records', {'id': record['id']})[0]
        self.assertEqual(updated['created_at'], record['created_at'])
        self.assertEqual(updated['place_id'], self.place_id)
        self.assertEqual(updated['reflection'], '修改心得')
        with self.assertRaisesRegex(ValueError, '不能删除'):
            self.admin.call('delete_place', {'id': self.place_id})
        self.user.call('delete_record', {'id': record['id']})
        self.assertEqual(self.user.call('profile')['points'], 9)
        self.assertEqual(self.user.call('hot_places'), [])
        with self.assertRaises(ValueError):
            self.user.call('delete_record', {'id': record['id']})
        self.assertEqual(self.user.call('profile')['points'], 9)

    def test_notice_and_place_crud_search(self):
        self.admin.call('save_notice', {'title': '学习公告', 'content': '测试内容', 'remark': '备注'})
        notice = self.user.call('list_notices', {'keyword': '学习'})[0]
        self.admin.call('save_notice', {'id': notice['id'], 'title': '修改公告', 'content': '新内容', 'remark': ''})
        self.assertEqual(self.user.call('list_notices', {'id': notice['id']})[0]['content'], '新内容')
        self.assertEqual(self.user.call('list_notices', {'keyword': '不存在'}), [])
        self.admin.call('delete_notice', {'id': notice['id']})
        self.assertEqual(self.user.call('list_notices'), [])
        self.admin.call('save_place', {'id': self.place_id, 'name': '修改景点', 'location': '新位置', 'history': '新介绍'})
        self.assertEqual(self.user.call('list_places', {'keyword': '修改'})[0]['location'], '新位置')
        self.assertEqual(self.user.call('list_places', {'keyword': "' OR 1=1 --"}), [])
        self.admin.call('delete_place', {'id': self.place_id})
        self.assertEqual(self.user.call('list_places'), [])

    def test_profile_and_session_invalidation(self):
        another_login = self.login('student')
        self.user.call('update_profile', {'username': 'renamed', 'old_password': 'testpass1',
                                        'password': 'newpass2', 'confirm_password': 'newpass2'})
        with self.assertRaises(ValueError):
            self.user.call('profile')
        with self.assertRaises(ValueError):
            another_login.call('profile')
        client = ApiClient(self.url)
        result = client.call('login', {'username': 'renamed', 'password': 'newpass2'})
        client.token = result['token']
        client.call('logout')
        with self.assertRaises(ValueError):
            client.call('profile')

    def test_record_filters_validation_and_persistence(self):
        for text in ['第一次', '第二次']:
            self.user.call('checkin', {'place_id': self.place_id, 'reflection': text})
        old = self.user.call('list_records', {'sort': 'oldest', 'place_id': self.place_id})
        new = self.user.call('list_records', {'sort': 'newest'})
        self.assertEqual(old[0]['id'], new[-1]['id'])
        for data in [{'place_id': 999, 'reflection': '不存在'}, {'place_id': self.place_id, 'reflection': ''},
                     {'place_id': -1, 'reflection': '错误'}, {'place_id': True, 'reflection': '错误'}]:
            with self.assertRaises(ValueError):
                self.user.call('checkin', data)
        with self.assertRaises(ValueError):
            self.user.call('list_records', {'sort': 'DROP TABLE records'})
        restarted = LearningService(self.db)
        token = restarted.handle('login', {'username': 'student', 'password': 'testpass1'})['token']
        self.assertEqual(restarted.handle('profile', {}, token)['points'], 2)

    def test_concurrent_checkins(self):
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(lambda i: self.user.call('checkin', {'place_id': self.place_id, 'reflection': f'并发测试{i}'}), range(10)))
        self.assertEqual(len(results), 10)
        self.assertEqual(self.user.call('profile')['points'], 10)
        self.assertEqual(self.user.call('hot_places')[0]['checkins'], 10)

    def test_http_invalid_json_and_health(self):
        with urlopen(self.url + '/health') as response:
            self.assertTrue(json.load(response)['ok'])
        self.assertIn('运行中', ApiClient(self.url).health())
        request = Request(self.url + '/api', data=b'{bad json')
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 400)
        error.exception.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
