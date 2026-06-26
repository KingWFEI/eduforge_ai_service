# 课程文档解析与图片展示前端接入说明

## 1. 功能概述

课程资料处理流程已更新为：

```text
上传 PDF / PPTX / DOCX / Markdown
  -> MarkItDown 转换为 Markdown
  -> 提取并保存文档图片
  -> 识别目录、章节和小节
  -> 按标题层级切分知识块
  -> 写入 MySQL 和 Chroma
  -> 生成课程结构草稿
  -> 确认结构并重建索引
  -> 按小节生成学习内容
```

主要变化：

1. 文档不再只按固定字数切块，改为优先按 Markdown 标题和编号标题切块。
2. 支持识别 `1 标题`、`1.1 标题`、`1.1.1 标题`。
3. PPTX 内嵌图片、PDF 含图页面和 DOCX 图片会保存为公开资源。
4. 知识块和学习内容可以包含 Markdown 图片。
5. 章节内容生成优先精确读取当前小节的知识块，再使用向量检索补充。

## 2. 静态图片地址

图片保存在：

```text
uploads/course_documents/{course_id}/{document_id}/assets/
```

后端已将 `/uploads` 挂载为静态资源目录。

接口返回的图片地址通常为相对地址：

```text
/uploads/course_documents/course_xxx/doc_xxx/assets/slide-021-image-01.png
```

前端需要拼接 API 服务地址：

```ts
const imageUrl = `${API_BASE_URL}${asset.url}`;
```

例如：

```text
http://127.0.0.1:8010/uploads/course_documents/course_xxx/doc_xxx/assets/slide-021-image-01.png
```

不要将返回地址当成本地文件路径处理。

## 3. 上传课程资料

### 接口

```http
POST /api/courses/{course_id}/upload
Content-Type: multipart/form-data
Authorization: Bearer {token}
```

权限：教师、管理员。

### 表单参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `file` | File | 是 | 上传文件 |
| `chapter_id` | string | 否 | 手动指定所属章节 |
| `description` | string | 否 | 文档说明 |
| `auto_generate_structure` | boolean | 否 | 是否上传后自动生成结构草稿，默认 `true` |

### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "document_id": "doc_123",
    "course_id": "course_123",
    "filename": "TRM.pptx",
    "chunk_count": 6,
    "parse_status": "parsed",
    "index_status": "indexed",
    "asset_count": 35,
    "assets": [
      {
        "filename": "slide-002-image-01.png",
        "url": "/uploads/course_documents/course_123/doc_123/assets/slide-002-image-01.png",
        "asset_type": "slide_image",
        "page_no": null,
        "slide_no": 2,
        "alt": "第 2 页插图 1"
      }
    ],
    "structure_draft": null
  }
}
```

### 新增字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `asset_count` | number | 提取出的图片数量 |
| `assets` | array | 图片资源列表 |

如果 `auto_generate_structure=true`，`structure_draft` 会返回生成的结构草稿。

上传和解析是同步操作，大文件可能耗时较长。前端应显示上传及解析中的加载状态，避免重复提交。

## 4. 文档图片结构

```ts
interface DocumentAsset {
  filename: string;
  url: string;
  asset_type: "slide_image" | "pdf_page" | "document_image";
  page_no: number | null;
  slide_no: number | null;
  alt: string;
}
```

资源类型说明：

| `asset_type` | 说明 |
|---|---|
| `slide_image` | PPTX 中提取出的内嵌图片 |
| `pdf_page` | PDF 中包含图片的整页预览 |
| `document_image` | DOCX 中提取出的媒体图片 |

PDF 使用整页预览，是为了保留矢量图、公式、文字标注和布局关系。

## 5. 获取课程文档列表

### 接口

```http
GET /api/courses/{course_id}/documents
```

文档列表中的每项新增：

```json
{
  "document_id": "doc_123",
  "filename": "TRM.pptx",
  "chunk_count": 6,
  "assets": [
    {
      "filename": "slide-021-image-01.png",
      "url": "/uploads/course_documents/course_123/doc_123/assets/slide-021-image-01.png",
      "asset_type": "slide_image",
      "slide_no": 21,
      "page_no": null,
      "alt": "第 21 页插图 1"
    }
  ]
}
```

前端可以使用 `assets.length` 显示图片数量，并提供“查看原始插图”入口。

## 6. 单独获取文档图片

### 接口

```http
GET /api/courses/{course_id}/documents/{document_id}/assets
```

权限：学生、教师、管理员。

### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "course_id": "course_123",
    "document_id": "doc_123",
    "filename": "TRM.pptx",
    "total": 35,
    "items": [
      {
        "filename": "slide-021-image-01.png",
        "url": "/uploads/course_documents/course_123/doc_123/assets/slide-021-image-01.png",
        "asset_type": "slide_image",
        "page_no": null,
        "slide_no": 21,
        "alt": "第 21 页插图 1"
      }
    ]
  }
}
```

