# Codex 实施说明：新增“多角色混剪”功能（高可用 UI/UX 版）

## 1. 目标

在现有“视频剪辑自动化”项目中，新增一个**可以直接产出混剪 MP4** 的功能。

用户输入：
- 一段文案
- 多个角色视频素材（A / B / C，可各自上传多个视频）
- 可选角色顺序规则（例如 `A+B+A+C+A`）

系统输出：
- 自动按文案拆句
- 将每句分配给对应角色
- 从该角色素材池中自动截取合适片段
- 按时间线拼接为一条**多角色混剪视频**
- 输出 `mp4`

示例结果：
- 文案共 5 句
- 角色顺序为 `A+B+A+C+A`
- 输出成片顺序即：A 讲第 1 句，B 讲第 2 句，A 讲第 3 句，C 讲第 4 句，A 讲第 5 句

---

## 2. 设计目标（必须满足）

### 2.1 核心目标
1. **最少输入即可生成结果**
   - 默认只要求：文案 + 素材。
   - 角色顺序、句长、时长估算、字幕、音频策略都要有默认值。

2. **第一次使用也能马上上手**
   - 不要做成复杂专业 NLE（非编）界面。
   - 默认走“一键混剪”路径。
   - 进阶能力放到“高级设置”里。

3. **让用户对生成过程可见、可改、可重试**
   - 用户必须能看到：
     - 文案被拆成了哪些句子
     - 每句分配给了哪个角色
     - 每句选用了哪个素材片段
   - 用户必须可以快速改：
     - 改某句角色
     - 改某句时长
     - 锁定某句不重算
     - 只重生成某一句或从某句开始重生成

4. **混剪优先，精剪后置**
   - 第一版不追求复杂转场、表情识别、自动找口型最优点。
   - 先做“稳定输出可用混剪”的能力。

---

## 3. UI/UX 总原则

### 3.1 默认路径必须极短
首页/功能入口后，用户最好只需要 3 步：
1. 粘贴文案
2. 上传角色素材
3. 点击“一键混剪”

### 3.2 单屏完成主流程
主界面尽量为**一个工作台页面**，而不是来回切换多个页面。

推荐布局：
- **左侧：文案与句子列表**
- **中间：视频预览 + 时间线**
- **右侧：角色规则 / 参数 / 导出**

这样用户能在一个视图里理解全流程。

### 3.3 先给结果，再给设置
默认先显示：
- 自动拆句结果
- 自动分配角色结果
- 一键生成按钮

不要一开始弹出一堆参数。

### 3.4 所有关键动作都要“可撤回、可重试”
必须支持：
- 重新拆句
- 重新分配角色
- 重新选片
- 重新生成整条视频
- 仅重生成某一条句子片段

### 3.5 明确状态反馈
每一步都要有状态：
- 未开始
- 处理中
- 成功
- 失败
- 可重试

不能让用户不知道系统卡在哪。

---

## 4. 推荐交互方案（按这个做）

## 4.1 页面结构

### 页面标题
`多角色混剪`

### 顶部区域
- 标题：`多角色混剪`
- 副标题：`输入文案和多个角色素材，自动生成混剪口播视频`
- 右上角主按钮：`一键混剪`
- 次按钮：`重新生成`
- 次按钮：`导出 MP4`

### 主体三栏布局

#### 左栏：文案区（宽约 28%）
模块：
1. 文案输入框
2. “自动拆句”按钮
3. 句子列表

句子卡片字段：
- 句子序号
- 句子文本
- 预计时长
- 角色标签（A/B/C）
- 锁定开关
- 单句操作菜单
  - 改角色
  - 改时长
  - 重新选片
  - 预览本句

#### 中栏：预览区（宽约 44%）
模块：
1. 视频播放器
2. 当前句信息浮层
   - 当前句文本
   - 当前角色
   - 当前素材文件名
   - 当前时间段
