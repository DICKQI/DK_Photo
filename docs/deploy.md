# DK Photo Docker 部署指南

## 概述

DK Photo 使用 Docker Compose 部署，包含两个服务：

| 服务 | 端口 | 说明 |
|------|------|------|
| `frontend` | `FRONTEND_PORT`，默认 `8080` | Nginx 静态前端，并代理 `/api` 到后端 |
| `backend` | `BACKEND_PORT`，默认仅本机 `127.0.0.1:8000` | FastAPI / Uvicorn 后端 |

默认情况下，外部访问前端 `http://<服务器IP>:8080` 即可；后端 `8000` 只绑定本机，避免直接暴露 API。

## Ubuntu 一键部署

在 Ubuntu/Debian 服务器上，克隆完整项目后可以直接运行部署脚本：

```bash
git clone <your-repo-url> DK_Photo
cd DK_Photo
bash deploy.sh
```

如果 `deploy.sh` 在 Git 中保留了可执行权限，也可以运行：

```bash
./deploy.sh
```

脚本会交互式完成：

1. 检查 Docker Engine 和 Docker Compose 插件。
2. 如果 Ubuntu/Debian 上未安装 Docker，询问是否自动安装。
3. 创建 `.env`。
4. 首次部署时初始化管理员显示名称、邮箱和密码。
5. 自动生成 `DK_PHOTO_SECRET_KEY`。
6. 创建数据目录和照片目录。
7. 检查端口占用。
8. 构建并启动服务。

> 自动安装 Docker 需要服务器能访问外网，并且当前用户具有 `sudo` 权限。非 Ubuntu/Debian 系统需要先手动安装 Docker 与 Compose 插件。

## 首次部署交互项

首次部署且数据库尚不存在时，脚本会提示输入：

- 管理员显示名称：写入 `DK_PHOTO_ADMIN_NAME`
- 管理员邮箱：写入 `DK_PHOTO_ADMIN_EMAIL`
- 管理员密码：写入 `DK_PHOTO_ADMIN_PASSWORD`

密码可以留空，脚本会自动生成强密码并在部署完成后显示一次，同时保存到 `.env`。

如果 `APP_DATA_PATH/dk_photo.sqlite3` 已存在，脚本不会用 `.env` 覆盖已有管理员。已有账号请在应用后台修改。

## 手动部署

```bash
cp .env.example .env
nano .env
docker compose up -d --build
docker compose ps
```

打开 `http://<服务器IP>:8080`，使用 `.env` 中配置的管理员账号登录。

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|------|------|
| `DK_PHOTO_ADMIN_NAME` | 是 | `Administrator` | 初始管理员显示名称，仅首次建库时生效 |
| `DK_PHOTO_ADMIN_EMAIL` | 是 | `admin@example.com` | 初始管理员邮箱，仅首次建库时生效 |
| `DK_PHOTO_ADMIN_PASSWORD` | 是 | `change-me-now` | 初始管理员密码，仅首次建库时生效，生产环境务必修改 |
| `DK_PHOTO_SECRET_KEY` | 是 | 自动生成 | JWT 签名密钥 |
| `DK_PHOTO_DATA_DIR` | 否 | `/app/data` | 容器内数据目录 |
| `DK_PHOTO_DEFAULT_LIBRARY_PATH` | 否 | `/photos` | 默认图库在容器内的路径 |
| `DK_PHOTO_DEFAULT_LIBRARY_NAME` | 否 | `Family Photos` | 默认图库名称 |
| `DK_PHOTO_CORS_ORIGINS` | 否 | `http://localhost:5173,http://localhost:8080` | 允许的跨域来源 |
| `DK_PHOTO_WATCH_ENABLED` | 否 | `true` | 是否启用文件监控自动扫描 |
| `DK_PHOTO_ACCESS_TOKEN_MINUTES` | 否 | `10080` | JWT 过期时间，单位分钟 |
| `PHOTOS_PATH` | 是 | `./photos` | 宿主机照片目录，生产环境建议使用绝对路径 |
| `APP_DATA_PATH` | 否 | `./data` | 宿主机数据目录 |
| `FRONTEND_BIND` | 否 | `0.0.0.0` | 前端监听地址 |
| `FRONTEND_PORT` | 否 | `8080` | 前端宿主机端口 |
| `BACKEND_BIND` | 否 | `127.0.0.1` | 后端监听地址，默认仅本机 |
| `BACKEND_PORT` | 否 | `8000` | 后端宿主机端口 |

