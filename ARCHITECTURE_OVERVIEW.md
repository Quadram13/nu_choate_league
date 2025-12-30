# Nu Choate League - Architecture Overview

## System Flow

### Current State (Temporary)
```
Sleeper API → Local Python Scripts → JSON Files → Static HTML → GitHub Pages
   (Manual)      (Manual)            (Static)      (Pre-gen)     (View only)
```

### Target State (Production)
```
Sleeper API → Scheduled Jobs → MongoDB → FastAPI → Modern Frontend → Users
   (Auto)        (Auto)          (Live)    (API)      (Interactive)   (Dynamic)
```

## Architecture Layers

### 1. Data Layer (MongoDB)
- **Location**: Arch Linux server (ThinkPad X1)
- **Databases**: `nu_choate_league_dev`, `nu_choate_league_staging`, `nu_choate_league_prod`
- **Service**: systemd service `mongodb.service`

### 2. Backend Layer (FastAPI)
- **Location**: Arch Linux server (systemd services)
- **Staging**: Port 8001
- **Production**: Port 8000
- **Functions**: REST API endpoints, scheduled jobs (systemd timers), data processing

### 3. Frontend Layer (Modern SPA)
- **Location**: nginx reverse proxy on Arch Linux
- **Features**: Interactive dashboard, real-time stats, visualizations

## Environment Separation

### Development
- Database: `nu_choate_league_dev`
- Backend: Local (port 8000)
- Frontend: Local dev server

### Staging
- Database: `nu_choate_league_staging`
- Backend: systemd service (port 8001)
- Frontend: nginx virtual host

### Production
- Database: `nu_choate_league_prod`
- Backend: systemd service (port 8000)
- Frontend: nginx virtual host

## Migration Roadmap

### Phase 1: Backend & Database Setup
1. Install and configure MongoDB
2. Create three databases (dev, staging, prod)
3. Migrate existing JSON data to MongoDB
4. Build FastAPI backend with core endpoints
5. Set up systemd services for staging and production
6. Configure nginx reverse proxy

**Deliverable**: Working API that serves league data

### Phase 2: Frontend Development
1. Choose frontend framework (React/Vue/Svelte)
2. Build dashboard components
3. Connect to FastAPI endpoints
4. Deploy via nginx

**Deliverable**: Production-ready web application

### Phase 3: Automation & Polish
1. Set up systemd timers for scheduled data updates
2. Implement error handling and monitoring
3. Performance optimization

**Deliverable**: Fully automated, production-ready system

## Technology Stack

- **Server**: Arch Linux on ThinkPad X1 (i7-10710U, 16GB RAM)
- **Database**: MongoDB (systemd service)
- **Backend**: FastAPI (Python, systemd services)
- **Frontend**: TBD (React/Vue/Svelte, served via nginx)
- **Web Server**: nginx (reverse proxy)
- **Scheduling**: systemd timers

## Cost

- **Hardware**: $0 (existing ThinkPad X1)
- **Electricity**: ~$5-10/month (24/7 operation)
- **Total**: ~$5-10/month

## Next Steps

See `BACKEND_DATABASE_PHASE.md` for detailed Phase 1 implementation guide.
