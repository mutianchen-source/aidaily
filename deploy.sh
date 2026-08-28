#!/bin/bash
# AI 资讯日报 · 腾讯云服务器一键部署脚本
# 在服务器上以 root 运行：bash deploy.sh
# 前提：项目文件已放到 /var/www/aidaily/ 目录下

set -e

APP_DIR="/var/www/aidaily"

echo "==> 1/5 更新软件源并安装 nginx"
apt-get update -y
apt-get install -y nginx

echo "==> 2/5 设置时区为北京时间"
timedatectl set-timezone Asia/Shanghai || true

echo "==> 3/5 配置 nginx"
cat > /etc/nginx/sites-available/aidaily <<EOF
server {
    listen 80 default_server;
    server_name _;
    root ${APP_DIR};
    index index.html;
    location / {
        try_files \$uri \$uri/ =404;
    }
}
EOF
ln -sf /etc/nginx/sites-available/aidaily /etc/nginx/sites-enabled/aidaily
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "==> 4/5 配置定时任务（每天 08:00 北京时间）"
CRON_LINE="0 8 * * * cd ${APP_DIR} && /usr/bin/python3 generate.py >> ${APP_DIR}/refresh.log 2>&1"
( crontab -l 2>/dev/null | grep -v generate.py ; echo "${CRON_LINE}" ) | crontab -

echo "==> 5/5 立即运行一次生成数据"
cd "${APP_DIR}"
/usr/bin/python3 generate.py

echo ""
echo "部署完成！在浏览器访问 http://服务器公网IP 即可查看。"
echo "以后每天 08:00 会自动刷新，日志在 ${APP_DIR}/refresh.log"
