# 个性化学习资源生成 v2

前端与 Flutter 对接请参阅 [`frontend-resource-generation-v2.md`](frontend-resource-generation-v2.md)。

## 统一异步入口

`POST /api/resources/generate` 接受单一 `resource_type` 和 `generation_scope`，立即返回
`task_id` 与 `queued`。旧版 `knowledge_point / goal / resource_types` 请求仍可使用。

```json
{
  "course_id": "course_ml",
  "chapter_id": "chapter_tree",
  "section_id": "section_entropy",
  "knowledge_point_ids": ["kp_entropy", "kp_gain"],
  "resource_type": "ppt",
  "user_request": "生成适合初学者的图解型互动课件",
  "generation_scope": "section"
}
```

轮询 `GET /api/agent-tasks/{task_id}`。状态与 LangGraph 节点同步，包括 `queued`、
`loading_profile`、`loading_course`、`retrieving`、`planning`、`searching_external`、
`generating_content`、`rendering_html`、`checking_html`、`reviewing`、`saving`、
`completed`、`failed` 和 `no_suitable_result`。

旧小节资源壳子仍保持 illustration/code_case/exercise/mind_map 的字段与顺序，避免破坏已上线
Flutter 页面。新页面要生成 document/video/ppt 时调用统一异步入口，不调用旧同步壳子接口。

## HTML 互动课件

课件流程为：课程结构与分层检索 → Pydantic 需求 → Pydantic 大纲 → Pydantic 页面内容 →
本地模板选择 → 固定后端模板渲染 → 安全/布局检查 → `index.html` → `cover.png`。

大模型内容永远不会作为可执行 HTML 或 JavaScript 保存。后端对所有内容进行 HTML escaping；
固定模板禁止 iframe、object/embed、表单、外部脚本和网络请求，使用 CSP `connect-src 'none'`。
舞台固定 1920×1080，视口只等比例缩放，不发生移动端重排；图片固定 `object-fit: contain`。

上游 Frontend Slides 的选定文件位于 `app/third_party/frontend_slides/`。运行时先读取
`bold-template-pack/selection-index.json`，再只读取被选中的 `design.md`。业务渲染代码位于
`app/agents/resource_generation/ppt/`，不修改 vendor 文件。许可证见
`app/third_party/frontend_slides/LICENSE`，本项目说明见同目录 `NOTICE.md`。

Flutter 流程：

1. 从资源详情读取 `content_json.visualization.renderer`；值为 `frontend_slides_html` 时使用 WebView。
2. 调用 `GET /api/resources/{resource_id}/html-entry` 获取短期 `html_url`、`cover_url` 和 `expires_at`。
3. WebView 横屏全屏打开 `html_url`；过期后重新调用 html-entry，不在 query 中携带长期 JWT。
4. 保持 JavaScript 开启以支持固定模板的键盘、滚轮和滑动翻页；不要把课件当作 PPTX 或图片列表。

## Bilibili 公开视频

video 默认模式为 `external_video`。模块只调用公开搜索元数据接口，保存 BV 号、标题、作者、简介、
时长、封面和原始播放页 URL。不会下载视频、获取流地址、解析 DASH/m3u8、使用 Cookie、绕过登录/
验证码/风控或重新上传内容。平台拒绝请求时停止继续请求，使用缓存或返回 `no_suitable_result`。

Provider → 缓存/限流/超时/有限重试 → BV 去重 → 规则校验 → 加权排序 → 候选防篡改 →
VideoReviewer。LLM 若后续参与重排，只能返回候选 BV 号；服务会从 Provider 原对象重新取回不可变元数据。
默认测试使用 Mock Provider，不依赖真实 Bilibili 网络。

Flutter 应打开 `content_json.visualization.video_url` 的公开页面；该 URL 不是 MP4，不应交给原生
`video_player`。

## 课程关系导图

mind_map 会加载整门课程目录，但只分层检索有限的当前节、当前章和跨章知识块，不把整本教材全文放入
单个 Prompt。`current_chapter_tree`、`intra_chapter_relations`、`cross_chapter_relations` 和
`related_chapters` 分开保存。关系 ID、关系枚举、自环、重复、证据、强度和数量均在保存前校验。

兼容字段 `tree` 在生成/序列化时始终由 `current_chapter_tree` 派生，数据库不维护第二套独立树。

## 数据库迁移

迁移 `e7f8a9b0c1d2` 以增量方式扩展 `resource_generation_tasks` 和 `learning_resources`，不删除旧字段。

```powershell
alembic upgrade head
alembic current
```

部署前备份数据库，并确认当前数据库已经位于前置 revision `c3d4e5f6a7b8`。迁移后再部署应用代码，
否则新 SELECT/INSERT 会引用尚不存在的列。

## 配置

完整默认值见 `.env.example`。路径配置包括 `FRONTEND_SLIDES_VENDOR_DIR`、
`GENERATED_RESOURCE_DIR` 和 `PPT_HTML_TEMPLATE_DIR`；PPT、视频、思维导图和任务重试/超时均有独立配置。
生产环境必须覆盖 `SECRET_KEY`。生成课件默认存放在未公开静态挂载的 `generated_resources/`，只通过
签名接口访问。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check app tests
alembic heads
.\.venv\Scripts\python.exe -c "from app.main import app; print(len(app.routes))"
.\.venv\Scripts\python.exe -m playwright install chromium
```

Playwright 可用且已安装 Chromium 时会执行真实浏览器截图；否则基础环境使用 matplotlib 生成封面。
真实 Bilibili 网络验证应放在手工/integration 测试中，默认测试套件不访问外网。
