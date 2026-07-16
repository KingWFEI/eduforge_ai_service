# 学习资源生成前端对接文档

本文档说明小节资源壳子、资源生成、资源详情查询以及图解图片展示流程。

## 1. 核心约定

系统中存在两种不同的资源 ID：

| 名称 | 示例 | 用途 |
|---|---|---|
| 资源壳子 ID | `res_sec_001_illustration` | 首次展示推荐卡片，可作为生成接口的可选参数 |
| 实际资源 ID | `slr_a1b2c3` | 资源生成成功后返回，用于查询资源详情 |

前端查询详情时必须使用 `slr_` 开头的实际资源 ID，不要使用 `res_` 开头的壳子 ID。

接口需要携带登录 Token：

```http
Authorization: Bearer <access_token>
```

## 2. 获取资源壳子

```http
GET /api/courses/{course_id}/sections/{section_id}/recommendations
```

首次调用时，个性化推荐智能体会读取当前章节/小节学习内容、知识点、学习进度和用户画像，从四种候选类型中选择 1 到 4 种资源壳子，并缓存结果。资源列表不再固定返回全部类型。

后续调用默认复用缓存；当学习内容或用户画像更新后，可传 `refresh=true` 强制重新规划：

```http
GET /api/courses/{course_id}/sections/{section_id}/recommendations?refresh=true
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "suggestion": "建议通过图解和练习巩固当前知识点",
    "resources": [
      {
        "id": "res_sec_001_illustration",
        "title": "聚类算法图解",
        "subtitle": "通过可视化理解不同簇和聚类中心",
        "type": "illustration",
        "reason": "聚类内容包含数据分布，且当前学生偏好图解学习"
      }
    ]
  }
}
```

支持的资源类型：

```text
illustration  图解
code_case    代码案例
exercise     练习题
mind_map     思维导图
```

## 3. 生成资源

```http
POST /api/courses/{course_id}/sections/{section_id}/resources/generate
Content-Type: application/json
```

最简请求：

```json
{
  "type": "illustration"
}
```

完整请求：

```json
{
  "type": "illustration",
  "resource_id": "res_sec_001_illustration",
  "content_id": "slc_001"
}
```

字段说明：

| 字段 | 必填 | 说明 |
|---|---|---|
| `type` | 是 | 资源类型 |
| `resource_id` | 否 | 资源壳子 ID；不传时后端根据 `type` 定位 |
| `content_id` | 否 | 小节学习内容 ID；不传时使用最新内容 |

生成接口只允许生成推荐入口返回的类型。如果尚未调用推荐接口，或请求类型不在个性化壳子列表中，后端会拒绝生成。前端必须先获取壳子，再允许用户点击生成。

### 3.1 生成成功

生成接口只返回生成状态和实际资源 ID，不返回资源正文：

```json
{
  "code": 0,
  "message": "资源生成成功",
  "data": {
    "generated": true,
    "resource_id": "slr_a1b2c3"
  }
}
```

前端拿到 `resource_id` 后，应立即调用资源详情接口。

### 3.2 智能体决定不生成

图解资源会先结合章节内容和用户画像判断是否需要生成。不适合图解时仍返回 HTTP 200：

```json
{
  "code": 0,
  "message": "智能体判断无需生成资源",
  "data": {
    "generated": false,
    "resource_id": null
  }
}
```

`generated=false` 是正常业务结果，不是接口异常。此时不要调用详情接口，也不要新增空资源卡片。

## 4. 查询资源列表或详情

同一个接口支持两种模式。

### 4.1 查询该小节全部已生成资源

不传 `resource_id`：

```http
GET /api/courses/{course_id}/sections/{section_id}/resources
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "course_id": "course_001",
    "section_id": "sec_001",
    "total": 2,
    "items": [
      {
        "resource_id": "slr_a1b2c3",
        "title": "K-Means 聚类算法图解",
        "type": "illustration",
        "description": "通过散点图展示聚类结果",
        "content_text": "图解说明",
        "content_json": {},
        "image_url": "/uploads/generated/illustrations/illustration_xxx.png",
        "created_at": "2026-07-14T16:00:00"
      }
    ]
  }
}
```

### 4.2 查询单个资源详情

传入 `resource_id`：

```http
GET /api/courses/{course_id}/sections/{section_id}/resources?resource_id={resource_id}
```

示例：

```http
GET /api/courses/course_001/sections/sec_001/resources?resource_id=slr_a1b2c3
```

