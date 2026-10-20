# AI RAG 高级知识库平台 · 数据库脚本导入说明

本项目用到 **两个数据库**，导入数据时两个都要处理，项目才能正常运行：

| 数据库 | 存什么 | 对应脚本 |
| --- | --- | --- |
| **MySQL** | 业务数据（用户、知识库、文档、片段、模型配置、检索策略、对话、Agent 运行、评测等） | `ai_rag.sql` |
| **PostgreSQL + PGVector** | 向量数据（知识片段的 Embedding 向量） | `ai_rag_vector.sql` |

> 简单说：MySQL 存“文字和业务”，PostgreSQL 存“向量”。两个脚本分别导入到对应的数据库里。
>
> 两个库通过 `chunk_id` 关联：向量表里的 `chunk_id` 就是 MySQL 里 `knowledge_chunk.id`。

---

## 一、准备工作（先装好这些软件）

1. **安装 MySQL**（建议 8.x），默认端口 `3306`。
2. **安装 PostgreSQL + pgvector 扩展**，默认端口 `5432`。
   - 详细安装步骤见喂饭教程文档 **《10-Windows本地安装PostgreSQL与PGVector》**，一步步跟着装即可。
   - ⚠️ 一定要装 **pgvector 扩展**，否则向量脚本会报 `type "vector" does not exist`。
3. **安装 Python 3.12.10**，后端是 FastAPI 项目，依赖在 `ai_rag/fastapi-app/requirements.txt` 里。
4. **安装数据库管理工具**：
   - **Navicat for MySQL** —— 用来连 MySQL。
   - **Navicat for PostgreSQL** —— 用来连 PostgreSQL。
   - 如果你装的是 **Navicat Premium**，一个软件就够了（它同时支持 MySQL 和 PostgreSQL）。
   - ⚠️ **Navicat for MySQL 连不了 PostgreSQL**，反之亦然，别用错工具。

---

## 二、导入 MySQL 业务数据（`ai_rag.sql`）

1. 打开 **Navicat for MySQL**，新建连接，连上本地 MySQL：
   - 主机 `localhost`、端口 `3306`、用户名 `root`、密码填你本地 MySQL 的密码（项目默认是 `123456`）。
2. 在连接上**新建数据库**：
   - 数据库名：`ai_rag`
   - 字符集：`utf8mb4`
   - 排序规则：`utf8mb4_unicode_ci`
   - ⚠️ 脚本里没有 `CREATE DATABASE` 语句，库必须自己先建好，否则没有地方执行脚本。
3. **双击进入 `ai_rag` 数据库** → 右键 → **运行 SQL 文件…** → 选择 `ai_rag.sql` → 开始。
4. 刷新左侧，能看到下面 25 张表，就说明导入成功：

```text
user                        用户，管理员和普通用户用 role 字段区分

ai_model_config             AI 模型配置，对话 / 向量 / 重排三类模型
prompt_template             Prompt 模板，代码按 code 取模板
function_tool               Agent 工具注册表，enabled 是真开关

knowledge_base              知识库
knowledge_document          知识文档
knowledge_chunk             知识片段
chunk_strategy              切分策略
document_process_task       文档处理任务，记录解析和切分的每一步

retrieval_strategy          检索策略配置
retrieval_debug_record      召回对比调试台的调试记录

qa_app                      问答应用
qa_app_kb                   问答应用与知识库的关联
chat_session                会话
chat_message                会话消息
message_reference           回答引用的片段来源
message_feedback            用户对回答的点赞点踩反馈

agent_run                   Agentic RAG 的一次运行
agent_step                  运行内的每一步节点
tool_call_log               工具调用日志

eval_dataset                评测集
eval_case                   评测问答对
eval_task                   评测任务
eval_case_result            单条评测结果
eval_report                 评测报告
```

每张表前面都有 `DROP TABLE IF EXISTS`，**脚本可以重复执行**，每次执行都是一套干净的表加初始化数据。

⚠️ 重复执行会清空所有业务数据，包括你自己传的文档和跑过的对话。

脚本自带的演示数据里，有 3 个知识库、11 篇文档、121 条知识片段、3 个问答应用，以及跑过的对话、Agent 运行记录和评测报告，导入后不用自己造数据就能把各个页面点一遍。

登录账号（密码都是 `123456`）：

```text
admin      平台管理员
zhangsan   普通用户
lisi       普通用户
```

---

## 三、导入 PostgreSQL 向量数据（`ai_rag_vector.sql`）

> 前提：第一步里的 **PostgreSQL 和 pgvector 扩展已经装好**（见 10 文档）。

1. 打开 **Navicat for PostgreSQL**，新建连接，连上本地 PostgreSQL：
   - 主机 `localhost`、端口 `5432`、用户名 `postgres`、密码 `123456`（或你安装 PostgreSQL 时设置的密码）。
2. 新建数据库：
   - 数据库名：`ai_rag_vector`
3. **双击进入 `ai_rag_vector` 数据库** → 右键 → **运行 SQL 文件…** → 选择 `ai_rag_vector.sql` → 开始。
   - 这个脚本已经包含了 `CREATE EXTENSION vector` + 建表 + 110 条向量数据 + 索引，**可以直接执行、也可以重复执行**（重复执行会先删旧表再重建，数据不会翻倍）。
4. 刷新左侧，能看到 `knowledge_chunk_vector` 表、里面有 110 条向量数据，就说明导入成功。

### 为什么是 110 条，而 MySQL 里有 121 条片段

`knowledge_chunk` 里的 121 条片段中，有 11 条是父子分块产生的**父块**。父块只在检索命中子块之后用来补全上下文，本身不参与向量检索，所以不做向量化，`vector_status` 是「待向量化」。真正向量化的是 68 条普通块加 42 条子块，一共 110 条，和向量表的行数正好对上。