3. 简化时间线
   - 每个片段一个彩色块
   - 色块按角色区分
   - Hover 显示句子/角色/时长/来源素材
   - 点击时间线块，高亮对应左栏句子卡片

#### 右栏：设置区（宽约 28%）
分成 3 个折叠面板：

1. **角色规则**
   - 模式：
     - 自动轮播
     - 主角色优先
     - 指定序列
   - 指定序列输入框：`A+B+A+C+A`
   - 主角色选择：A / B / C

2. **生成参数**
   - 输出比例：9:16 / 16:9 / 1:1
   - 分辨率：720p / 1080p
   - 帧率：25 / 30
   - 音频策略：保留原音 / 静音 / 后续 TTS 占位
   - 字幕：关闭 / SRT / 烧录
   - 转场：无 / 淡入淡出（默认无）

3. **导出与日志**
   - 生成进度条
   - 处理日志（可折叠）
   - 导出文件路径/下载按钮

---

## 5. 默认行为（非常重要）

若用户什么都不设置，系统必须这样工作：

### 5.1 默认拆句
按以下优先级拆句：
1. 换行
2. `。！？；`
3. `，、`
4. 句子过长时按字数二次拆分

默认单句建议长度：
- 8～24 个中文字符

### 5.2 默认角色分配
如果用户没有指定序列：
- 若只有 1 个角色：一直使用该角色
- 若有 2 个角色：`A+B+A+B...`
- 若有 3 个角色：默认使用 **主角色优先策略**
  - 默认主角色为 A
  - 循环模式：`A+B+A+C+A+B+A+C...`

### 5.3 默认时长估算
按文本长度估算：
- `duration = clamp(len(text) / 4.5, 1.2, 5.0)`
- 单位：秒

### 5.4 默认选片规则
同一角色下维护独立游标：
- 每次从该角色素材池中按时间顺序截取下一段
- 当前视频剩余长度不足时，自动切换到下一个素材
- 所有素材用完时：
  - 默认回环使用
  - UI 中提示“素材已循环使用”

### 5.5 默认输出
- 输出格式：`mp4`
- 编码：`H.264 + AAC`
- 默认比例：`9:16`
- 默认分辨率：`1080x1920`
- 默认帧率：`30fps`

---

## 6. 关键用户流程

## 6.1 最短路径流程
1. 用户进入页面
2. 粘贴文案
3. 上传 A/B/C 角色素材
4. 系统自动识别角色分组（允许用户手动改）
5. 系统自动拆句
6. 系统自动分配角色
7. 用户点击 `一键混剪`
8. 系统生成混剪时间线并渲染预览
9. 用户点击 `导出 MP4`

## 6.2 微调流程
1. 用户点击某一句
2. 修改角色或时长
3. 点击 `仅重生成本句`
4. 时间线局部更新
5. 保留其它句子的结果不变

## 6.3 重生成流程
1. 用户修改序列为 `A+B+A+C+A`
2. 点击 `重新分配角色`
3. 系统只重算角色与选片，不重拆句
4. 用户点击 `重新生成视频`

---

## 7. 页面细节要求（提升好用度）

## 7.1 素材导入体验
素材区要支持：
- 拖拽上传
- 点击上传
- 批量上传
- 按角色分组展示

每个素材卡片展示：
- 缩略图
- 文件名
- 时长
- 分辨率
- 角色归属
- 删除按钮

如果系统无法自动识别角色，默认全部归到“未分组”，并提示用户一键指定为 A/B/C。

## 7.2 句子列表体验
每句都必须是一个独立卡片，卡片内容：
- `01`
- 句子文本
- `角色: A`
- `时长: 2.3s`
- `素材: a1.mp4 00:02.2-00:04.5`
- 锁定按钮
- 更多操作按钮

交互：
- 点击卡片 => 播放器跳到对应片段
- 拖动卡片 => 调整句子顺序
- 修改顺序后可选择是否同步更新时间线