响应示例：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "resource_id": "slr_a1b2c3",
    "course_id": "course_001",
    "section_id": "sec_001",
    "knowledge_point_id": "kp_001",
    "title": "K-Means 聚类算法图解",
    "type": "illustration",
    "difficulty": "基础",
    "description": "通过散点图展示样本点、不同簇和聚类中心",
    "content_text": "图中不同颜色代表不同聚类结果。",
    "content_json": {
      "overview": "通过二维散点图观察聚类结果",
      "scenes": [],
      "key_takeaways": [],
      "visualization": {
        "renderer": "image",
        "image_url": "/uploads/generated/illustrations/illustration_xxx.png",
        "mime_type": "image/png",
        "generated_by": "python_matplotlib"
      }
    },
    "image_url": "/uploads/generated/illustrations/illustration_xxx.png",
    "source": "DeepSeek + 课程知识库 + 学生画像 + Python 可视化",
    "created_at": "2026-07-14T16:00:00",
    "updated_at": "2026-07-14T16:00:00"
  }
}
```

后端会校验资源是否属于当前用户、课程和小节。资源不存在、用户无权访问或资源不属于当前小节时返回 404。

## 5. 图解图片展示

Python 绘图代码只在后端执行。前端不会收到 Python 代码，只需要展示 `data.image_url`。

`image_url` 是相对于 API 服务的路径。前端需要与 API 地址拼接：

```ts
export function resolveResourceImageUrl(imageUrl?: string | null) {
  if (!imageUrl) return null;
  if (/^https?:\/\//.test(imageUrl)) return imageUrl;
  return `${API_BASE_URL}${imageUrl}`;
}
```

React 示例：

```tsx
const imageSrc = resolveResourceImageUrl(resource.image_url);

return imageSrc ? (
  <img
    src={imageSrc}
    alt={resource.title}
    loading="lazy"
    className="resource-illustration"
  />
) : null;
```

本地开发时完整图片地址类似：

```text
http://127.0.0.1:8000/uploads/generated/illustrations/illustration_xxx.png
```

## 6. TypeScript 类型

```ts
export type ResourceType =
  | "illustration"
  | "code_case"
  | "exercise"
  | "mind_map";

export interface GenerateResourceRequest {
  type: ResourceType;
  resource_id?: string | null;
  content_id?: string | null;
}

export interface GenerateResourceResult {
  generated: boolean;
  resource_id: string | null;
}

export interface ResourceDetail {
  resource_id: string;
  course_id: string;
  section_id: string;
  knowledge_point_id?: string | null;
  title: string;
  type: ResourceType;
  difficulty?: string | null;
  description?: string | null;
  content_text?: string | null;
  content_json?: Record<string, unknown> | null;
  image_url?: string | null;
  source?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ResourceListResult {
  course_id: string;
  section_id: string;
  total: number;
  items: Array<{
    resource_id: string;
    title: string;
    type: ResourceType;
    description?: string | null;
    content_text?: string | null;
    content_json?: Record<string, unknown> | null;
    image_url?: string | null;
    created_at?: string | null;
  }>;
}
```

## 7. 推荐调用流程

```text
进入小节
  → 获取资源壳子
  → GET /resources（不传 resource_id）恢复历史资源列表
  → 用户点击生成
  → POST 生成资源
  → 判断 generated
      → false：提示无需生成，流程结束
      → true：保存 resource_id
  → GET 查询资源详情
  → 根据 type 渲染正文、结构化内容或图片
```

前端伪代码：

```ts
async function generateAndLoadResource(courseId: string, sectionId: string, type: ResourceType) {
  const generateResponse = await api.post(
    `/api/courses/${courseId}/sections/${sectionId}/resources/generate`,
    { type },
  );
  const generated: GenerateResourceResult = generateResponse.data.data;

  if (!generated.generated || !generated.resource_id) {
    showMessage("智能体判断当前内容无需生成该资源");
    return null;
  }

  const detailResponse = await api.get(
    `/api/courses/${courseId}/sections/${sectionId}/resources`,
    { params: { resource_id: generated.resource_id } },
  );

  return detailResponse.data.data as ResourceDetail;
}
```

## 8. 前端注意事项

- `resource_id` 生成成功后需要保存，详情接口必须使用该 ID。
- 不要将壳子 ID 当作实际资源 ID。
- 不要期待生成接口直接返回正文或图片。
- `generated=false` 不应进入错误提示流程。
- 图片路径需要拼接 API 服务地址，不能拼接前端站点地址。
- 列表渲染时使用实际 `resource_id` 作为唯一键。
- 旧资源不会被新资源覆盖，每次成功生成都会得到新的实际资源 ID。

## 9. Swagger 与 Apifox

Swagger：

```text
http://127.0.0.1:8000/docs
```

OpenAPI 地址：

```text
http://127.0.0.1:8000/openapi.json
```

接口调整后，请在 Apifox 中重新同步 OpenAPI 文档。
