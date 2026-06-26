# Windows Intranet Deployment Guide

This guide documents the validated Windows deployment used to publish BMSC AI Video on an intranet VM with NSSM and Nginx.

The target layout is:

```text
D:\BMSC-AI-Video\
├── backend\
│   └── .venv\
├── frontend\
└── logs\
```

The public URL is served by Nginx on a dedicated port, for example:

```text
http://172.28.18.120:8081
```

## Runtime Ports

Use these ports unless the VM requires different values:

| Component | Bind address | Port | Public access |
|---|---:|---:|---|
| Nginx | `0.0.0.0` | `8081` | Yes |
| Frontend Vite preview | `127.0.0.1` / `0.0.0.0` | `4173` | Through Nginx |
| Backend FastAPI | `127.0.0.1` | `3001` | Through Nginx `/api/` |

The backend and frontend ports do not need to be exposed in the firewall when Nginx runs on the same VM.

## Backend Service

The backend must be executed with the Python virtual environment located inside the backend folder:

```text
D:\BMSC-AI-Video\backend\.venv\Scripts\python.exe
```

Install or configure the NSSM service with:

```powershell
nssm install BMSCAIVideoBackend
```

Use these NSSM values:

```text
Path:
D:\BMSC-AI-Video\backend\.venv\Scripts\python.exe

Startup directory:
D:\BMSC-AI-Video\backend

Arguments:
-m uvicorn app.main:app --host 127.0.0.1 --port 3001
```

Configure backend logs:

```powershell
nssm set BMSCAIVideoBackend AppStdout D:\BMSC-AI-Video\logs\backend.log
nssm set BMSCAIVideoBackend AppStderr D:\BMSC-AI-Video\logs\backend-err.log
nssm set BMSCAIVideoBackend AppRotateFiles 1
nssm set BMSCAIVideoBackend AppRotateOnline 1
nssm set BMSCAIVideoBackend AppRotateBytes 10485760
```

Validate the backend locally:

```powershell
curl http://127.0.0.1:3001/health
```

Expected response:

```json
{"status":"ok"}
```

## Frontend Service

Before running the frontend service, configure the API base URL in:

```text
D:\BMSC-AI-Video\frontend\.env
```

For the Nginx deployment on port `8081`, use:

```env
VITE_API_BASE_URL=http://172.28.18.120:8081/api
```

Build the frontend after changing `.env`:

```powershell
cd D:\BMSC-AI-Video\frontend
npm install
npm run build
```

Install or configure the NSSM service:

```powershell
nssm install BMSCAIVideoFrontend
```

Use these NSSM values:

```text
Path:
C:\Program Files\nodejs\npm.cmd

Startup directory:
D:\BMSC-AI-Video\frontend

Arguments:
run preview
```

Configure frontend logs:

```powershell
nssm set BMSCAIVideoFrontend AppStdout D:\BMSC-AI-Video\logs\frontend.log
nssm set BMSCAIVideoFrontend AppStderr D:\BMSC-AI-Video\logs\frontend-err.log
nssm set BMSCAIVideoFrontend AppRotateFiles 1
nssm set BMSCAIVideoFrontend AppRotateOnline 1
nssm set BMSCAIVideoFrontend AppRotateBytes 10485760
```

Validate the frontend locally:

```powershell
curl http://127.0.0.1:4173
```

## Log Files

Create the log directory and files if they do not exist:

```powershell
New-Item -ItemType Directory -Force D:\BMSC-AI-Video\logs

New-Item -ItemType File -Force D:\BMSC-AI-Video\logs\backend.log
New-Item -ItemType File -Force D:\BMSC-AI-Video\logs\backend-err.log
New-Item -ItemType File -Force D:\BMSC-AI-Video\logs\frontend.log
New-Item -ItemType File -Force D:\BMSC-AI-Video\logs\frontend-err.log
New-Item -ItemType File -Force D:\BMSC-AI-Video\logs\nginx-access.log
New-Item -ItemType File -Force D:\BMSC-AI-Video\logs\nginx-error.log
```

Monitor logs:

