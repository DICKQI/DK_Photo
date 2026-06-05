# DK Photo

DK Photo 是一个自托管的私有家庭相册中心，基于 Vue 3 和 FastAPI 构建。它以只读方式索引配置的照片文件夹，将元数据和缩略图保存在应用数据目录中，并以文件夹视图为核心呈现照片库，操作体验类似群晖 Synology Photos。

## 功能特性

- **文件夹优先浏览**：支持多级嵌套文件夹，响应式照片网格布局，面包屑导航。
- **只读索引**：支持 JPEG、PNG、WebP、GIF 图片及 MP4、MOV、WebM、AVI、MKV 视频，不修改原始文件。
- **SQLite 元数据库**：使用 SQLModel ORM 管理索引数据，Pillow 生成 WebP 缩略图（320px / 720px / 1440px 三档）。
- **EXIF 信息提取**：自动提取相机型号、镜头、ISO、光圈、快门、焦距、GPS 坐标等元数据。
- **实时文件监控**：基于 watchdog 监测文件系统变化，自动触发增量扫描。
- **手动扫描任务**：管理员可随时触发指定图库的扫描任务，查看扫描状态和历史。
- **内建用户系统**：管理员 (admin) / 成员 (member) 两种角色，支持多用户。
- **图库权限管理**：可为每个成员单独分配图库的查看和分享权限，管理员可访问所有图库。
- **完整用户管理**：创建/启用/禁用用户、重置密码、修改角色和信息。
- **文件系统浏览器**：管理员可在页面上浏览服务器目录（支持 Windows 盘符和 Linux 挂载点），选择新增图库路径。
- **私密分享链接**：支持分享单张照片、整个文件夹或多选照片，可设置过期时间（1~365 天或永不过期），可随时撤销。
- **批量操作**：进入选择模式后可多选照片，支持批量添加/移除标签、批量收藏、批量下载 ZIP、批量分享、批量加入/移出相册。
- **用户相册**：创建、编辑、删除个人相册，添加/移除照片，设置封面。
- **智能浏览视图**：全部照片、最近添加、视频、地点、收藏、按标签/评分/相机/镜头筛选。
- **照片查看器**：全屏灯箱，支持键盘前后翻页、缩放、旋转、幻灯片放映、EXIF 信息面板。
- **个人元数据**：支持为照片添加标签、描述、评分（1-5 星）、收藏，每个用户独立维护。
- **标签管理**：支持标签搜索、重命名、删除，自动汇总各标签下的照片数量。
- **评分筛选**：按评分筛选照片，自动累计（如 4 星显示所有 4 星及以上的照片）。
- **相机/镜头筛选**：自动从 EXIF 中汇总相机和镜头型号，按数量排序，支持点击筛选。
- **地点聚类**：将 GPS 坐标精确到小数点后两位进行聚类，展示各地点的照片数量和最新封面。
- **右键快捷操作**：在文件夹上右键可更改封面或重命名文件夹。
- **暗色/亮色主题**：支持一键切换，自动跟随系统偏好。
- **中英文双语界面**：支持简体中文和英文切换，覆盖全部 UI 文本。
- **Docker Compose 部署**：前端 Nginx 静态托管 + 后端 Uvicorn，开箱即用。

## 快速开始

推荐使用交互式部署脚本：

```bash
bash deploy.sh
```

首次部署时脚本会创建 `.env`、初始化管理员显示名称/邮箱/密码、生成 `DK_PHOTO_SECRET_KEY`，并通过 Docker Compose 构建启动服务。
首次部署可以先不配置照片目录。部署完成后运行 `bash deploy.sh photos`，把一个或多个宿主机照片目录挂载到容器内的 `/photos/<名称>`。

也可以手动复制 `.env.example` 为 `.env` 后运行：

```powershell
docker compose up -d --build
```

打开 `http://localhost:8080`，使用管理员账号登录。登录后进入管理页面对默认图库进行扫描，或添加其他挂载的文件夹。

> 文件夹选择器显示的是后端进程可见的目录。在 Docker 环境中，这些是容器内路径（如 `/photos/travel`）；请先运行 `bash deploy.sh photos` 挂载宿主机目录，再在管理页选择对应的容器路径。添加图库时设置的名称会作为此图库根文件夹的名称。

## Docker 照片目录挂载

Docker 容器不能直接访问宿主机任意目录。使用脚本的照片目录挂载管理器添加目录：

```bash
bash deploy.sh photos
```

脚本会维护 `.dk-photo-photo-mounts` 并生成 `docker-compose.photos.yml`。例如宿主机目录 `/mnt/nas/travel` 可以映射为容器内 `/photos/travel`。后台添加图库时请选择 `/photos/travel`，不要填写宿主机路径。

挂载管理只检查目录是否存在和可读，不会递归扫描照片；索引由登录后的管理后台扫描任务完成。

## 本地开发

后端启动：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

前端启动：

```powershell
cd frontend
pnpm install
pnpm run dev
```