## 7.3 低干扰但清晰的视觉设计
视觉上不要花哨，遵循：
- 明确层级
- 高信息密度但不拥挤
- 重点按钮突出
- 文本可读性优先

建议：
- 整体偏深灰/浅灰中性界面
- 角色颜色固定：
  - A：蓝
  - B：紫
  - C：橙
- 危险操作使用红色
- 主 CTA 统一一个高强调色

## 7.4 空状态要设计完整
空状态文案示例：
- 文案为空：`请先粘贴文案，我们会自动帮你拆成镜头句子。`
- 素材为空：`请上传至少一个角色素材后再生成。`
- 尚未生成：`你还没有生成混剪，点击“一键混剪”开始。`

## 7.5 错误提示必须具体
不要只写“生成失败”。
要写成：
- `角色 B 没有可用素材，无法为第 4 句选片。`
- `第 7 句估算时长为 6.8s，超过当前限制，请缩短句子或手动调整。`
- `导出失败：FFmpeg 返回非 0 状态码。`

---

## 8. 前端功能需求

## 8.1 必做功能
1. 文案输入与自动拆句
2. 素材上传与角色分组
3. 角色策略设置
4. 句子列表展示
5. 单句角色修改
6. 单句时长修改
7. 单句锁定
8. 简化时间线展示
9. 预览播放器
10. 一键混剪
11. 重新生成
12. 导出 MP4
13. 处理日志展示

## 8.2 可选增强（先预留接口）
1. 自动字幕
2. TTS 配音
3. BGM
4. 自动封面
5. 智能去重（避免相邻镜头视觉太像）
6. 智能口型/人脸活跃度选片

---

## 9. 后端处理流程

建议新增一条明确的 pipeline：

1. `normalize_script`
2. `split_script`
3. `assign_roles`
4. `estimate_durations`
5. `select_clips`
6. `build_timeline`
7. `render_preview`
8. `export_mp4`

---

## 10. 数据结构建议

## 10.1 Project
```ts
interface RoughCutProject {
  id: string;
  title: string;
  script: string;
  sentences: SentenceItem[];
  roles: RoleConfig[];
  assets: RoleAsset[];
  settings: RenderSettings;
  timeline: TimelineClip[];
  status: 'idle' | 'processing' | 'ready' | 'error';
  outputUrl?: string;
  createdAt: string;
  updatedAt: string;
}
```

## 10.2 Sentence
```ts
interface SentenceItem {
  id: string;
  index: number;
  text: string;
  roleId?: string;
  estimatedDuration: number;
  locked: boolean;
  clipId?: string;
}
```

## 10.3 Role
```ts
interface RoleConfig {
  id: 'A' | 'B' | 'C' | string;
  name: string;
  color: string;
  isPrimary?: boolean;
}
```

## 10.4 Asset
```ts
interface RoleAsset {
  id: string;
  roleId: string;
  fileName: string;
  filePath: string;
  duration: number;
  width: number;
  height: number;
}
```

## 10.5 Timeline Clip
```ts
interface TimelineClip {
  id: string;
  sentenceId: string;
  roleId: string;
  assetId: string;
  filePath: string;
  sourceStart: number;
  sourceEnd: number;
  duration: number;
  timelineStart: number;
  timelineEnd: number;
  subtitleText: string;
}
```

## 10.6 Render Settings
```ts
interface RenderSettings {
  aspectRatio: '9:16' | '16:9' | '1:1';
  resolution: '720p' | '1080p';
  fps: 25 | 30;
  audioMode: 'keep' | 'mute' | 'tts';
  subtitleMode: 'off' | 'srt' | 'burn';
  transitionMode: 'none' | 'fade';
  roleStrategy: 'auto' | 'primary-first' | 'manual-sequence';
  manualSequence?: string; // e.g. A+B+A+C+A
}
```

---

## 11. 角色分配规则

实现一个独立函数：

```ts
function assignRoles(
  sentences: SentenceItem[],
  roles: RoleConfig[],
  strategy: 'auto' | 'primary-first' | 'manual-sequence',
  manualSequence?: string
): SentenceItem[]
```

