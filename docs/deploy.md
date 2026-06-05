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
4. 配置应用数据目录、端口等部署参数。
5. 首次部署时初始化管理员显示名称、邮箱和密码。
6. 自动生成 `DK_PHOTO_SECRET_KEY`。
7. 创建数据目录。
8. 检查端口占用；如果默认端口被占用，提示输入新的宿主机端口并写回 `.env`。
9. 构建并启动服务。

照片目录可以在部署完成后运行 `bash deploy.sh photos` 添加。脚本支持多个宿主机目录，并统一挂载到容器内 `/photos/<名称>`。挂载只负责让后端能访问目录，不会自动创建图库或扫描。

> 自动安装 Docker 需要服务器能访问外网，并且当前用户具有 `sudo` 权限。非 Ubuntu/Debian 系统需要先手动安装 Docker 与 Compose 插件。

## 首次部署交互项

首次部署且数据库尚不存在时，脚本会提示输入：

- 管理员显示名称：写入 `DK_PHOTO_ADMIN_NAME`
- 管理员邮箱：写入 `DK_PHOTO_ADMIN_EMAIL`
- 管理员密码：写入 `DK_PHOTO_ADMIN_PASSWORD`

密码可以留空，脚本会自动生成强密码并在部署完成后显示一次，同时保存到 `.env`。

如果 `APP_DATA_PATH/dk_photo.sqlite3` 已存在，脚本不会用 `.env` 覆盖已有管理员。已有账号请在应用后台修改。

## 配置照片目录挂载

Docker 容器不能直接访问宿主机任意目录，必须通过 volume 映射。部署完成后运行：

```bash
bash deploy.sh photos
```

进入照片目录挂载管理器后，可以添加、删除、列出、检查并应用挂载。添加目录时输入宿主机真实目录和容器内显示名称：

```text
宿主机照片目录: /mnt/nas/travel
容器内显示名称 [/photos/travel]:
```

脚本会维护 `.dk-photo-photo-mounts`，并自动生成 `docker-compose.photos.yml`：

```yaml
services:
  backend:
    volumes:
      - type: bind
        source: /mnt/nas/travel
        target: /photos/travel
        read_only: true
```

因此管理后台的文件浏览器里应选择容器内路径 `/photos/travel`，而不是宿主机路径 `/mnt/nas/travel`。`/photos` 是 Docker 挂载入口，不要直接添加为图库。

挂载管理器只检查目录是否存在和当前用户是否可读，不会递归扫描照片。照片和视频索引由登录后的管理后台扫描任务完成。

## 手动部署

```bash
cp .env.example .env
nano .env
docker compose up -d --build
docker compose ps
```

打开 `http://<服务器IP>:8080`，使用 `.env` 中配置的管理员账号登录。

如果需要照片目录挂载，推荐仍使用 `bash deploy.sh photos` 生成 `docker-compose.photos.yml`，然后用脚本显示的 Compose 命令启动或重启服务。

## 部署后访问相册

部署成功后，可以通过以下地址访问 DK Photo 相册页面：

### 本机访问

如果服务器有桌面环境，可以直接在服务器上打开：

```
http://localhost:8080
```

### 局域网访问（内网）

同一局域网内的其他设备可以通过服务器的局域网 IP 访问。部署脚本会自动检测并显示局域网 IP，也可以通过以下命令手动查看：

```bash
ip -4 route get 1 | awk '{print $7; exit}'
# 或
hostname -I | awk '{print $1}'
```

假设服务器局域网 IP 为 `192.168.1.100`，访问地址为：

```
http://192.168.1.100:8080
```

> 如果无法访问，请检查服务器防火墙是否放行了 `8080` 端口：`sudo ufw allow 8080`

### 公网访问（外网）

如果希望通过外网访问，需要满足以下条件：

1. **服务器有公网 IP**：部署脚本会自动检测并显示公网 IP，也可以运行 `curl ifconfig.me` 查看。
2. **路由器端口转发**：在路由器中将公网 IP 的 `8080` 端口转发到服务器内网 IP 的 `8080` 端口。
3. **防火墙放行**：确保服务器和路由器的防火墙都放行了 `8080` 端口。

```bash
# 查看公网 IP
curl ifconfig.me
```

公网访问地址示例：

```
http://203.0.113.50:8080
```

### 通过反向代理配置域名 + HTTPS（推荐）