Vite 开发服务器会将 `/api` 请求代理到 `http://localhost:8000`。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DK_PHOTO_ADMIN_NAME` | `Administrator` | 初始管理员显示名称，仅首次建库时生效 |
| `DK_PHOTO_ADMIN_EMAIL` | `admin@example.com` | 初始管理员邮箱 |
| `DK_PHOTO_ADMIN_PASSWORD` | `change-me-now` | 初始管理员密码，请务必修改 |
| `DK_PHOTO_SECRET_KEY` | 开发默认值 | JWT 签名密钥，正式使用前务必修改 |
| `DK_PHOTO_DATA_DIR` | `/app/data` | SQLite 数据库、缩略图的存储目录 |
| `DK_PHOTO_DEFAULT_LIBRARY_PATH` | `/photos` | 启动时若此路径存在则自动创建为默认图库 |
| `DK_PHOTO_DEFAULT_LIBRARY_NAME` | `Family Photos` | 自动创建图库时的名称 |
| `DK_PHOTO_CORS_ORIGINS` | `http://localhost:5173,http://localhost:8080` | 允许的 CORS 来源，逗号分隔 |
| `DK_PHOTO_WATCH_ENABLED` | `true` | 是否启用 watchdog 文件监控自动扫描 |
| `APP_DATA_PATH` | `./data` | Docker 宿主机数据目录 |
| `FRONTEND_BIND` | `0.0.0.0` | 前端监听地址 |
| `FRONTEND_PORT` | `8080` | 前端宿主机端口 |
| `BACKEND_BIND` | `127.0.0.1` | 后端监听地址，默认仅本机 |
| `BACKEND_PORT` | `8000` | 后端宿主机端口 |
| `NPM_REGISTRY` | `https://registry.npmjs.org/` | 前端 Docker 构建时使用的 npm registry |

## API 概览

| 分组 | 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- | --- |
| 认证 | `POST` | `/api/auth/login` | 无 | 登录 |
| | `GET` | `/api/auth/me` | 用户 | 当前用户信息 |
| | `POST` | `/api/auth/logout` | 无 | 退出登录 |
| 文件夹 | `GET` | `/api/folders` | 用户 | 列出文件夹 |
| | `GET` | `/api/folders/{id}` | 用户 | 文件夹详情（含祖先链） |
| | `PATCH` | `/api/folders/{id}/cover` | 管理员 | 更改文件夹封面 |
| | `PATCH` | `/api/folders/{id}/rename` | 管理员 | 重命名文件夹 |
| 资源 | `GET` | `/api/assets` | 用户 | 列出/搜索/筛选资源 |
| | `GET` | `/api/assets/tags` | 用户 | 列出所有标签及数量 |
| | `GET` | `/api/assets/ratings` | 用户 | 列出评分分布 |
| | `GET` | `/api/assets/cameras` | 用户 | 列出相机型号 |
| | `GET` | `/api/assets/lenses` | 用户 | 列出镜头型号 |
| | `GET` | `/api/assets/places` | 用户 | 列出地点聚类 |
| | `POST` | `/api/assets/bulk-tags` | 用户 | 批量添加标签 |
| | `POST` | `/api/assets/bulk-tags/remove` | 用户 | 批量移除标签 |
| | `PATCH` | `/api/assets/tags/{name}` | 用户 | 重命名标签 |
| | `DELETE` | `/api/assets/tags/{name}` | 用户 | 删除标签 |
| | `GET` | `/api/assets/{id}` | 用户 | 资源详情 |
| | `PATCH` | `/api/assets/{id}/favorite` | 用户 | 切换收藏 |
| | `PATCH` | `/api/assets/{id}/metadata` | 用户 | 更新描述和评分 |
| | `PATCH` | `/api/assets/{id}/tags` | 用户 | 替换全部标签 |
| | `POST` | `/api/assets/download` | 用户 | 批量下载 ZIP |
| | `GET` | `/api/assets/{id}/original` | 用户 | 下载原文件 |
| | `GET` | `/api/assets/{id}/thumbnail` | 用户 | 获取缩略图 |
| 相册 | `GET` | `/api/albums` | 用户 | 列出我的相册 |
| | `POST` | `/api/albums` | 用户 | 创建相册 |
| | `GET` | `/api/albums/{id}` | 用户 | 相册详情 |
| | `PATCH` | `/api/albums/{id}` | 用户 | 更新相册名称/描述 |
| | `PATCH` | `/api/albums/{id}/cover` | 用户 | 设置相册封面 |
| | `GET` | `/api/albums/{id}/assets` | 用户 | 列出相册内资源 |
| | `POST` | `/api/albums/{id}/assets` | 用户 | 添加资源到相册 |
| | `DELETE` | `/api/albums/{id}/assets` | 用户 | 从相册移除资源 |
| | `DELETE` | `/api/albums/{id}` | 用户 | 删除相册 |
| 分享 | `POST` | `/api/shares` | 用户 | 创建分享链接 |
| | `GET` | `/api/shares` | 用户 | 列出我的分享 |
| | `PATCH` | `/api/shares/{id}` | 用户 | 更新分享 |
| | `DELETE` | `/api/shares/{id}` | 用户 | 撤销分享 |
| | `GET` | `/api/public/shares/{token}` | 无 | 公开分享元数据 |
| | `GET` | `/api/public/shares/{token}/assets` | 无 | 列出分享的资源 |
| | `GET` | `/api/public/shares/{token}/download` | 无 | 下载分享 ZIP |
| | `GET` | `/api/public/shares/{token}/assets/{id}/original` | 无 | 从分享下载原图 |
| | `GET` | `/api/public/shares/{token}/assets/{id}/thumbnail` | 无 | 从分享获取缩略图 |
| 管理 | `GET` | `/api/admin/libraries` | 管理员 | 列出图库 |
| | `POST` | `/api/admin/libraries` | 管理员 | 创建图库 |
| | `PATCH` | `/api/admin/libraries/{id}` | 管理员 | 更新图库名称 |
| | `DELETE` | `/api/admin/libraries/{id}` | 管理员 | 删除图库及数据 |
| | `POST` | `/api/admin/libraries/{id}/scan` | 管理员 | 触发扫描 |
| | `GET` | `/api/admin/jobs` | 管理员 | 查看扫描任务（最近40个） |
| | `GET` | `/api/admin/users` | 管理员 | 列出用户 |
| | `GET` | `/api/admin/users/{id}` | 管理员 | 获取用户详情 |
| | `POST` | `/api/admin/users` | 管理员 | 创建用户 |
| | `PATCH` | `/api/admin/users/{id}` | 管理员 | 更新用户 |
| | `POST` | `/api/admin/users/{id}/password` | 管理员 | 重置密码 |
| | `POST` | `/api/admin/users/{id}/disable` | 管理员 | 禁用用户 |
| | `POST` | `/api/admin/users/{id}/enable` | 管理员 | 启用用户 |
| | `GET` | `/api/admin/users/{id}/permissions` | 管理员 | 查看用户图库权限 |
| | `PUT` | `/api/admin/users/{id}/permissions` | 管理员 | 更新用户图库权限 |
| | `GET` | `/api/admin/shares` | 管理员 | 列出所有分享链接 |
| | `PATCH` | `/api/admin/shares/{id}` | 管理员 | 更新任意分享链接 |
| | `DELETE` | `/api/admin/shares/{id}` | 管理员 | 撤销任意分享链接 |
| | `GET` | `/api/admin/filesystem/roots` | 管理员 | 列出文件系统根目录 |
| | `GET` | `/api/admin/filesystem/children` | 管理员 | 浏览子目录 |
| 健康 | `GET` | `/api/health` | 无 | 健康检查 |

