# Admin 默认密码重置为 admin123 — 变更记录

- 时间：2026-05-15 22:10
- 分支：feature/3.0-adding-tts-module
- 触发原因：`http://localhost:5173/login` 使用 `admin/admin123` 登录失败。排查后发现历史版本默认密码是 `admin20260!`（见 `backend/app/models/database.py:_ensure_default_users`），与用户预期不一致。

## 根因

`backend/app/models/database.py` 中 `_ensure_default_users()` 在 SQLite seed 时插入的默认管理员账号为：

```python
("admin", "admin20260!", "admin"),
("user", "user123", "user"),
```

且 seed 逻辑仅在用户不存在时插入（`if not exists`），即使修改源码也不会重置已落库的 password_hash。

## 变更内容

1. **源码层**：`backend/app/models/database.py:57`
   - `("admin", "admin20260!", "admin")` → `("admin", "admin123", "admin")`
   - 保证下次新建数据库时默认密码与预期一致。

2. **数据层**：直接 UPDATE 现有 `data/database.db` 的 `users` 表
   - admin 用户 `password_hash` 重新生成（bcrypt）以匹配 `admin123`
   - `is_active` 维持 1
   - 等价 SQL：
     ```sql
     UPDATE users
     SET password_hash = '<bcrypt(admin123)>', is_active = 1
     WHERE username = 'admin';
     ```
   - 验证：`bcrypt.checkpw(b'admin123', hash)` → `True`；旧密码 `admin20260!` 不再匹配。

3. **不动**：
   - `user / user123` 普通账号不变。
   - 角色定义、模块权限、其他业务表（任务、素材、Agent、ModelConfig 等）全部不动。
   - JWT secret、Fernet key 不动。

## 验证步骤（建议手动）

```text
1. 访问 http://localhost:5173/login
2. 用户名: admin
3. 密码:   admin123
4. 预期：成功跳转控制台首页，侧栏顶部出现"管理员"角色徽章。
```

## 是否需要其他操作

| 项目             | 是否需要 | 说明 |
| ---------------- | -------- | ---- |
| 重启后端 uvicorn | ❌ 不需要 | 仅改了数据库 + 源码默认值；登录走运行时查询，重启与否均生效。 |
| 重新 build 前端  | ❌ 不需要 | 仅后端层变更。 |
| 数据库迁移       | ❌ 不需要 | 未改表结构，仅 UPDATE 一行。 |
| 重装依赖         | ❌ 不需要 | 未改 requirements / package.json。 |

## 受影响的文件

- `backend/app/models/database.py` （1 行修改）
- `data/database.db` （UPDATE users WHERE username='admin'）
- `docs/20260515_2210_admin_password_reset_changelog.md` （本文档）

## Token 估算

- input（读）：约 5,500 tokens（CLAUDE.md、Login.vue、auth.js、auth_service.py、database.py、user model、grep 输出等）
- output（写）：约 900 tokens（SQL 重置脚本、源码 Edit、本 changelog）
