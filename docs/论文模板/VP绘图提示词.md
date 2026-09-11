# 红色文化学习打卡系统 VP 绘图提示词

以下图片是按照老师给出的四章模板仍需准备的系统分析与设计图。建议在 Visual Paradigm 中使用 AI 生成功能，生成后导出为高清 PNG，同时保留可编辑的 VP 工程文件。所有图统一采用白底、黑色线条、中文标注、无渐变、无阴影的课程论文风格。

## 1 用户学习打卡活动图

```text
请生成 UML 活动图，标题为“红色文化学习打卡系统——用户学习打卡活动图”。参与者为普通用户。流程：开始→打开客户端→填写服务端地址、用户名和密码→判断是否已有账号；没有账号时进入注册页面，输入用户名、密码和确认密码，服务端校验后注册成功并返回登录页；已有账号或注册完成后提交登录→服务端验证身份→登录成功进入主界面→查看公告或查询红色景点→可按景点编号或名称筛选→选择景点→填写学习心得→判断心得是否为空；为空时提示重新填写，不为空时提交打卡→服务端校验会话令牌和景点编号→向 records 表新增记录→返回“打卡成功，学习积分 +1”→刷新个人积分和学习记录→结束。登录失败、景点不存在、网络连接失败分别用异常分支返回相应提示。使用标准 UML 初始节点、活动节点、判断节点、合并节点和终止节点，箭头方向清晰，A4 纵向，白底黑线，中文标签。
```

## 2 领域静态类图 仅含属性

```text
请生成 UML 静态类图，标题为“红色文化学习打卡系统——领域静态类图”。只显示类名和属性，不显示任何方法。包含四个领域类：User（id:int，username:string，password_hash:string，salt:string）；ScenicSpot（id:int，name:string，location:string，history:string）；CheckInRecord（id:int，user_id:int，place_id:int，created_at:string，reflection:string）；Announcement（id:int，title:string，content:string，published_at:string，remark:string）。关系：User 1 对多 CheckInRecord，ScenicSpot 1 对多 CheckInRecord；User 与 ScenicSpot 通过 CheckInRecord 构成多对多学习打卡关系；Announcement 与其他实体无直接外键关系。管理员是服务端固定账号，不是数据库实体，不要画 Admin 类，不要添加 role、score、check_count 字段。使用标准 UML 类框和多重度标记，白底黑线，横向布局，中文说明。
```

## 3 用户学习打卡顺序图

```text
请生成 UML 顺序图，标题为“红色文化学习打卡系统——用户学习打卡顺序图”。生命线从左到右依次为：普通用户、LearningApp 客户端界面、ApiClient 通信类、HTTP Handler 请求处理器、LearningService 业务类、SQLite 数据库。消息流程：用户选择景点并填写心得→LearningApp 调用 request('checkin', data)→ApiClient.call('checkin', data)→向 POST /api 发送 JSON，请求头携带 Bearer token→Handler 解析 action、data 和 token→LearningService.handle('checkin', data, token)→校验会话是否有效→校验当前账号不是管理员→查询 places 表确认景点存在→向 records 表执行参数化 INSERT，写入 user_id、place_id、created_at、reflection→数据库提交→逐层返回打卡成功信息→LearningApp 刷新个人积分和学习记录。增加 alt 组合片段：会话失效返回 401；心得为空或景点不存在返回 400；成功返回 200。使用标准 UML 激活条、同步消息和返回消息，A4 横向，白底黑线，中文标注。
```

## 4 分析类图 含属性和方法

```text
请生成 UML 分析类图，标题为“红色文化学习打卡系统——分析类图”。类分为边界类、控制类和实体类。边界类 LearningApp，属性 root、api、tables、rows、busy，方法 request()、logged_in()、load()、checkin()、edit_record()、delete()、logout()。控制类 ApiClient，属性 base_url、token，方法 send()、health()、call()。控制类 HTTPHandler，属性 service，方法 do_GET()、do_POST()、reply()、reply_home()。控制类 LearningService，属性 db_path、sessions、session_lock，方法 profile()、handle()。实体类 User、ScenicSpot、CheckInRecord、Announcement，属性与数据库字段一致。依赖关系：LearningApp 使用 ApiClient，ApiClient 通过 HTTP/JSON 调用 HTTPHandler，HTTPHandler 调用 LearningService，LearningService 访问四个实体对应的 SQLite 表。管理员为服务端固定身份，不单独建实体类。类框显示可见性符号、属性类型、方法和返回类型，白底黑线，横向布局。
```

