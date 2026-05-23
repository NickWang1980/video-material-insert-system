# vendor/heygem inline 改造 + py39 本地化 — Changelog

**日期**：2026-05-22
**目标**：项目根目录达到 copy-one-folder 可迁移（拷一个文件夹到新机器即可跑起来），消除对 `D:\workspace\bzybox\v-project\heygem_win_no_docker_50_v2\` 的所有运行时依赖。

---

## 背景

迁移前主仓存在 2 层外部依赖：

1. **submodule 远端 404**：`vendor/heygem` 是 git submodule，URL 指向 `https://github.com/NickWang1980/heygem-vmis-sidecar.git`，但该仓库从未在 GitHub 创建。submodule 改动无法 push、双仓库管理增加 clone 复杂度。
2. **start_api.bat 硬编码 fallback**：`vendor/heygem/start_api.bat` 第 20 行写死 `D:\workspace\bzybox\v-project\heygem_win_no_docker_50_v2\py39\python.exe` 作为兜底路径。本机能跑全靠这条 fallback；submodule 本身不含 py39（12.25 GB 太大不进 git）。

---

## 三个动作

### 1. py39 物理化到项目内

```powershell
robocopy `
  "D:\workspace\bzybox\v-project\heygem_win_no_docker_50_v2\py39" `
  "D:\workspace\bzybox\v-project\video-material-insert-system\feature\3.0-adding-tts-module\vendor\heygem\py39" `
  /E /MT:16 /R:1 /W:1 /NFL /NDL /NP
```

实际数据：8355 目录、64197 文件、12.247 GB、用时 2 分 6 秒（SSD）、0 失败。原 heygem 目录保留不动。

### 2. start_api.bat 删除硬编码 fallback

由 3 策略（local / env / 硬编码）改为 2 策略（local / env），错误提示文本同步更新为引导用户用 `robocopy` 或 `HEYGEM_PY39_DIR`。

### 3. 干掉 submodule，inline 进主仓

- `git rm --cached vendor/heygem`（删 gitlink，留工作树文件）
- 删 `.gitmodules` + `.git/config` 的 `[submodule "vendor/heygem"]` 节
- 删 `vendor/heygem/.git` (41 字节 gitlink 指针文件)
- 备份 `.git/modules/vendor/heygem` → `.git/modules/vendor/heygem.bak`（保留可回滚，验证 OK 后可删）
- `git add vendor/heygem` 把 104 个文件作为普通 tracked 文件入库

#### 配套的 master .gitignore 放宽

发现 inline 后有 3 条 master 规则误伤 heygem 源代码：

| 原规则 | 误伤范围 | 改法 |
|---|---|---|
| `*.pyc` | heygem 用 .pyc 反编译形式发布的~50 个核心模块 | 加 `!vendor/heygem/**/*.pyc` 例外 |
| `data/` | `vendor/heygem/landmark2face_wy/data/*.py`（5 个数据集源文件） | 加 `/` 前缀 → `/data/`（只匹配根级） |
| `tools/` | `vendor/heygem/wenet/tools/_extract_feats.py` | 加 `/` 前缀 → `/tools/` |

`.gitignore` 改完 inline 文件数从 50 + 升到 104（与原 submodule tracked 文件数完全等价）。

---

## 改动的文件清单

| 文件 | 改动 | 备注 |
|---|---|---|
| `vendor/heygem/start_api.bat` | 修改 | 删除外部硬编码 fallback；2 策略错误提示文案重写 |
| `vendor/heygem/py39/` (整目录) | 新增 | 12.25 GB，已被 `vendor/heygem/.gitignore` 屏蔽不进 git |
| `.gitmodules` | 删除 | 整个文件删除（原本只有 vendor/heygem 一项） |
| `.git/config` | 修改 | 删除 `[submodule "vendor/heygem"]` 节 |
| `vendor/heygem/.git` | 删除 | gitlink 指针文件 |
| `.git/modules/vendor/heygem` | 重命名为 `.bak` | 保留作回滚备份 |
| `vendor/heygem/*` (104 文件) | 新增到主仓 index | 从 submodule 转为 inline 跟踪 |
| `.gitignore` | 修改 | `data/` → `/data/`；`tools/` → `/tools/`；新增 `!vendor/heygem/**/*.pyc` |
| `CLAUDE.md` | 修改 | 第 9 节 + Change Video Gen behavior 段：submodule 表述改为 inline |

---

## Commits

| SHA | 类型 | 说明 |
|---|---|---|
| `d917ad6` | inline 主体 | 106 文件 / +5791 -5 行 |
| `c278fd1` | cleanup | 补 stage `.gitmodules` 的删除（前一个 commit 漏掉的） |
| `<待加>` | docs | CLAUDE.md 第 9 节 / Change Video Gen 段更新 + 本 changelog |

---

## 验证

**当前机器自检**（用户跑）：

```powershell
# 1. py39 已就位
Test-Path "vendor\heygem\py39\python.exe"            # True
& "vendor\heygem\py39\python.exe" --version          # Python 3.10.16