完整的请求/响应格式和参数说明请参阅 [api.md](./api.md)。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端框架 | Vue 3.5 + TypeScript + Vite |
| 前端路由 | vue-router 4 |
| 前端图标 | lucide-vue-next |
| 后端框架 | FastAPI 0.115 |
| ORM | SQLModel 0.0.22 (SQLAlchemy + Pydantic) |
| 数据库 | SQLite |
| 认证 | JWT (PyJWT) + bcrypt (passlib) |
| 图像处理 | Pillow 11.1 |
| 文件监控 | watchdog 6.0 |
| 部署 | Docker Compose (Nginx + Uvicorn) |

## 项目结构

```
DK_Photo/
├── .env.example              # 环境变量模板
├── docker-compose.yml        # Docker 部署编排
├── README.md                 # 项目说明
├── api.md                    # API 详细文档
├── data/                     # 运行时数据（SQLite、缩略图）
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py           # FastAPI 入口
│   │   ├── config.py         # 配置管理
│   │   ├── db.py             # 数据库引擎和迁移
│   │   ├── models.py         # SQLModel 数据模型
│   │   ├── schemas.py        # Pydantic 请求/响应模型
│   │   ├── deps.py           # 依赖注入（认证、权限）
│   │   ├── security.py       # 密码哈希、JWT
│   │   ├── api/              # API 路由
│   │   │   ├── auth.py       # 认证接口
│   │   │   ├── folders.py    # 文件夹接口
│   │   │   ├── assets.py     # 资源接口
│   │   │   ├── albums.py     # 相册接口
│   │   │   ├── shares.py     # 分享接口
│   │   │   └── admin.py      # 管理接口
│   │   └── services/         # 业务服务
│   │       ├── scanner.py    # 扫描索引
│   │       ├── thumbnails.py # 缩略图生成
│   │       ├── filesystem.py # 文件系统浏览
│   │       ├── permissions.py# 权限控制
│   │       ├── paths.py      # 路径安全
│   │       └── watcher.py    # 文件监控
│   └── tests/
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── App.vue
        ├── main.ts
        ├── router.ts
        ├── types.ts
        ├── styles.css          # ~4900 行完整设计系统
        ├── components/         # 通用组件
        ├── composables/        # 组合式函数
        ├── services/           # API 客户端
        └── views/              # 页面视图
```

## 测试

后端测试：

```powershell
cd backend
pytest
```

前端检查：

```powershell
cd frontend
pnpm type-check
pnpm test:unit
```
