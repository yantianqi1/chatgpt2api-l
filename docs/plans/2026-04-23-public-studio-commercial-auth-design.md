# 公开生图站商业化鉴权与激活码设计

## 目标

在当前公开生图站能力之上，增加一套可商业化使用的用户鉴权、个人额度、激活码充值和模型单价管理能力，同时保留匿名访问路径。

这次设计需要同时满足四个要求：

- 公开站用户可以自助注册和登录，只使用 `用户名 + 密码`
- 登录用户拥有独立个人额度，匿名用户继续使用公共额度
- 激活码支持后台批量生成、设置额度、一次性兑换和兑换追踪
- 不同模型支持独立价格配置，扣费规则为 `模型单价 × n`

## 已确认业务规则

### 用户与登录

- 公开站用户可以自助注册
- 注册字段只有 `用户名` 和 `密码`
- 注册成功后默认赠送 `1.00` 额度
- 登录后使用服务端会话，不让前端长期持有管理员式密钥

### 匿名与登录用户额度边界

- 公开站继续保留匿名可用
- 匿名请求只扣公共额度池
- 登录用户请求只扣个人额度
- 登录用户个人额度耗尽后，不能回退使用公共额度

### 激活码

- 激活码为 `32` 位
- 每个激活码只能兑换一次
- 谁先兑换成功，额度就加到谁的账户
- 兑换后激活码永久作废
- 后台必须能看到兑换人和兑换时间

### 模型价格

- 当前模型支持单独设置价格
- 扣费规则固定为：`价格 × n`
- 价格和额度都允许小数
- 精度固定为两位小数

## 方案对比

### 方案 A：SQLite + 服务端会话 + 定点计费

做法：

- 引入本地 `sqlite` 数据文件承载用户、会话、激活码、价格和流水
- 使用服务端 session cookie 完成登录态
- 所有价格与额度统一按两位小数的定点值存储

优点：

- 对当前单机自托管项目足够稳定
- 能保证激活码兑换和扣费操作具备原子性
- 方便审计用户充值与扣费流水
- 不需要引入外部数据库，落地成本可控

缺点：

- 需要增加一层持久化服务和迁移初始化逻辑
- 相比现有 JSON 配置复杂度更高

结论：采用。

### 方案 B：继续扩展 JSON 文件

做法：

- 在现有 `public_panel.json` 旁边继续增加用户、激活码、价格等 JSON 文件

优点：

- 开发速度快

缺点：

- 并发安全差
- 一次性兑换和扣费极易出现竞态
- 密码、会话、流水、筛选查询都不适合用 JSON 做商业化持久层

结论：不采用。

### 方案 C：外部数据库 + JWT

做法：

- 引入 MySQL/Postgres
- 使用 JWT 或 OAuth 风格鉴权

优点：

- 长期扩展性最好

缺点：

- 对当前仓库是过配
- 运维和改造成本明显高

结论：不作为这次实现方案。

## 最终架构

### 1. 匿名公共面板仍然保留

公开站根路由 `/` 继续提供当前生图工作台。

匿名用户：

- 可以直接访问页面
- 可以继续发起文生图和编辑图
- 扣费走 `public_panel` 公共额度池
- 扣费金额不再固定为 `1`，而是改为 `模型单价 × n`

### 2. 登录用户走个人额度体系

登录用户仍然在同一个公开站 `/` 内操作。

登录后：

- 请求不再走公共额度
- 请求只检查当前用户个人余额
- 当个人余额小于本次请求成本时，接口直接返回额度不足错误
- 不会自动降级到匿名公共额度

### 3. 管理端新增商业化控制面

管理端新增独立页面 `/billing`，承载：

- 模型单价配置
- 激活码批量生成
- 激活码列表与兑换状态查询

这部分不继续塞进当前“设置”卡片区域，避免设置页职责失控。

## 数据模型设计

### 1. 存储方式

新增 `sqlite` 数据文件，推荐路径：

- `data/public_billing.db`

现有：

- `accounts.json` 继续用于号池
- `public_panel.json` 继续用于匿名公共面板开关和匿名额度池

商业化相关状态不写入 JSON。

### 2. 表结构

#### `users`

字段：

- `id`
- `username`
- `password_hash`
- `balance_cents`
- `status`
- `created_at`
- `updated_at`

规则：

- `username` 全局唯一
- `balance_cents` 使用整数保存“分值”，即两位小数定点值
- `status` 初期仅保留 `active` / `disabled`

#### `user_sessions`

字段：

- `id`
- `user_id`
- `token_hash`
- `expires_at`
- `created_at`
- `last_seen_at`