# 2. submodule 痕迹清理
Test-Path .gitmodules                                # False
git submodule status                                 # 空输出

# 3. inline 文件树完整
git ls-files vendor/heygem | Measure-Object          # ~104

# 4. heygem sidecar 用本地 py39 启动
Get-Process python -ErrorAction SilentlyContinue | `
  Where-Object { $_.Path -like "*heygem_win_no_docker_50_v2*" } | `
  Stop-Process -Force                                # 杀掉外部 heygem 进程（如有）
cmd /c "vendor\heygem\start_api.bat"                 # 日志含 "using py39 from: ...\vendor\heygem\py39"

# 5. 健康检查
Invoke-RestMethod http://127.0.0.1:8383/health       # { ready: true, gpu: {...} }

# 6.（试探）临时改名外部 heygem 目录，再启 sidecar
Rename-Item "D:\workspace\bzybox\v-project\heygem_win_no_docker_50_v2" `
            "heygem_win_no_docker_50_v2_BAK"
# 重启 sidecar，仍能跑 = 真的脱钩了
Rename-Item "D:\workspace\bzybox\v-project\heygem_win_no_docker_50_v2_BAK" `
            "heygem_win_no_docker_50_v2"             # 验证完改回去
```

**端到端**：master 前端 `/video-gen` 提交一次音频+视频合成任务，能完成。

---

## 未来在新机器上的迁移流程

1. 把 `D:\workspace\bzybox\v-project\video-material-insert-system\feature\3.0-adding-tts-module\` 整个文件夹拷到新机
2. 装系统级 Python 3.11+ / Node 18+（不需要特定路径）
3. 跑 `scripts\start_all.bat --with-heygem`
4. 首次启动会：pip install backend deps → npm install frontend deps → heygem sidecar 用本地 `vendor/heygem/py39/python.exe` 起来 → master 起在 :8000、前端 :5173
5. 首次合成任务会触发 Qwen3-TTS / Whisper 权重下载（~2-5 GB，按需 lazy load，可走 hf-mirror.com）

**注意**：如果是从 GitHub `git clone` 而非"拷文件夹"，py39（12.25 GB，gitignored）不会被带过来。需要：
- 从已有便携 Python 安装 robocopy 一份进 `vendor/heygem/py39/`，或
- 设 `HEYGEM_PY39_DIR` 环境变量指向已存在的便携 py39 目录

---

## Token 估算（本轮）

- Input (读取 / Grep / Read): ~120k tokens（含完整 audit + 现有文件读取）
- Output (Write / Edit / Bash commands / commit msgs): ~16k tokens

---

## 回滚方案

如发现 inline 后 heygem 跑不起来，回滚步骤：

```bash
# 1. 回退两个 inline 相关 commit
git reset --hard 06d7f85   # 回到 inline 之前最后一个 commit

# 2. 恢复 submodule
mkdir -p vendor/heygem/.git
mv .git/modules/vendor/heygem.bak .git/modules/vendor/heygem
echo "gitdir: ../../.git/modules/vendor/heygem" > vendor/heygem/.git
git submodule init
git submodule update --init vendor/heygem

# 3. py39 不用动（仍在 vendor/heygem/py39/）
```

`.git/modules/vendor/heygem.bak` 验证一切正常后可删（保留约半个月做缓冲期）。

---

## 后续可选清理（本计划范围外）

- `.claude/settings.local.json:51` 仍引用 `heygem_win_no_docker_50_v2`（仅 IDE 设置，不影响运行）
- `docs/20260517_0307_video_gen_phase1_plan.md` / `docs/20260517_0411_video_gen_phase1_changelog.md` 历史文档中有路径与 submodule 引用（仅历史记录，不改）