生产环境强烈建议使用 Nginx/Caddy/Traefik 等反向代理，配置 SSL 证书启用 HTTPS，并通过域名访问。详见 [HTTPS 反向代理](#https-反向代理) 章节。

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|------|------|
| `DK_PHOTO_ADMIN_NAME` | 是 | `Administrator` | 初始管理员显示名称，仅首次建库时生效 |
| `DK_PHOTO_ADMIN_EMAIL` | 是 | `admin@example.com` | 初始管理员邮箱，仅首次建库时生效 |
| `DK_PHOTO_ADMIN_PASSWORD` | 是 | `change-me-now` | 初始管理员密码，仅首次建库时生效，生产环境务必修改 |
| `DK_PHOTO_SECRET_KEY` | 是 | 自动生成 | JWT 签名密钥 |
| `DK_PHOTO_DATA_DIR` | 否 | `/app/data` | 容器内数据目录 |
| `DK_PHOTO_DEFAULT_LIBRARY_PATH` | 否 | 空 | 默认图库路径；Docker 部署不建议设置，避免把 `/photos` 挂载根目录当作图库 |
| `DK_PHOTO_DEFAULT_LIBRARY_NAME` | 否 | `Family Photos` | 默认图库名称 |
| `DK_PHOTO_CORS_ORIGINS` | 否 | `http://localhost:5173,http://localhost:8080` | 允许的跨域来源 |
| `DK_PHOTO_WATCH_ENABLED` | 否 | `true` | 是否启用文件监控自动扫描 |
| `DK_PHOTO_ACCESS_TOKEN_MINUTES` | 否 | `10080` | JWT 过期时间，单位分钟 |
| `APP_DATA_PATH` | 否 | `./data` | 宿主机数据目录 |
| `FRONTEND_BIND` | 否 | `0.0.0.0` | 前端监听地址 |
| `FRONTEND_PORT` | 否 | `8080` | 前端宿主机端口 |
| `BACKEND_BIND` | 否 | `127.0.0.1` | 后端监听地址，默认仅本机 |
| `BACKEND_PORT` | 否 | `8000` | 后端宿主机端口 |
| `NPM_REGISTRY` | 否 | `https://registry.npmjs.org/` | 前端 Docker 构建时使用的 npm registry |

`BACKEND_PORT` 只影响宿主机直接访问后端的端口，例如 `http://localhost:8001/docs`。前端容器内的 `/api` 代理仍通过 Docker 网络访问 `backend:8000`，因此修改 `BACKEND_PORT` 不会破坏前端访问后端。

照片目录不再通过 `.env` 的单个 `PHOTOS_PATH` 配置。请使用 `bash deploy.sh photos` 管理多个照片目录挂载。挂载完成后仍需在管理后台手动添加具体子目录为图库，例如 `/photos/travel`。

如果构建时经常出现 npm 包下载超时，可以在 `.env` 中改为：

```env
NPM_REGISTRY=https://registry.npmmirror.com
```

## 目录结构

部署后的常见目录布局：

```text
DK_Photo/
├── .env
├── docker-compose.yml
├── docker-compose.photos.yml
├── .dk-photo-photo-mounts
├── deploy.sh
├── data/
│   ├── dk_photo.sqlite3
│   └── thumbnails/
├── backend/
└── frontend/
```

在 `docker-compose.yml` 中：

- `${APP_DATA_PATH}` 挂载到 `/app/data`，用于数据库和缩略图，读写。
- 照片目录挂载由 `docker-compose.photos.yml` 追加到 backend 服务，统一位于容器内 `/photos/<名称>`，只读。`/photos` 本身只是挂载根目录，不会作为图库扫描。

## 挂载多个照片目录

运行 `bash deploy.sh photos`，选择“添加目录”，为每个宿主机目录指定一个容器内显示名称：

```text
/mnt/nas/family  -> /photos/family
/mnt/nas/travel  -> /photos/travel
/media/disk/raw  -> /photos/raw
```

应用挂载并重建后端容器后，在管理后台通过文件浏览器选择对应容器内路径添加图库。不要直接选择 `/photos`，否则等同于尝试把所有挂载目录作为一个根图库。不要手动修改主 `docker-compose.yml`；升级时它应保持为项目提供的基础编排文件。

## 日常管理

```bash
docker compose ps
docker compose logs -f
docker compose logs -f backend
docker compose restart
docker compose down
docker compose up -d --build
```

如果已经生成 `docker-compose.photos.yml`，请使用 `bash deploy.sh config` 显示的完整 Compose 命令，例如 `docker compose -f docker-compose.yml -f docker-compose.photos.yml ...`。如果脚本提示当前用户需要 `sudo docker`，命令也相应改成 `sudo docker compose ...`。

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
bash deploy.sh deploy
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

1. 运行 `bash deploy.sh photos`，检查宿主机目录是否存在且可读。
2. 进入容器检查挂载：`docker compose exec backend ls /photos`
3. 在管理后台选择容器内路径，例如 `/photos/travel`。
4. 登录后在管理后台触发扫描。

支持格式：JPEG / PNG / WebP / GIF / MP4 / MOV / WebM / AVI / MKV。

### 重置数据库

```bash
docker compose down
rm -f data/dk_photo.sqlite3
bash deploy.sh
```

重置后会重新进入初始管理员配置流程。