## 5 系统逻辑结构示意图

```text
请生成系统逻辑结构示意图，标题为“红色文化学习打卡系统——逻辑结构模型”。按从上到下四层绘制：表示层为 Tkinter/ttk 桌面客户端，包含登录注册、公告浏览、景点查询、学习打卡、记录管理、管理员维护界面；通信层为 ApiClient、HTTP/JSON、Bearer token；业务层为 ThreadingHTTPServer、HTTP Handler、LearningService，包含参数校验、身份认证、权限控制、业务处理和异常响应；数据层为 SQLite，包含 users、places、records、notices 四张表。箭头显示客户端请求经过通信层进入业务层，再访问数据层并返回结果。注明管理员身份由服务端固定配置识别，不保存到 users 表。使用分层架构图风格，白底黑线，A4 横向，中文标注。
```

## 6 系统物理结构示意图

```text
请生成系统物理结构示意图，标题为“红色文化学习打卡系统——物理结构模型”。包含两种连接场景：场景一，同一台 MacBook Air 上运行 client.py 和 server.py，客户端通过 http://127.0.0.1:8765 访问服务端；场景二，同一局域网中的客户端电脑运行 client.py，通过 http://服务端电脑局域网IP:8765 访问服务端电脑。服务端监听 0.0.0.0:8765，服务端进程访问本机 data/learning.db SQLite 文件，客户端不能直接访问数据库。图中显示客户端电脑、无线路由器或局域网、服务端电脑、Python 服务进程和 SQLite 数据库文件，标注 HTTP/JSON 和端口 8765。白底黑线，部署图风格，A4 横向，中文标注。
```

## 7 EAD 实体属性图

```text
请生成 EAD 实体属性图，标题为“红色文化学习打卡系统——实体属性图 EAD”。包含四个实体及属性：用户 users：id 主键、username 唯一且非空、password_hash 非空、salt 非空；景点 places：id 主键、name 非空、location 非空、history 非空；学习记录 records：id 主键、user_id 外键且非空、place_id 外键且非空、created_at 非空、reflection 非空；公告 notices：id 主键、title 非空、content 非空、published_at 非空、remark 默认空字符串。使用实体矩形、属性椭圆或 Visual Paradigm 标准 EAD 表示法，主键清楚标识。管理员不是数据库实体，不要添加 admin 表、role、score、check_count 字段。白底黑线，横向布局，中文标注。
```

## 8 ERD 数据库实体关系图

```text
请生成 Crow's Foot ERD，标题为“红色文化学习打卡系统——数据库 ERD”。包含四张表：users(id INTEGER PK AUTOINCREMENT，username TEXT NOT NULL UNIQUE，password_hash TEXT NOT NULL，salt TEXT NOT NULL)；places(id INTEGER PK AUTOINCREMENT，name TEXT NOT NULL，location TEXT NOT NULL，history TEXT NOT NULL)；records(id INTEGER PK AUTOINCREMENT，user_id INTEGER NOT NULL FK→users.id，place_id INTEGER NOT NULL FK→places.id ON DELETE RESTRICT，created_at TEXT NOT NULL，reflection TEXT NOT NULL)；notices(id INTEGER PK AUTOINCREMENT，title TEXT NOT NULL，content TEXT NOT NULL，published_at TEXT NOT NULL，remark TEXT NOT NULL DEFAULT '')。关系：users 1 对多 records，places 1 对多 records；records.user_id 和 records.place_id 必须有对应父记录；删除已有打卡记录关联的景点时受限；notices 无外键。管理员为服务端固定账号，不保存到数据库，因此不要创建 admin 表，也不要添加 role、score、check_count 字段。白底黑线，表名和字段清楚，横向布局，适合本科论文插图。
```

## 导出要求

1. 图片标题可保留在 VP 工程中，但论文插图最好由 Word 图题统一编号。
2. 横向图建议导出宽度不低于 2200 像素，纵向图不低于 1600 像素。
3. 优先同时保存 `.vpp` 和 `.png`；如果 VP 支持 SVG，可额外导出 SVG 备用。
4. 文件名建议依次为：`图1.1_用户学习打卡活动图.png`、`图1.3_领域静态类图.png`、`图1.4_用户学习打卡顺序图.png`、`图1.5_分析类图.png`、`图2.1_逻辑结构模型.png`、`图2.2_物理结构模型.png`、`图2.4_EAD.png`、`图2.5_ERD.png`。
