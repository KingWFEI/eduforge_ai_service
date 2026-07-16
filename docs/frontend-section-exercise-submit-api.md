# 提交随堂练习答案接口

## 基本信息

| 项目 | 内容 |
|---|---|
| 接口路径 | `POST /api/courses/{course_id}/sections/{section_id}/exercises/submit` |
| 认证 | 需要 Bearer Token |
| 角色 | 学生 |
| 幂等性 | 非幂等。每次请求都会创建一条新的提交记录 |

## 请求参数

路径参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `course_id` | string | 是 | 课程 ID |
| `section_id` | string | 是 | 小节 ID，对应章节结构中的小节 ID |

请求体：

```json
{
  "answers": [
    {
      "exercise_id": "ex_001",
      "type": "choice",
      "user_answer": "B",
      "is_correct": true
    },
    {
      "exercise_id": "ex_002",
      "type": "multi_choice",
      "user_answer": ["A", "B", "D"],
      "is_correct": true
    },
    {
      "exercise_id": "ex_003",
      "type": "true_false",
      "user_answer": false,
      "is_correct": false
    },
    {
      "exercise_id": "ex_004",
      "type": "fill_blank",
      "user_answer": ["无监督", "标签"],
      "is_correct": true
    }
  ]
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `answers` | array | 是 | 本次提交的答题列表，不能为空 |
| `answers[].exercise_id` | string | 是 | 题目 ID，对应 `content_json.exercises[].id` |
| `answers[].type` | string | 是 | `choice` / `multi_choice` / `true_false` / `fill_blank` |
| `answers[].user_answer` | dynamic | 是 | 用户答案，格式见下表 |
| `answers[].is_correct` | boolean | 是 | 前端判题结果 |

`user_answer` 格式：

| type | user_answer 类型 | 示例 |
|---|---|---|
| `choice` | string | `"B"` |
| `multi_choice` | array<string> | `["A", "B", "D"]` |
| `true_false` | boolean | `false` |
| `fill_blank` | array<string> | `["无监督", "标签"]` |

## 响应体

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "submit_id": "sub_20260626_001",
    "total": 5,
    "correct": 4,
    "incorrect": 1,
    "score": 80
  }
}
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `submit_id` | string | 本次提交记录 ID |
| `total` | int | 总题数 |
| `correct` | int | 正确题数 |
| `incorrect` | int | 错误题数 |
| `score` | int | 百分制分数，由后端按 `correct / total * 100` 计算 |

## 业务说明

- 后端不重新判题，直接以请求体中的 `is_correct` 为准。
- 后端会重新计算 `total`、`correct`、`incorrect` 和 `score`，前端不需要传分数。
- 同一用户对同一小节可以多次提交，每次提交都会生成新的 `submit_id`。
- 如果 `course_id + section_id` 不存在，接口返回 `40400`。
- 该接口只用于章节学习页的 `content_json.exercises[]` 随堂练习，不影响旧的 `/api/exercise/submit` 练习集接口。

## 获取最近一次随堂练习提交

学生每次进入章节学习页时，可以调用该接口获取当前小节最近一次做题情况。

### 基本信息

| 项目 | 内容 |
|---|---|
| 接口路径 | `GET /api/courses/{course_id}/sections/{section_id}/exercises/latest` |
| 认证 | 需要 Bearer Token |
| 角色 | 学生 |

### 请求参数

路径参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `course_id` | string | 是 | 课程 ID |
| `section_id` | string | 是 | 小节 ID |

### 有提交记录时响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "submit_id": "sub_20260626_001",
    "total": 5,
    "correct": 4,
    "incorrect": 1,
    "score": 80,
    "answers": [
      {
        "exercise_id": "ex_001",
        "type": "choice",
        "user_answer": "B",
        "is_correct": true
      },
      {
        "exercise_id": "ex_002",
        "type": "fill_blank",
        "user_answer": ["无监督", "标签"],
        "is_correct": true
      }
    ],
    "submitted_at": "2026-06-26T18:30:00"
  }
}
```

### 无提交记录时响应

```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `submit_id` | string | 最近一次提交记录 ID |
| `total` | int | 总题数 |
| `correct` | int | 正确题数 |
| `incorrect` | int | 错误题数 |
| `score` | int | 百分制分数 |
| `answers` | array | 最近一次提交的答题明细 |
| `answers[].exercise_id` | string | 题目 ID |
| `answers[].type` | string | `choice` / `multi_choice` / `true_false` / `fill_blank` |
| `answers[].user_answer` | dynamic | 用户提交的答案 |
| `answers[].is_correct` | boolean | 本题是否正确 |
| `submitted_at` | string | 最近一次提交时间 |

## 标记小节学习完成

学生完成当前小节学习内容后，调用该接口更新小节学习进度。课程目录接口会基于该进度展示小节完成状态。

### 基本信息

| 项目 | 内容 |
|---|---|
| 接口路径 | `POST /api/courses/{course_id}/sections/{section_id}/complete` |
| 认证 | 需要 Bearer Token |
| 角色 | 学生 |
| 幂等性 | 可重复调用，重复调用仍保持完成状态 |

### 请求参数

路径参数：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `course_id` | string | 是 | 课程 ID |
| `section_id` | string | 是 | 小节 ID |

请求体：无。

### 响应体

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "progress": 1.0
  }
}
```

### 业务说明

- 后端会把当前学生当前小节的学习进度写为 `progress = 1.0`。
- 后端会把当前学生当前小节的学习状态写为 `status = completed`。
- 如果之前没有学习进度记录，则创建新记录。
- 如果之前已有进度记录，则更新原记录，不重复创建。
- 如果 `course_id + section_id` 不存在，接口返回 `40400`。