### manual-sequence
- 解析 `A+B+A+C+A`
- 转换为数组：`['A','B','A','C','A']`
- 文案句数超过序列长度时，循环使用该模式

### primary-first
- 若角色数量 >= 3，默认：`A+B+A+C` 循环

### auto
- 按现有角色顺序平均轮播

---

## 12. 选片规则

实现一个独立的 clip selector，按角色维护游标：

```ts
interface RoleCursor {
  roleId: string;
  assetIndex: number;
  offset: number;
}
```

### 规则
1. 每个角色独立维护 `assetIndex + offset`
2. 需要片段时，先从当前 asset 当前 offset 往后截取
3. 若当前 asset 不够，则切到下一个 asset
4. 若角色素材池全部用完，则：
   - 默认从第一个素材重新开始
   - 增加标记 `looped: true`
5. 输出 clip 时要写清来源，供 UI 展示

---

## 13. 渲染方案

## 13.1 第一版建议
第一版使用 FFmpeg 即可，不依赖复杂视频引擎。

### 流程
1. 为每个 timeline clip 切出临时片段
2. 对所有片段做统一 scale / fps / sar 处理
3. 生成 concat 列表
4. 拼接为预览视频
5. 导出正式 MP4

### 片段裁剪示例
```bash
ffmpeg -y -ss 2.2 -to 4.5 -i a1.mp4 -vf "scale=1080:1920,fps=30" -c:v libx264 -c:a aac clip_001.mp4
```

### concat 列表示例
```txt
file 'clip_001.mp4'
file 'clip_002.mp4'
file 'clip_003.mp4'
```

### 拼接示例
```bash
ffmpeg -y -f concat -safe 0 -i concat.txt -c:v libx264 -c:a aac output.mp4
```

---

## 14. API/服务层建议

如果当前项目已有后端 API，请新增以下能力；如果当前项目是本地型桌面/Node 工具，则映射成 service 方法。

## 14.1 建议接口

### 1）创建项目
`POST /api/rough-cut/projects`

### 2）上传素材
`POST /api/rough-cut/projects/:id/assets`

### 3）拆句
`POST /api/rough-cut/projects/:id/split-script`

### 4）分配角色
`POST /api/rough-cut/projects/:id/assign-roles`

### 5）生成时间线
`POST /api/rough-cut/projects/:id/build-timeline`

### 6）单句重生成
`POST /api/rough-cut/projects/:id/regenerate-sentence/:sentenceId`

### 7）导出视频
`POST /api/rough-cut/projects/:id/export`

### 8）获取任务状态
`GET /api/rough-cut/projects/:id/status`

---

## 15. 前端组件建议

请优先复用现有 UI 框架与设计系统，不要另起一套风格。

建议新增组件：
- `RoughCutPage`
- `ScriptInputPanel`
- `SentenceListPanel`
- `SentenceCard`
- `RoleStrategyPanel`
- `AssetLibraryPanel`
- `PreviewPlayer`
- `TimelineStrip`
- `RenderProgressPanel`
- `ExportPanel`

如果项目使用 React，建议页面结构：

```tsx
<RoughCutPage>
  <TopBar />
  <MainLayout>
    <LeftPane>
      <ScriptInputPanel />
      <SentenceListPanel />
    </LeftPane>
    <CenterPane>
      <PreviewPlayer />
      <TimelineStrip />
    </CenterPane>
    <RightPane>
      <RoleStrategyPanel />
      <AssetLibraryPanel />
      <RenderProgressPanel />
      <ExportPanel />
    </RightPane>
  </MainLayout>
</RoughCutPage>
```

---

## 16. 状态管理要求

必须支持以下状态：

```ts
interface RoughCutUIState {
  selectedSentenceId?: string;
  isSplitting: boolean;
  isAssigningRoles: boolean;
  isBuildingTimeline: boolean;
  isRenderingPreview: boolean;
  isExporting: boolean;
  error?: string;
}
```