推荐前端使用图片网格或图片查看器展示，并根据 `slide_no`、`page_no` 排序。

## 7. 获取知识块

### 接口

```http
GET /api/courses/{course_id}/chunks
```

### 查询参数

| 参数 | 类型 | 说明 |
|---|---|---|
| `document_id` | string | 按文档过滤 |
| `chapter_id` | string | 按章节或小节过滤 |
| `keyword` | string | 搜索正文、标题或文件名 |
| `page` | number | 页码 |
| `page_size` | number | 每页数量，最大 100 |

### 知识块示例

```json
{
  "chunk_id": "chunk_123",
  "document_id": "doc_123",
  "course_id": "course_123",
  "chapter_id": "sec_123",
  "section": "注意力机制 > TRM中的注意力",
  "content": "## TRM中的注意力\n\n在只有单词向量的情况下...\n\n![第 21 页插图 1](/uploads/course_documents/course_123/doc_123/assets/slide-021-image-01.png)",
  "images": [
    "/uploads/course_documents/course_123/doc_123/assets/slide-021-image-01.png"
  ],
  "chunk_index": 10,
  "indexed": true
}
```

### 新增字段

```ts
images: string[];
```

`content` 本身已经包含 Markdown 图片，`images` 用于：

- 单独展示图片缩略图；
- 图片预加载；
- 图片查看器；
- 不渲染完整 Markdown 时展示关联插图。

## 8. Markdown 渲染要求

前端展示以下字段时必须使用 Markdown 渲染器：

- `knowledge_chunks.content`
- `course chapter content.content`
- `section learning content.content_markdown`

Markdown 渲染器需要支持：

- 标题；
- 列表；
- 表格；
- 代码块；
- 图片；
- 普通链接。

图片地址转换示例：

```ts
function resolveAssetUrl(url: string): string {
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return url;
  return `${API_BASE_URL}${url.startsWith("/") ? "" : "/"}${url}`;
}
```

如果 Markdown 组件支持自定义图片节点：

```tsx
<Markdown
  components={{
    img: ({ src = "", alt = "" }) => (
      <img
        src={resolveAssetUrl(src)}
        alt={alt}
        loading="lazy"
        className="course-content-image"
      />
    ),
  }}
>
  {contentMarkdown}
</Markdown>
```

建议样式：

```css
.course-content-image {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 16px auto;
  object-fit: contain;
}
```

不要允许图片超出正文容器。

## 9. 生成课程结构草稿

### 接口

```http
POST /api/courses/{course_id}/structure-drafts/generate
```

请求：

```json
{
  "document_ids": ["doc_123"]
}
```

系统优先使用文档完整目录树生成草稿，不再使用少量 RAG 命中结果代替完整目录。

支持的标题形式：

```text
1 一级章节
1.1 二级小节
1.1.1 三级标题
```

前端应展示草稿编辑器，允许教师修改：