规则：

- 浏览器只保存 session cookie
- 服务端保存 token hash，不保存明文 token

#### `activation_codes`

字段：

- `id`
- `code`
- `amount_cents`
- `batch_note`
- `status`
- `created_at`
- `redeemed_by_user_id`
- `redeemed_at`

规则：

- `code` 唯一
- `status` 为 `unused` 或 `redeemed`
- 一经兑换不得重置回未使用

#### `quota_ledger`

字段：

- `id`
- `scope`
- `user_id`
- `change_cents`
- `balance_after_cents`
- `reason`
- `reference_type`
- `reference_id`
- `created_at`

说明：

- `scope` 取值：`user` 或 `public`
- `reason` 取值示例：`signup_bonus`、`activation_code_redeem`、`image_generate_charge`、`image_edit_charge`
- 所有额度变动都必须落流水

#### `model_pricing`

字段：

- `model`
- `price_cents`
- `enabled`
- `updated_at`

规则：

- 每个模型一条记录
- 当前至少初始化 `gpt-image-1` 和 `gpt-image-2`

## 核心计费设计

### 1. 金额精度

- 外部展示：两位小数
- 内部存储：整数 cents
- 所有输入价格和额度在边界层转换为 cents

禁止使用浮点数直接做扣费与余额比较。

### 2. 模型价格规则

每次请求成本：

- `cost_cents = model_price_cents × n`

其中：

- 生成图按请求中的 `model` 与 `n`
- 编辑图同样按 `model` 与 `n`

### 3. 匿名扣费流程

匿名请求时：

1. 查模型单价
2. 计算成本
3. 从 `public_panel` 额度池预留对应成本
4. 后端生成成功则提交扣费
5. 失败则回滚预留

### 4. 登录用户扣费流程

登录用户请求时：

1. 从 session 识别用户
2. 查模型单价
3. 计算成本
4. 判断用户余额是否足够
5. 成功生成后扣减用户余额并写流水
6. 失败不扣费

登录用户不接触 `public_panel` 匿名额度池。

## 鉴权设计

### 1. 注册

接口：

- `POST /api/public-auth/register`

请求：

- `username`
- `password`

行为：

- 校验用户名唯一
- 密码做哈希
- 新建用户
- 发放初始额度 `1.00`
- 写入 `signup_bonus` 流水
- 创建 session
- 直接登录

### 2. 登录

接口：

- `POST /api/public-auth/login`

请求：

- `username`
- `password`

行为：

- 校验用户名和密码
- 创建 session
- 写入 HttpOnly cookie

### 3. 登出

接口：

- `POST /api/public-auth/logout`

行为：

- 服务端 session 失效
- 清理 cookie

### 4. 当前用户状态

接口：

- `GET /api/public-auth/me`

返回：

- `id`
- `username`
- `balance`
- `status`

## 激活码设计

### 1. 用户兑换

接口：

- `POST /api/public-auth/redeem`

请求：

- `code`

行为：

- 必须登录
- 校验激活码存在且未兑换
- 将额度增加到当前用户余额
- 标记激活码已兑换
- 记录兑换人和兑换时间
- 写 `activation_code_redeem` 流水

该操作必须使用事务，确保“加余额”和“标记已兑换”原子完成。

### 2. 管理端批量生成

接口：

- `POST /api/admin/billing/activation-codes`

请求：

- `count`
- `amount`
- `batch_note`

返回：

- 本次生成的激活码列表

规则：

- 生成 `32` 位无歧义字符串
- 排除容易混淆字符，如 `0/O`、`I/l`
- 支持批量生成

### 3. 管理端列表查询

接口：

- `GET /api/admin/billing/activation-codes`

支持：

- 按 `status` 筛选
- 按 `batch_note` 搜索
- 按兑换用户名搜索

## 前端交互设计

### 1. 公开站

公开站顶部改为双态：

#### 匿名态

- 显示 `登录`
- 显示 `注册`
- 显示匿名额度说明

#### 登录态

- 显示用户名
- 显示个人余额
- 显示“兑换激活码”入口
- 显示退出登录

### 2. 登录页

保留单页 `/login`，改为双标签：

- `登录`
- `注册`

表单字段始终只有：

- `用户名`
- `密码`

注册成功后自动登录并跳回 `/`。

视觉方向：

- 明确是公开产品入口，不再像后台密钥登录页
- 展示产品文案、模型支持和额度/激活码说明

### 3. 登录用户在公开站的操作

登录后在 `/` 页增加：

