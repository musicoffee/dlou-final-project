"""业务逻辑：检查权限、执行查询、处理打卡。"""
import hashlib
import hmac
import secrets
import sqlite3
import threading
import time
from datetime import datetime
from database import connect, initialize, DEFAULT_DB


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 200000).hex()


def text_field(data, key, limit=200, required=True):
    value = data.get(key, '')
    if not isinstance(value, str):
        raise ValueError(f'{key} 必须是文本')
    value = value.strip()
    if required and not value:
        raise ValueError(f'{key} 不能为空')
    if len(value) > limit:
        raise ValueError(f'{key} 最多 {limit} 个字符')
    return value


def read_password(data, key='password'):
    value = data.get(key, '')
    if not isinstance(value, str) or not 6 <= len(value) <= 128:
        raise ValueError('密码长度应为 6～128 个字符')
    return value


def read_id(data, key='id', optional=False):
    value = data.get(key, '')
    if optional and value in ('', None):
        return None
    if isinstance(value, bool) or not str(value).isdigit() or int(value) <= 0:
        raise ValueError(f'{key} 必须是正整数')
    return int(value)


class LearningService:
    def __init__(self, db_path=DEFAULT_DB):
        self.db_path = db_path
        initialize(db_path)
        self.sessions = {}
        self.session_lock = threading.Lock()

    def create_admin(self, username, password):
        username = text_field({'username': username}, 'username', 30)
        password = read_password({'password': password})
        salt = secrets.token_hex(16)
        with connect(self.db_path) as db:
            db.execute('INSERT INTO users(username,password_hash,salt,role) VALUES(?,?,?,?)',
                       (username, password_hash(password, salt), salt, 'admin'))

    def has_admin(self):
        with connect(self.db_path) as db:
            return db.execute("SELECT id FROM users WHERE role='admin'").fetchone() is not None

    def profile(self, db, user_id):
        row = db.execute('''SELECT id,username,role,
            (SELECT COUNT(*) FROM records WHERE user_id=users.id) AS points
            FROM users WHERE id=?''', (user_id,)).fetchone()
        if row is None:
            raise PermissionError('用户不存在，请重新登录')
        return dict(row)

    def handle(self, action, data, token=''):
        if not isinstance(data, dict):
            raise ValueError('data 必须是对象')
        # 每次请求单独连接，with 中的写操作成功后提交，失败则回滚。
        with connect(self.db_path) as db:
            if action == 'register':
                username = text_field(data, 'username', 30)
                password = read_password(data)
                if password != data.get('confirm_password'):
                    raise ValueError('两次密码不一致')
                salt = secrets.token_hex(16)
                try:
                    db.execute('INSERT INTO users(username,password_hash,salt) VALUES(?,?,?)',
                               (username, password_hash(password, salt), salt))
                except sqlite3.IntegrityError:
                    raise ValueError('用户名已存在') from None
                return {'message': '注册成功，请登录'}
            if action == 'login':
                username = text_field(data, 'username', 30)
                password = read_password(data)
                user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
                if not user or not hmac.compare_digest(password_hash(password, user['salt']), user['password_hash']):
                    raise PermissionError('用户名或密码错误')
                new_token = secrets.token_urlsafe(32)
                with self.session_lock:
                    self.sessions = {k: v for k, v in self.sessions.items() if v[1] > time.time()}
                    self.sessions[new_token] = (user['id'], time.time() + 8 * 3600)
                return {'token': new_token, 'user': self.profile(db, user['id'])}

            with self.session_lock:
                session = self.sessions.get(token)
            if not session or session[1] <= time.time():
                raise PermissionError('登录已失效，请重新登录')
            user = self.profile(db, session[0])
            user_id = user['id']
            if action == 'logout':
                with self.session_lock:
                    self.sessions.pop(token, None)
                return {'message': '已退出登录'}
            if action == 'profile':
                return user
            if action == 'update_profile':
                old_password = read_password(data, 'old_password')
                saved = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
                if not hmac.compare_digest(password_hash(old_password, saved['salt']), saved['password_hash']):
                    raise ValueError('原密码不正确')
                username = text_field(data, 'username', 30)
                new_password = read_password(data)
                if new_password != data.get('confirm_password'):
                    raise ValueError('两次新密码不一致')
                salt = secrets.token_hex(16)
                try:
                    db.execute('UPDATE users SET username=?,password_hash=?,salt=? WHERE id=?',
                               (username, password_hash(new_password, salt), salt, user_id))
                except sqlite3.IntegrityError:
                    raise ValueError('用户名已存在') from None
                with self.session_lock:
                    self.sessions = {k: v for k, v in self.sessions.items() if v[0] != user_id}
                return {'message': '资料已修改，请重新登录'}
            if action == 'list_notices':
                number = read_id(data, optional=True)
                keyword = text_field(data, 'keyword', required=False)
                return [dict(r) for r in db.execute('''SELECT * FROM notices
                    WHERE (? IS NULL OR id=?) AND instr(title,?)>0 ORDER BY id DESC''',
                    (number, number, keyword))]
            if action in ('list_places', 'hot_places'):
                number = read_id(data, optional=True)
                keyword = text_field(data, 'keyword', required=False)
                rows = db.execute('''SELECT p.*,COUNT(r.id) AS checkins FROM places p
                    LEFT JOIN records r ON r.place_id=p.id
                    WHERE (? IS NULL OR p.id=?) AND instr(p.name,?)>0
                    GROUP BY p.id ORDER BY checkins DESC,p.id ASC''', (number, number, keyword))
                places = [dict(r) for r in rows]
                for place in places:
                    place['is_hot'] = place['checkins'] >= 10
                return [p for p in places if p['is_hot']] if action == 'hot_places' else places
            if action == 'list_records':
                record_id = read_id(data, optional=True)
                place_id = read_id(data, 'place_id', optional=True)
                # 排序只能从固定白名单选择，不能把用户输入直接拼进 SQL。
                orders = {'newest': 'r.id DESC', 'oldest': 'r.id ASC', 'place': 'r.place_id ASC,r.id DESC'}
                order = orders.get(data.get('sort', 'newest'))
                if order is None:
                    raise ValueError('排序方式无效')
                return [dict(r) for r in db.execute('''SELECT r.*,p.name,p.location,p.history
                    FROM records r JOIN places p ON p.id=r.place_id
                    WHERE user_id=? AND (? IS NULL OR r.id=?) AND (? IS NULL OR place_id=?)
                    ORDER BY ''' + order, (user_id, record_id, record_id, place_id, place_id))]
            if action == 'checkin':
                place_id = read_id(data, 'place_id')
                reflection = text_field(data, 'reflection', 3000)
                if not db.execute('SELECT id FROM places WHERE id=?', (place_id,)).fetchone():
                    raise ValueError('景点不存在')
                db.execute('INSERT INTO records(user_id,place_id,created_at,reflection) VALUES(?,?,?,?)',
                           (user_id, place_id, now(), reflection))
                return {'message': '打卡成功，学习积分 +1'}
            if action in ('update_record', 'delete_record'):
                number = read_id(data)
                if action == 'update_record':
                    reflection = text_field(data, 'reflection', 3000)
                    result = db.execute('UPDATE records SET reflection=? WHERE id=? AND user_id=?',
                                        (reflection, number, user_id))
                else:
                    result = db.execute('DELETE FROM records WHERE id=? AND user_id=?', (number, user_id))
                if result.rowcount == 0:
                    raise ValueError('记录不存在或不属于当前用户')
                return {'message': '心得已修改' if action == 'update_record' else '记录已删除，学习积分 -1'}

            if user['role'] != 'admin':
                raise PermissionError('该操作需要管理员权限')
            if action == 'list_users':
                return [dict(r) for r in db.execute('''SELECT id,username,role,
                    (SELECT COUNT(*) FROM records WHERE user_id=users.id) AS points FROM users ORDER BY id''')]
            if action == 'save_place':
                fields = (text_field(data, 'name', 100), text_field(data, 'location', 200), text_field(data, 'history', 5000))
                number = read_id(data, optional=True)
                if number:
                    result = db.execute('UPDATE places SET name=?,location=?,history=? WHERE id=?', fields + (number,))
                    if not result.rowcount:
                        raise ValueError('景点不存在')
                else:
                    db.execute('INSERT INTO places(name,location,history) VALUES(?,?,?)', fields)
                return {'message': '景点已保存'}
            if action == 'save_notice':
                fields = (text_field(data, 'title', 100), text_field(data, 'content', 5000), text_field(data, 'remark', 500, False))
                number = read_id(data, optional=True)
                if number:
                    result = db.execute('UPDATE notices SET title=?,content=?,remark=? WHERE id=?', fields + (number,))
                    if not result.rowcount:
                        raise ValueError('公告不存在')
                else:
                    db.execute('INSERT INTO notices(title,content,remark,published_at) VALUES(?,?,?,?)', fields + (now(),))
                return {'message': '公告已保存'}
            if action in ('delete_place', 'delete_notice'):
                number = read_id(data)
                table = 'places' if action == 'delete_place' else 'notices'
                try:
                    result = db.execute(f'DELETE FROM {table} WHERE id=?', (number,))
                except sqlite3.IntegrityError:
                    raise ValueError('该景点已有打卡记录，不能删除；可以修改景点介绍') from None
                if not result.rowcount:
                    raise ValueError('数据不存在')
                return {'message': '已删除'}
            raise ValueError('未知操作')
