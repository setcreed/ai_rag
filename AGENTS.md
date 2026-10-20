# 项目约定

本项目是 FastAPI、Vue 和双数据库组成的 RAG 展示项目，同时保留源码研读材料。

- `fastapi-app/`：后端，Python 3.12；业务数据使用 MySQL，向量使用 PostgreSQL + pgvector。
- `vue/`：前端，使用 npm 锁文件构建。
- `deploy/`、`compose.yaml`、`deploy.sh`：单机 Docker 展示部署；使用方式见 `README.md`。
- `docs/`：研读与面试材料，入口为 `docs/README.md`。
- `ROADMAP.md`：当前状态、待办和验证记录。

## 部署边界与验证

- 部署默认只暴露 Nginx，保留浏览器访问密码；这是 HTTP 展示环境，不承载敏感数据。
- 初始化 SQL 会删表，只允许官方容器在新数据卷首次初始化时导入；更新脚本不得重放 SQL 或删除数据卷。
- 真实部署凭据只存放在忽略提交的 `deploy/.env` 与 `deploy/secrets/`，不得打包到交付文件或镜像。
- 部署修改先做 Shell 语法与 Compose 配置检查，再使用独立 Compose 项目和任务专用目录做隔离验证。
- `fastapi-app/tests/` 的既有测试会写入并清扫数据库；不得直接针对用户数据库运行。部署独立测试位于 `deploy/tests/`。
