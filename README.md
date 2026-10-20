# AI RAG 展示项目

FastAPI + Vue 企业知识库，MySQL 保存业务数据，PostgreSQL + pgvector 保存向量数据。使用外部模型 API，无需 GPU。源码研读材料见 [docs/README.md](docs/README.md)，项目状态见 [ROADMAP.md](ROADMAP.md)。

## 一键部署

适用：空白 Ubuntu/Debian 服务器，建议 Ubuntu 24.04，2 核、4 GB 内存，至少 20 GB 可用磁盘。需能访问 Docker 官方软件源、Docker Hub、PyPI 和 npm。首次构建时间取决于网络，脚本串行构建以降低峰值内存。

先将项目推送到自己的 GitHub 仓库。在本地项目目录执行以下命令，将 `YOUR_NAME` 替换为 GitHub 用户名，仓库名按实际修改。先在 GitHub 创建空仓库，不添加 README 或其他初始化文件：

```bash
# 已初始化仓库时跳过 git init
git init -b main
git status --short
git add .
git diff --cached --stat
git commit -m "init: 纳入 RAG 源码与 Docker 展示部署配置，支持服务器部署"
git remote add origin https://github.com/YOUR_NAME/ai_rag.git
git push -u origin main
```

提交前确认 SQL、示例文件和源码中没有自己的敏感数据或凭据。`.gitignore` 已排除真实环境文件、部署密码、部署状态、依赖和临时目录。GitHub 命令行认证方式见 [GitHub 官方说明](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github)。

在服务器安装 Git 后拉取仓库，再执行部署脚本：

```bash
# Ubuntu/Debian，已有 Git 时跳过
sudo apt-get update
sudo apt-get install -y git

# 在当前用户有写权限的目录中拉取
git clone https://github.com/YOUR_NAME/ai_rag.git
cd ai_rag
sudo bash deploy.sh
```

私有仓库建议在服务器配置仅有读取权限的 SSH Deploy Key，配置方式见 [GitHub 官方说明](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys)，然后使用 SSH 地址拉取：

```bash
git clone git@github.com:YOUR_NAME/ai_rag.git
```

也可以把整个项目上传到服务器，例如 `/opt/ai_rag`，然后在该目录执行：

```bash
sudo bash deploy.sh
```

脚本会自动安装缺失的 Docker Engine 和 Compose 插件、生成随机凭据、构建镜像、初始化两个空数据卷、启动服务并验证登录。已有 Docker 时直接复用；缺少 Compose 插件时尝试从官方软件源补装，不卸载冲突包，不修改防火墙或添加镜像加速器。安装中断后可以重试，已有密钥及源配置与预期一致时复用，不一致时保留原文件并停止。自动安装依据 [Docker 官方 Ubuntu 文档](https://docs.docker.com/engine/install/ubuntu/)；其他系统安装好 Docker 和 Compose 后也可运行脚本。

部署完成后，在云服务器安全组放行 TCP `80`，建议限制到演示者 IP。打开 `http://服务器公网IP`：

1. 浏览器弹窗填写账号 `demo` 和脚本输出的随机密码。
2. 应用登录页填写账号 `admin` 和同一随机密码。
3. 在模型配置页面分别填写对话、向量和重排模型的 API Key，然后测试连接。初始向量为 `1024` 维，不要随意切换 Embedding 模型。

脚本不会自动向模型服务发起收费调用。演示数据的其他账号初始为停用状态；管理员可以在页面按需启用。HTTP 和访问密码用于受控展示，不适合敏感数据；应用仍沿用原项目密码存储方式。需要公开长期运营时，应另行完成 HTTPS、密码哈希和文件授权改造。

## 更新、日志与数据

本地修改并提交、推送后，在服务器项目目录执行：

```bash
git pull --ff-only && sudo bash deploy.sh
```

仅在拉取成功后部署。`--ff-only` 在服务器分支有分叉时会停止，避免自动合并。不要直接在服务器修改业务源码；端口及密码等本机配置保存在忽略提交的文件中，不参与拉取。

部署会使用构建缓存重建镜像并启动服务，保留凭据与数据，不重新导入 SQL。只有完整部署及管理员登录验收成功后，才写入 `deploy/.installed`；失败后重试仍验收管理员登录，后续正常更新只验收代理与接口。如果已在页面修改应用密码，使用新密码登录。

```bash
# 配置检查，不安装软件或启动容器
bash deploy.sh --check

# 状态与日志
sudo docker compose --env-file deploy/.env ps
sudo docker compose --env-file deploy/.env logs --tail=80 backend

# 停止服务，保留数据
sudo docker compose --env-file deploy/.env stop
```

- `deploy/.env`：数据库、JWT 和展示访问凭据，权限为 `600`；请备份并保密，更新时保留。
- `deploy/secrets/demo.htpasswd`：自动生成的浏览器访问密码摘要，目录仅供管理员读取。
- `deploy/.installed`：首次部署验收成功标记，更新和备份时保留；不要手动创建以跳过验收。旧版部署没有此标记，升级时会补做初始管理员登录验收；如果应用密码已修改，需先通过页面恢复为 `deploy/.env` 中的初始密码，完成验收后再修改。
- `mysql_data`、`postgres_data`、`uploads`：项目命名卷，分别保存业务、向量和文件；上传卷首次从后端镜像复制示例文件，此后保留已有内容。
- 初始化脚本仅在新数据库卷首次启动时执行。SQL 包含删表语句，不要手工对已有数据库重复导入，不要使用 `docker compose down -v`。
- 镜像升级不会把新的示例文件自动合并到已有上传卷。

如端口 `80` 被占用，可在首次生成配置后修改 `deploy/.env` 的 `HTTP_PORT` 并重新运行。备份时应停止业务写入，配套保存两个数据库的逻辑导出、上传文件和凭据，并验证恢复结果。

数据库初始化失败时脚本会停止，保留现场。查看对应容器日志；不要删除数据卷或反复手工导入 SQL。软件源或镜像仓库无法访问时，先解决服务器网络再重试。

当前镜像在服务器本地构建；修改前后端依赖后需要重新下载对应依赖，首次部署仍取决于网络和内存。只改文档通常可以复用镜像构建缓存。

## 部署结构与验证

`compose.yaml` 管理 Nginx、后端、MySQL 和带 pgvector 的 PostgreSQL，仅 Nginx 发布端口。Nginx 代理 `/api/` 并去掉前缀，关闭响应缓冲以支持 SSE。后端单 worker 运行，适合低并发展示，避免同时执行多份 OCR。

隔离回归测试入口：

```bash
python3 -m unittest discover -s deploy/tests -v
```

既有 `fastapi-app/tests/` 会写入并清扫数据库，不应对演示库直接运行。实际容器验证情况见 `ROADMAP.md`。
