#!/bin/bash
set -Eeuo pipefail
[[ "$DEMO_PASSWORD" =~ ^[a-f0-9]{32}$ ]] || exit 1
export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"
mysql --default-character-set=utf8mb4 -uroot "$MYSQL_DATABASE" < /seed/ai_rag.sql
mysql --default-character-set=utf8mb4 -uroot "$MYSQL_DATABASE" <<SQL
UPDATE user SET password='$DEMO_PASSWORD' WHERE username='admin';
UPDATE user SET status='DISABLED' WHERE username <> 'admin';
UPDATE user SET avatar=REPLACE(avatar, 'http://127.0.0.1:9090/files/download/', '/api/files/download/');
UPDATE knowledge_document SET file_url=REPLACE(file_url, 'http://127.0.0.1:9090/files/download/', '/api/files/download/');
UPDATE ai_model_config SET api_key=NULL;
CREATE TABLE _deployment_state (id INT PRIMARY KEY);
INSERT INTO _deployment_state VALUES (1);
SQL