```powershell
Get-Content D:\BMSC-AI-Video\logs\backend.log -Wait -Tail 50
Get-Content D:\BMSC-AI-Video\logs\backend-err.log -Wait -Tail 50
Get-Content D:\BMSC-AI-Video\logs\frontend.log -Wait -Tail 50
Get-Content D:\BMSC-AI-Video\logs\frontend-err.log -Wait -Tail 50
Get-Content D:\BMSC-AI-Video\logs\nginx-access.log -Wait -Tail 50
Get-Content D:\BMSC-AI-Video\logs\nginx-error.log -Wait -Tail 50
```

## Nginx Configuration

If another system already uses port `80`, keep that server block unchanged and add a new server block for BMSC AI Video on a different port, such as `8081`.

Example complete Nginx configuration:

```nginx
worker_processes 1;

events {
    worker_connections 1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;
    sendfile      on;

    # Existing system on port 80.
    server {
        listen 80;
        server_name 172.28.18.120;

        client_max_body_size 500M;

        location / {
            proxy_pass         http://127.0.0.1:3000;
            proxy_http_version 1.1;
            proxy_set_header   Upgrade $http_upgrade;
            proxy_set_header   Connection 'upgrade';
            proxy_set_header   Host $host;
            proxy_cache_bypass $http_upgrade;
        }

        location /api/ {
            proxy_pass         http://127.0.0.1:8000;
            proxy_http_version 1.1;
            proxy_set_header   Host $host;
            proxy_set_header   X-Real-IP $remote_addr;
            proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;

            proxy_buffering    off;
            proxy_cache        off;
            add_header         X-Accel-Buffering no;

            proxy_read_timeout     300s;
            proxy_connect_timeout   75s;
            proxy_send_timeout     300s;
        }
    }

    # BMSC AI Video on port 8081.
    server {
        listen 8081;
        server_name 172.28.18.120;

        client_max_body_size 500M;

        access_log D:/BMSC-AI-Video/logs/nginx-access.log;
        error_log  D:/BMSC-AI-Video/logs/nginx-error.log;

        location / {
            proxy_pass         http://127.0.0.1:4173;
            proxy_http_version 1.1;
            proxy_set_header   Upgrade $http_upgrade;
            proxy_set_header   Connection 'upgrade';
            proxy_set_header   Host $host;
            proxy_cache_bypass $http_upgrade;
        }

        location /api/ {
            rewrite ^/api/(.*)$ /$1 break;
            proxy_pass         http://127.0.0.1:3001;
            proxy_http_version 1.1;
            proxy_set_header   Host $host;
            proxy_set_header   X-Real-IP $remote_addr;
            proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;

            proxy_buffering    off;
            proxy_cache        off;
            add_header         X-Accel-Buffering no;

            proxy_read_timeout     900s;
            proxy_connect_timeout   75s;
            proxy_send_timeout     900s;
        }
    }
}
```

Test the Nginx configuration:

```powershell
cd C:\nginx
.\nginx.exe -t
```

If the test succeeds, restart the existing Nginx service:

```powershell
nssm restart DocuMindNginx
```

If this VM uses a dedicated Nginx service for BMSC AI Video, restart that service instead.

## Firewall

Open the public Nginx port:

```powershell
New-NetFirewallRule -DisplayName "BMSC AI Video 8081" -Direction Inbound -Protocol TCP -LocalPort 8081 -Action Allow
```

Ports `3001` and `4173` should remain local-only when traffic is routed through Nginx.

## Service Operations

Restart services:

```powershell
nssm restart BMSCAIVideoBackend
nssm restart BMSCAIVideoFrontend
nssm restart DocuMindNginx
```

Check service status:

```powershell
nssm status BMSCAIVideoBackend
nssm status BMSCAIVideoFrontend
nssm status DocuMindNginx
```

Check NSSM executable paths:

```powershell
nssm get BMSCAIVideoBackend Application
nssm get BMSCAIVideoBackend AppDirectory
nssm get BMSCAIVideoBackend AppParameters

nssm get BMSCAIVideoFrontend Application
nssm get BMSCAIVideoFrontend AppDirectory
nssm get BMSCAIVideoFrontend AppParameters
```

## Final Validation

From the VM:

```powershell
curl http://127.0.0.1:3001/health
curl http://127.0.0.1:4173
curl http://127.0.0.1:8081/api/health
```

From another machine on the intranet:

```text
http://172.28.18.120:8081
```

Default first-start admin credentials:

```text
Email: admin@bmsc.com.bo
Password: admin123
```

Change the default password after the first login.