要求：
- 所有异步动作必须可显示 loading
- 所有失败必须可重试
- 句子级重生成要有局部 loading，不能卡死整个页面

---

## 17. 性能要求

1. 句子数 30 以内时，前端交互要流畅
2. 单次混剪预览生成应优先走低成本预览渲染
3. 正式导出可与预览分开
4. 日志流式回显，避免用户误以为卡死
5. 大文件上传要有进度条

---

## 18. 验收标准（必须逐条满足）

## 18.1 基础验收
- [ ] 用户只输入文案并上传 A/B/C 素材后，可以完成一键混剪
- [ ] 文案能被自动拆成多个句子
- [ ] 每句都能分配到角色
- [ ] 每句都能自动选出素材片段
- [ ] 能生成预览视频
- [ ] 能导出 MP4

## 18.2 UI/UX 验收
- [ ] 页面主流程在一个工作台内完成
- [ ] 用户可一眼看出“文案 -> 角色 -> 片段 -> 时间线 -> 导出”的链路
- [ ] 单句支持改单角色
- [ ] 单句支持改单时长
- [ ] 单句支持局部重生成
- [ ] 所有失败状态都有具体错误提示

## 18.3 结果可用性验收
- [ ] 当用户指定 `A+B+A+C+A` 时，生成结果按该模式分配
- [ ] 当素材不足时，系统能给出明确提示或自动循环复用
- [ ] 生成的片段顺序和句子顺序一致
- [ ] 导出的视频可正常播放

---

## 19. 实施优先级

## P0（本次必须完成）
1. 页面入口
2. 文案输入
3. 自动拆句
4. 素材上传
5. 角色分组
6. 默认角色分配
7. 手动指定序列
8. 自动选片
9. 时间线展示
10. 预览生成
11. 导出 MP4
12. 错误提示
13. 单句局部重生成

## P1（下一轮）
1. 自动字幕
2. 烧录字幕
3. 淡入淡出转场
4. 主角色权重更细化
5. 素材智能去重

## P2（后续增强）
1. TTS
2. 智能找表情更合适的片段
3. 自动 BGM
4. AI 镜头节奏优化

---

## 20. 对 Codex 的明确执行要求

请直接在当前项目中新增“多角色混剪”能力，并遵守以下要求：

1. **优先保证主路径可用**，不要先陷入高级特效。
2. **优先做 UI 工作台**，让用户可以在一个页面完成输入、检查、生成、导出。
3. **默认行为必须完整**，用户不配置高级参数也能生成结果。
4. **所有重要数据都要可视化**：句子、角色、素材来源、时间线、导出状态。
5. **代码结构清晰**：把拆句、分角、选片、渲染拆成独立模块。
6. **尽量复用项目现有组件/样式/状态管理/任务系统**。
7. **不要破坏现有功能**，新增能力应以独立页面/模块接入。
8. **如果已有路由系统**，新增独立路由，例如：`/rough-cut/multi-role`
9. **如果已有任务队列或 FFmpeg 服务封装**，优先复用。
10. **提交时附带 README / 使用说明 / 关键截图占位说明**。

---

## 21. 建议的开发顺序

### 第 1 步
先完成静态 UI：
- 三栏布局
- 文案输入
- 素材区
- 句子列表
- 时间线占位
- 导出区

### 第 2 步
接入脚本拆句与角色分配

### 第 3 步
接入素材选择与时间线生成

### 第 4 步
接入 FFmpeg 预览渲染与导出

### 第 5 步
补充局部重生成、错误提示、日志面板

---

## 22. 最终效果预期

用户进入该功能后，体验应该是：

> 我只需要贴一段文案、上传几个角色素材，系统就帮我自动拆句、自动分配角色、自动拼出一个 A+B+A+C+A 风格的多角色混剪视频；如果某一句不满意，我只改单句，不用整条重来。

这就是本功能要达到的核心体验。
