# 🐳 Docker Deployment

This project supports Docker deployment with multi-container orchestration using Docker Compose.

## Quick Start

```bash
# 1. Configure environment variables
cp backend/.env.example backend/.env
# Edit backend/.env with your API credentials

# 2. Build and run
docker-compose up -d

# 3. Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:5000
```

## What's Included

- **Backend**: Flask API with Python 3.11
- **Frontend**: React app served with nginx
- **Database**: SQLite with persistent volume storage
- **Networking**: Internal Docker network for service communication

## Files Overview

```
├── docker-compose.yml          # Multi-container orchestration
├── backend/
│   ├── Dockerfile             # Backend container definition
│   ├── .dockerignore          # Build context exclusions
│   ├── .env.example           # Environment template
│   └── .env.production        # Production config template
└── frontend/
    ├── Dockerfile             # Frontend container definition (multi-stage)
    ├── .dockerignore          # Build context exclusions
    ├── nginx.conf             # nginx web server config
    └── .env.example           # Environment template
```

## Environment Configuration

### Backend (.env)
```env
SECRET_KEY=your-secret-key-here
KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret
```

### Security Notes
- Never commit `.env` files (already in `.gitignore`)
- Use `.env.example` as a template
- Generate strong `SECRET_KEY` for production

## Common Commands

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild after code changes
docker-compose up -d --build

# Access backend container
docker-compose exec backend bash
```

## Production Deployment

For production:
1. Use `.env.production` as template
2. Set `FLASK_DEBUG=False`
3. Generate secure `SECRET_KEY`
4. Configure proper CORS origins
5. Use HTTPS with reverse proxy

## Troubleshooting

**Port conflicts**: Edit ports in `docker-compose.yml`
**Database issues**: Check volume mounts and permissions
**Build failures**: Ensure all dependencies are in `requirements.txt`

For detailed documentation, see the deployment guide.

## Architecture

```
┌──────────────┐      ┌──────────────┐
│   Frontend   │─────▶│   Backend    │
│ (React+Nginx)│      │   (Flask)    │
│   Port: 3000 │      │  Port: 5000  │
└──────────────┘      └──────┬───────┘
                             │
                      ┌──────▼───────┐
                      │  SQLite DB   │
                      │   (Volume)   │
                      └──────────────┘
```