- 章节标题；
- 小节标题；
- 描述；
- 知识点名称；
- 知识点描述和难度。

## 10. 确认课程结构

### 接口

```http
POST /api/course-structure-drafts/{draft_id}/confirm
```

请求：

```json
{
  "draft": null,
  "rebuild_index": true
}
```

如果教师编辑过草稿，可以将完整草稿放入 `draft`。

`rebuild_index=true` 时系统会：

1. 保存正式章节、小节和知识点；
2. 重新解析原文和图片；
3. 重新生成知识块；
4. 将知识块归属到正式小节；
5. 保留图片 URL。

确认期间前端应显示不可重复提交的加载状态。

## 11. 生成小节学习内容

### 创建任务

```http
POST /api/course-structure-drafts/{draft_id}/generate-content
```

### 查询任务

```http
GET /api/course-structure-drafts/content-generation-tasks/{task_id}
```

### SSE 进度

```http
GET /api/course-structure-drafts/content-generation-tasks/{task_id}/events
```

任务状态：

```text
pending
running
completed
failed
cancelled
```

前端重点展示：

- `progress`
- `current_step`
- `current_section`
- `contents_generated`
- `contents_failed`
- `error_message`

## 12. 查询生成内容

### 接口

```http
GET /api/course-structure-drafts/contents
```

查询参数：

```text
course_id={course_id}
chapter_id={chapter_id}
section_id={section_id}
```

生成的 `content_markdown` 可能包含：

```markdown
## 来源插图

![来源插图](/uploads/course_documents/course_123/doc_123/assets/slide-021-image-01.png)
```

前端应使用和知识块相同的 Markdown 图片处理逻辑。

## 13. 章节原文内容

### 接口

```http
GET /api/courses/{course_id}/chapters/{chapter_id}/content
```

返回的每个 `chunks` 项新增：

```ts
images: string[];
```

聚合字段 `content` 也可能直接包含 Markdown 图片。

## 14. 兼容性和旧数据

旧文档的知识块中没有图片 URL，不会自动更新。

处理方式：

1. 重新上传原文件；或
2. 确认结构时使用 `rebuild_index=true`；或
3. 调用已有文档重建索引入口。

前端应兼容以下情况：

```ts
assets ?? []
images ?? []
asset_count ?? 0
```

不要假设所有历史文档都包含图片资源。

## 15. 当前限制

1. PPTX 只能直接提取内嵌图片。
2. 由多个文本框、箭头和形状组合而成的 PPT 图形可能不会作为单张图片提取。
3. PDF 当前展示含图页面的整页预览。
4. 当前功能解决的是图片保存、关联和展示，不包含图片语义理解。
5. 图片中的公式、流程关系和知识说明需要后续接入 OCR 或视觉模型。

## 16. 推荐前端页面

知识库管理页建议增加：

- 文档图片数量；
- 查看图片按钮；
- 图片预览弹窗；
- 解析状态；
- 索引状态；
- 重新索引入口。

知识块详情建议增加：

- Markdown 正文；
- 关联图片缩略图；
- 来源文档；
- 标题路径；
- 所属章节和知识点。

学生学习内容页建议：

- 正文内直接渲染 Markdown 图片；
- 点击图片查看原图；
- 图片使用懒加载；
- 加载失败时显示 `alt` 文本和重试按钮。

## 17. 联调检查清单

- [ ] PPTX 上传响应包含 `asset_count` 和 `assets`
- [ ] 图片 URL 拼接 API 地址后可返回 `200`
- [ ] 文档图片接口能返回完整图片列表
- [ ] chunk 的 `content` 可以渲染图片
- [ ] chunk 的 `images` 与正文图片一致
- [ ] 生成草稿包含完整课程目录
- [ ] 确认结构后图片仍保留
- [ ] 生成学习内容包含来源插图
- [ ] 历史文档没有 `assets/images` 时页面不报错
- [ ] 图片在移动端不会超出正文容器
