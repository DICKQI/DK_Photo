# DK Photo

DK Photo is a self-hosted family photo library built with Vue 3 and FastAPI. It indexes a configured photo folder in read-only mode, keeps metadata and thumbnails in an app data directory, and presents the library primarily through a folder view inspired by Synology Photos.

## Features

- Folder-first browsing with nested folders and responsive photo grids.
- Read-only indexing of JPEG, PNG, WebP, and GIF files.
- SQLite metadata database and Pillow-generated thumbnails.
- Real-time filesystem watching with manual scan fallback.
- Built-in admin/member accounts.
- Full user management with per-library view/share permissions.
- Admin-only server filesystem browser for choosing library folders.
- Expiring public share links for folders or individual photos.
- Docker Compose deployment with read-only photo volume mounting.

HEIC/HEIF, RAW, video, AI search, face recognition, map views, and original-file management are intentionally out of scope for the first version.

## Quick Start

1. Copy `.env.example` to `.env`.
2. Set `PHOTOS_PATH` to the host folder that contains your photos.
3. Change `DK_PHOTO_ADMIN_EMAIL`, `DK_PHOTO_ADMIN_PASSWORD`, and `DK_PHOTO_SECRET_KEY`.
4. Start the app:

```powershell
docker compose up --build
```

Open `http://localhost:8080`, sign in with the admin account, and use the Admin page to scan the default library or add another mounted folder.

The folder picker shows directories visible to the backend process. In Docker, that means container paths such as `/photos`; mount host folders in `docker-compose.yml` before selecting them.

## Local Development

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend
pnpm install
pnpm run dev
```

The Vite dev server proxies `/api` requests to `http://localhost:8000`.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DK_PHOTO_ADMIN_EMAIL` | `admin@example.com` | Initial administrator email. |
| `DK_PHOTO_ADMIN_PASSWORD` | `change-me-now` | Initial administrator password. |
| `DK_PHOTO_SECRET_KEY` | development value | JWT signing secret. Change it before real use. |
| `DK_PHOTO_DATA_DIR` | `./data` | SQLite database, thumbnails, and logs. |
| `DK_PHOTO_DEFAULT_LIBRARY_PATH` | empty | Optional library path created on first boot if it exists. |
| `DK_PHOTO_CORS_ORIGINS` | localhost origins | Allowed browser origins. |
| `DK_PHOTO_WATCH_ENABLED` | `true` | Enable watchdog-based library monitoring. |

## API Overview

- `POST /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/logout`
- `GET /api/folders`, `GET /api/folders/{id}`
- `GET /api/assets`, `GET /api/assets/{id}`, `GET /api/assets/{id}/original`
- `GET /api/assets/{id}/thumbnail?size=small|medium|large`
- `GET/POST /api/admin/libraries`, `POST /api/admin/libraries/{id}/scan`
- `GET /api/admin/filesystem/roots`, `GET /api/admin/filesystem/children?path=...`
- `GET /api/admin/jobs`, `GET/POST/PATCH /api/admin/users`, user enable/disable/password/permission endpoints, `GET /api/admin/shares`
- `POST /api/shares`
- `GET /api/public/shares/{token}`, `GET /api/public/shares/{token}/assets`

## Tests

```powershell
cd backend
pytest
```

Frontend checks:

```powershell
cd frontend
pnpm type-check
pnpm test:unit
```
