import os

# 业务库：MySQL，保存用户、知识库、对话、评测等全部结构化数据
TORTOISE_ORM = {
    "connections": {
        "default": {
            "engine": "tortoise.backends.mysql",
            "credentials": {
                "host": os.getenv("MYSQL_HOST", "localhost"),
                "port": int(os.getenv("MYSQL_PORT", "3306")),
                # 数据库名称，和 ai_rag.sql 里建的库同名
                "database": os.getenv("MYSQL_DATABASE", "ai_rag"),
                "user": os.getenv("MYSQL_USER", "root"),
                # 数据库密码，按本机 MySQL 实际密码改
                "password": os.getenv("MYSQL_PASSWORD", "123456"),
                "minsize": 1,
                "maxsize": int(os.getenv("MYSQL_POOL_MAX", "10")),
                "charset": "utf8mb4",
                "echo": os.getenv("SQL_ECHO", "true").lower() == "true"
            }
        },
    },
    "apps": {
      "models": {
          # 指向 models 包，Tortoise 会扫描包里导出的所有 Model 子类
          "models": ["models"],
          "default_connection": "default",
      }
    },
    # use_tz 开着时，auto_now_add / auto_now 生成的是 UTC 时间，
    # 而下面 timezone 又配的是东八区，两边对不上，
    # create_time 会比实际早 8 小时。关掉之后 Tortoise 统一按 timezone 生成
    "use_tz": False,
    "timezone": "Asia/Shanghai"
}

# 向量库：PostgreSQL + PGVector，只保存知识片段的向量和检索用的元数据
# 业务数据仍然在上面的 MySQL 里，两个库通过 knowledge_chunk.id 关联
PGVECTOR = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "ai_rag_vector"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "123456"),
    # 向量维度，必须与 ai_model_config 中启用的向量模型输出维度一致
    # 百炼 text-embedding-v4 默认输出 1024 维
    "dimension": 1024,
}

JWT_SECRET = os.getenv("JWT_SECRET", "ai-rag-advanced-knowledge-platform-jwt-secret")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24