---

## 四、核对项目配置（`settings.py`）

项目后端配置文件在：

```text
ai_rag/fastapi-app/settings.py
```

默认配置如下，**如果你本地的端口 / 账号 / 密码和下面不一样，就改这里对应的值**：

```python
# MySQL 业务库
"credentials": {
    "host": "localhost",
    "port": 3306,
    "database": "ai_rag",
    "user": "root",
    "password": "123456",
}

# PostgreSQL 向量库
PGVECTOR = {
    "host": "localhost",
    "port": 5432,
    "database": "ai_rag_vector",
    "user": "postgres",
    "password": "123456",
    "dimension": 1024,
}
```

⚠️ 这里的 `dimension` 必须和向量脚本对得上：脚本建的表字段是 `vector(1024)`。改了其中一个，另一个也要跟着改，否则写入向量会报维度不匹配。

向量表的表名 `knowledge_chunk_vector` 直接写在 `ai/vector_store.py` 的 SQL 里，不在配置文件中，改表名要连代码一起改。

---

## 五、导入完还要做一件事：填真实 API Key

脚本里已经预置了三条 AI 模型配置（对话模型、向量模型、重排模型），接口地址、协议和模型名都填好了，但 **API Key 是空的**（数据库里是 `NULL`），不填上真实的 Key 没法调用模型。

登录管理端 → 左侧【AI 配置 → AI模型配置】→ 依次编辑这三条配置：

| 配置名称 | 模型类型 | 接口协议 | 接口地址 | 模型名称 |
| --- | --- | --- | --- | --- |
| 百炼对话模型配置 | 对话模型 | OpenAI兼容 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 百炼向量模型配置 | 向量模型 | OpenAI兼容 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `text-embedding-v4` |
| 百炼重排模型配置 | 重排模型 | DashScope原生 | `https://dashscope.aliyuncs.com/api/v1` | `gte-rerank-v2` |

- **API Key**：填你自己申请的真实 Key，这是唯一必须补的字段，三条都要填。
- **接口地址**：脚本里已填好。注意 OpenAI 兼容协议填的是**基础地址**，不要填到 `/chat/completions` 或 `/embeddings` 这一层。
- **接口协议**：决定代码走哪条调用路径。对话模型和向量模型走 OpenAI 兼容接口，重排模型走 DashScope 原生接口，两者的地址不一样，别填混。
- **向量维度**：向量模型那条的维度是 `1024`，必须和 `settings.py` 里的 `dimension`、向量表的 `vector(1024)` 三处一致。

⚠️ **向量模型要特别注意**：脚本里的 110 条向量是用 **1024 维**的向量模型生成的。如果你换成输出维度不同的向量模型，旧向量和新问题的向量就不在同一个空间里，检索结果会不准。这时候要么换回 1024 维的模型，要么在【知识库管理 → 文档管理】页面对每篇文档点一次「向量化」，用你自己的模型把片段重新生成一遍。

---

## 六、常见问题

- **执行向量脚本报 `type "vector" does not exist`**
  → PostgreSQL 没装 pgvector 扩展，回看 10 文档把扩展装上。

- **Navicat for MySQL 打不开 PostgreSQL 的库**
  → 正常现象，它只支持 MySQL。PostgreSQL 要用 **Navicat for PostgreSQL** 或 **Navicat Premium**。

- **执行 `ai_rag.sql` 报错说没有选中数据库**
  → 脚本里没有 `CREATE DATABASE`，要先手工建好 `ai_rag` 库，双击进入这个库之后再运行脚本。

- **中文乱码**
  → MySQL 数据库字符集要用 `utf8mb4`；导入时确保脚本文件是 UTF-8 编码。

- **向量脚本执行时提示表已存在 / 冲突**
  → 本脚本已带 `DROP TABLE IF EXISTS ... CASCADE`，可以重复执行；如果仍报错，确认你连的是 `ai_rag_vector` 这个库。

- **后端启动报连不上向量库**
  → PostgreSQL 服务没启动，或者 `settings.py` 里的 `PGVECTOR` 端口密码和本地对不上。

- **提问时回答说没有检索到资料**
  → 先确认向量脚本导入成功、【知识库管理 → 片段管理】里片段的向量化状态是「已完成」；再看该问答应用绑定的检索策略里，相似度阈值是不是调得太高，调低一点重试。

- **AI 功能报模型配置相关的错**
  → 就是第五节说的，脚本里的 API Key 是空的，去【AI 配置 → AI模型配置】里把三条配置的 Key 都填上。

- **不想导入向量数据**
  → 也可以不导入 `ai_rag_vector.sql`，但表还是要建：先执行脚本里建表和建索引的部分，再到管理端【知识库管理 → 文档管理】页面对每篇文档点「向量化」重新生成向量（前提是在【AI模型配置】里配好了可用的向量模型和真实 API Key）。

---

## 七、整体启动顺序

```text
1. 装好 MySQL、PostgreSQL（含 pgvector 扩展）、Python
2. 新建 ai_rag 库，导入 ai_rag.sql                  → MySQL
3. 新建 ai_rag_vector 库，导入 ai_rag_vector.sql    → PostgreSQL
4. 按需修改 settings.py 的账号 / 密码 / 端口
5. 安装后端依赖：pip install -r requirements.txt
6. 启动后端：python main.py                          → 9090 端口
7. 启动前端：npm install 后 npm run dev              → 5173 端口
8. 登录管理端，在【AI模型配置】里填真实 API Key
```

到这里数据库就准备好了，项目可以正常跑起来。