- 当前余额展示
- 激活码兑换输入框或弹层
- 额度不足时的明确提示

### 4. 管理端 `/billing`

页面拆成两个区域：

#### 模型价格区

- 模型名称
- 当前单价
- 启用状态
- 更新时间

#### 激活码管理区

- 批量生成器
- 本次生成结果
- 激活码列表
- 状态筛选
- 批次筛选
- 用户搜索

## 后端接口边界

### 公开接口

- `POST /api/public-auth/register`
- `POST /api/public-auth/login`
- `POST /api/public-auth/logout`
- `GET /api/public-auth/me`
- `POST /api/public-auth/redeem`
- `GET /api/public-panel/status`
- `POST /api/public-panel/images/generations`
- `POST /api/public-panel/images/edits`

### 管理接口

- `GET /api/admin/billing/model-pricing`
- `POST /api/admin/billing/model-pricing`
- `GET /api/admin/billing/activation-codes`
- `POST /api/admin/billing/activation-codes`

管理员接口继续沿用现有后台鉴权方式。

## 错误处理

需要明确暴露以下错误：

- `用户名已存在`
- `用户名或密码错误`
- `会话失效，请重新登录`
- `激活码不存在`
- `激活码已被兑换`
- `个人额度不足`
- `匿名公共额度不足`
- `模型未启用或价格未配置`

禁止静默回退：

- 登录用户额度不足时不能偷偷改扣匿名额度
- 激活码重复兑换时不能返回伪成功
- 模型未配置价格时不能按默认 `1` 扣费

## 测试策略

### 1. 后端单元测试

覆盖：

- 注册成功并发放初始额度
- 重复用户名注册失败
- 登录成功与密码错误失败
- 激活码单次兑换成功
- 激活码重复兑换失败
- 模型价格按 `price × n` 计算
- 登录用户只扣个人额度
- 匿名用户只扣公共额度
- 登录用户额度不足不回退匿名额度

### 2. API 测试

覆盖：

- `register/login/logout/me`
- `redeem`
- 管理端批量生成激活码
- 管理端设置模型价格
- 匿名与登录用户绘图扣费路径差异

### 3. 前端验证

覆盖：

- 登录/注册页切换
- 登录后余额刷新
- 兑换成功后余额变化
- 额度不足提示
- 管理端价格保存与激活码生成

## 当前落地情况（2026-04-23）

本设计对应的 MVP 已在 `feat/public-studio-user-auth` 工作树落地，当前实现与设计对齐点如下：

- 已提供 `POST /api/public-auth/register`、`login`、`logout`、`redeem` 与 `GET /api/public-auth/me`，登录态使用服务端 session cookie
- 注册成功后固定发放 `1.00` 初始额度，并写入 `signup_bonus` 流水
- 匿名用户继续扣 `public_panel` 公共额度；登录用户只扣个人余额，额度不足时直接报错，不回退到匿名公共额度
- 管理端已提供 `/api/admin/billing/model-pricing` 与 `/api/admin/billing/activation-codes` 两组接口，支持模型价格维护、激活码批量生成和按状态/批次/兑换用户名筛选
- 公开站 `/login` 已改为注册/登录双标签页，首页已展示个人余额与激活码兑换入口
- 管理端 `/billing` 已落地为独立页面，并只在 `admin` 变体中暴露；`studio` 变体访问该路由会返回 `notFound`

本次 Task 10 验证结果：

- 后端回归：`UV_CACHE_DIR=.uv-cache uv run --with pytest --with httpx python -m pytest test/test_public_billing_store.py test/test_public_money.py test/test_public_auth_service.py test/test_public_auth_api.py test/test_public_activation_codes.py test/test_admin_billing_api.py test/test_image_workflow_service.py test/test_public_panel_api.py test/test_chat_completions_api.py -q`
- 结果：`81 passed in 1.84s`
- 前端构建：`npm run build`
- 结果：`build:admin` 与 `build:studio` 均通过，静态路由包含 `/billing`

## 不在本次范围

这次不做：

- 邮箱注册
- 手机验证码
- 忘记密码
- 用户资料页
- 用户管理大盘
- 多币种或真实货币支付
- 激活码撤销与退款

## 最终建议

本次实现应坚持两个边界：

- 匿名公共额度和登录用户个人额度必须彻底分开
- 所有价格、充值、扣费都必须可追踪、可审计

用 `SQLite + 服务端会话 + 两位小数定点计费`，可以在不引入外部基础设施的前提下，把这套公开生图站升级到可售卖、可控账、可继续扩展的商业化基础版本。