## 目录结构

部署后的常见目录布局：

```text
DK_Photo/
├── .env
├── docker-compose.yml
├── deploy.sh
├── data/
│   ├── dk_photo.sqlite3
│   └── thumbnails/
├── photos/
├── backend/
└── frontend/
```

在 `docker-compose.yml` 中：

- `${APP_DATA_PATH}` 挂载到 `/app/data`，用于数据库和缩略图，读写。
- `${PHOTOS_PATH}` 挂载到 `/photos`，用于照片库，只读。

## 挂载多个照片目录

默认脚本只挂载一个照片目录。如果需要多个目录，可以在 `docker-compose.yml` 的 `backend.volumes` 中追加：

```yaml
volumes:
  - ${APP_DATA_PATH:-./data}:/app/data
  - ${PHOTOS_PATH:-./photos}:/photos:ro
  - /mnt/nas/family:/mnt/photos/family:ro
  - /mnt/nas/travel:/mnt/photos/travel:ro
```

重启后，在管理后台通过文件浏览器选择对应容器内路径添加图库。

## 日常管理

```bash
docker compose ps
docker compose logs -f
docker compose logs -f backend
docker compose restart
docker compose down
docker compose up -d --build
```

如果脚本提示当前用户需要 `sudo docker`，上面的命令也相应改成 `sudo docker compose ...`。

## 升级更新

```bash
git pull
cp -r data data-backup-$(date +%Y%m%d)
bash deploy.sh
```

已有数据库存在时，脚本不会重新初始化管理员账号。

## 备份恢复

备份：

```bash
tar -czf dk-photo-backup-$(date +%Y%m%d).tar.gz data/
```

恢复：

```bash
docker compose down
tar -xzf dk-photo-backup-YYYYMMDD.tar.gz
docker compose up -d
```

## 安全建议

1. 使用脚本生成或手动设置强 `DK_PHOTO_SECRET_KEY`。
2. 生产环境使用强管理员密码。
3. 防火墙只开放前端端口，默认是 `8080`。
4. 默认不要公开后端 `8000`，当前 Compose 已将后端绑定到 `127.0.0.1`。
5. 正式公网访问建议通过 Nginx/Caddy/Traefik 配置 HTTPS。

### HTTPS 反向代理

如果外部反代负责公网入口，可以把前端也改为仅本机监听：

```env
FRONTEND_BIND=127.0.0.1
FRONTEND_PORT=8080
BACKEND_BIND=127.0.0.1
BACKEND_PORT=8000
```

然后将外部 Nginx/Caddy 反代到 `http://127.0.0.1:8080`。

## 故障排查

### 容器无法启动

```bash
docker compose logs backend
docker compose logs frontend
```

### 前端页面空白或 API 请求失败

1. 检查后端健康状态：`curl http://localhost:8000/api/health`
2. 检查前端代理配置：`docker compose exec frontend cat /etc/nginx/conf.d/default.conf`
3. 检查防火墙与端口占用。

### 照片不显示

1. 确认 `PHOTOS_PATH` 指向正确目录。
2. 确认目录中存在支持的图片或视频。
3. 进入容器检查挂载：`docker compose exec backend ls /photos`
4. 登录后在管理后台触发扫描。

支持格式：JPEG / PNG / WebP / GIF / MP4 / MOV / WebM / AVI / MKV。

### 重置数据库

```bash
docker compose down
rm -f data/dk_photo.sqlite3
bash deploy.sh
```

重置后会重新进入初始管理员配置流程。
