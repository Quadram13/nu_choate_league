# Backend & Database Phase - Implementation Guide

## Overview

Step-by-step instructions for Phase 1: Setting up MongoDB database and FastAPI backend on Arch Linux.

**Goal**: Create a working API that serves league data from MongoDB.

**Prerequisites**: Arch Linux installed, WiFi connected, system updated, sudo access

**Automated Setup**: After completing Steps 1-2 (MongoDB installation and configuration), you can use the automated setup script to complete Steps 3-9:

```bash
# Download and run the setup script
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/nu_choate_league/main/setup_backend.sh -o setup_backend.sh
chmod +x setup_backend.sh
./setup_backend.sh
```

The script will prompt you for:
- MongoDB passwords (dev, staging, prod)
- Sleeper League ID
- JWT Secret (or generate one)
- Project directory
- GitHub username

Or follow the manual steps below.

---

## Environment Separation

Three environments on the same machine:
- **Development**: `nu_choate_league_dev` database, local backend (port 8000)
- **Staging**: `nu_choate_league_staging` database, systemd service (port 8001)
- **Production**: `nu_choate_league_prod` database, systemd service (port 8000)

Each environment has its own MongoDB user and environment variables.

---

## Step 1: Install MongoDB

```bash
# Install yay (AUR helper) if needed
sudo pacman -S --needed base-devel git
git clone https://aur.archlinux.org/yay.git
cd yay && makepkg -si && cd .. && rm -rf yay

# Install MongoDB
yay -S mongodb-bin

# Start and enable MongoDB
sudo systemctl start mongodb
sudo systemctl enable mongodb
sudo systemctl status mongodb
```

---

## Step 2: Configure MongoDB

```bash
# Create data directory
sudo mkdir -p /var/lib/mongodb
sudo chown -R mongodb:mongodb /var/lib/mongodb

# Connect to MongoDB
mongosh
```

Create admin user:
```javascript
use admin
db.createUser({
  user: "admin",
  pwd: "YOUR_SECURE_ADMIN_PASSWORD",
  roles: [
    { role: "userAdminAnyDatabase", db: "admin" },
    { role: "readWriteAnyDatabase", db: "admin" },
    { role: "dbAdminAnyDatabase", db: "admin" }
  ]
})
```

Create application users for each database:
```javascript
// Development
use nu_choate_league_dev
db.createUser({
  user: "nuchoate_app",
  pwd: "YOUR_DEV_PASSWORD",
  roles: [{ role: "readWrite", db: "nu_choate_league_dev" }]
})

// Staging
use nu_choate_league_staging
db.createUser({
  user: "nuchoate_app",
  pwd: "YOUR_STAGING_PASSWORD",
  roles: [{ role: "readWrite", db: "nu_choate_league_staging" }]
})

// Production
use nu_choate_league_prod
db.createUser({
  user: "nuchoate_app",
  pwd: "YOUR_PROD_PASSWORD",
  roles: [{ role: "readWrite", db: "nu_choate_league_prod" }]
})

exit
```

Enable authentication:
```bash
sudo nano /etc/mongodb.conf
```

Add:
```
security:
  authorization: enabled
```

Restart MongoDB:
```bash
sudo systemctl restart mongodb
```

---

## Step 3: Initial Data Sync

```bash
# Install Python dependencies (needs sudo for package install)
sudo pacman -S python python-pip

# Install Python packages (as regular user)
pip install pymongo requests

# Download script from GitHub (as regular user)
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/nu_choate_league/main/sync_sleeper_to_mongodb.py -o sync_sleeper_to_mongodb.py
chmod +x sync_sleeper_to_mongodb.py

# Sync to dev database
export MONGODB_URI="mongodb://nuchoate_app:DEV_PASSWORD@localhost:27017/nu_choate_league_dev?authSource=nu_choate_league_dev"
python sync_sleeper_to_mongodb.py --env dev

# Sync to staging database
export MONGODB_URI="mongodb://nuchoate_app:STAGING_PASSWORD@localhost:27017/nu_choate_league_staging?authSource=nu_choate_league_staging"
python sync_sleeper_to_mongodb.py --env staging

# Sync to production database (after staging verified)
export MONGODB_URI="mongodb://nuchoate_app:PROD_PASSWORD@localhost:27017/nu_choate_league_prod?authSource=nu_choate_league_prod"
python sync_sleeper_to_mongodb.py --env prod
```

**Note**: The sync script:
- Fetches data directly from Sleeper API
- Stores raw data in MongoDB
- Only processes new weeks (incremental)
- Calculates standings incrementally
- Tracks what's been processed in `metadata` collection

---

## Step 4: Install Python and Dependencies

```bash
# Install Python and tools
sudo pacman -S python python-pip python-virtualenv gcc make pkg-config

# Set up project environment
cd /path/to/nu_choate_league
python -m venv venv
source venv/bin/activate
pip install -r misc/backend/requirements.txt
pip install fastapi uvicorn[standard] motor pymongo python-dotenv pydantic pydantic-settings
```

---

## Step 5: FastAPI Backend Setup

```bash
cd misc/backend
nano .env
```

Add:
```
MONGODB_URI=mongodb://nuchoate_app:DEV_PASSWORD@localhost:27017/nu_choate_league_dev?authSource=nu_choate_league_dev
API_ENV=development
LOG_LEVEL=debug
PORT=8000
```

Test locally:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal:
```bash
curl http://localhost:8000/
curl http://localhost:8000/api/v1/leagues
```

---

## Step 6: Create systemd Services

### Staging Service

```bash
sudo nano /etc/systemd/system/nuchoate-api-staging.service
```

Add:
```ini
[Unit]
Description=Nu Choate League API - Staging
After=network.target mongodb.service

[Service]
Type=simple
User=yourusername
WorkingDirectory=/path/to/nu_choate_league/misc/backend
EnvironmentFile=/etc/nuchoate-api-staging.env
ExecStart=/path/to/nu_choate_league/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo nano /etc/nuchoate-api-staging.env
```

Add:
```
MONGODB_URI=mongodb://nuchoate_app:STAGING_PASSWORD@localhost:27017/nu_choate_league_staging?authSource=nu_choate_league_staging
API_ENV=staging
LOG_LEVEL=info
PORT=8001
```

### Production Service

```bash
sudo nano /etc/systemd/system/nuchoate-api-prod.service
```

Add:
```ini
[Unit]
Description=Nu Choate League API - Production
After=network.target mongodb.service

[Service]
Type=simple
User=yourusername
WorkingDirectory=/path/to/nu_choate_league/misc/backend
EnvironmentFile=/etc/nuchoate-api-prod.env
ExecStart=/path/to/nu_choate_league/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo nano /etc/nuchoate-api-prod.env
```

Add:
```
MONGODB_URI=mongodb://nuchoate_app:PROD_PASSWORD@localhost:27017/nu_choate_league_prod?authSource=nu_choate_league_prod
API_ENV=production
LOG_LEVEL=warning
PORT=8000
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable nuchoate-api-staging.service
sudo systemctl enable nuchoate-api-prod.service
sudo systemctl start nuchoate-api-staging.service
sudo systemctl start nuchoate-api-prod.service
```

---

## Step 7: API Testing

```bash
# Test staging
curl http://localhost:8001/
curl http://localhost:8001/api/v1/leagues

# Test production
curl http://localhost:8000/
curl http://localhost:8000/api/v1/leagues

# Check logs
sudo journalctl -u nuchoate-api-staging.service -f
sudo journalctl -u nuchoate-api-prod.service -f
```

---

## Step 8: Set Up nginx Reverse Proxy

```bash
# Install nginx
sudo pacman -S nginx

# Configure nginx
sudo nano /etc/nginx/nginx.conf
```

Add:
```nginx
http {
    upstream api_staging {
        server 127.0.0.1:8001;
    }
    
    upstream api_prod {
        server 127.0.0.1:8000;
    }
    
    server {
        listen 8080;
        server_name staging.local;
        location /api {
            proxy_pass http://api_staging;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
    
    server {
        listen 80;
        server_name localhost;
        location /api {
            proxy_pass http://api_prod;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
        location / {
            root /path/to/nu_choate_league/frontend/dist;
            try_files $uri $uri/ /index.html;
        }
    }
}
```

```bash
sudo systemctl enable nginx
sudo systemctl start nginx
```

---

## Step 9: Configure Scheduled Jobs

The sync script is at the root: `sync_sleeper_to_mongodb.py`

Download it from GitHub:
```bash
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/nu_choate_league/main/sync_sleeper_to_mongodb.py -o sync_sleeper_to_mongodb.py
chmod +x sync_sleeper_to_mongodb.py
```

Create timer:
```bash
sudo nano /etc/systemd/system/nuchoate-sync.timer
```

Add:
```ini
[Unit]
Description=Nu Choate League Data Sync Timer
Requires=nuchoate-sync.service

[Timer]
OnCalendar=daily
OnCalendar=Mon..Sun *-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Create service:
```bash
sudo nano /etc/systemd/system/nuchoate-sync.service
```

Add:
```ini
[Unit]
Description=Nu Choate League Data Sync
After=network.target mongodb.service

[Service]
Type=oneshot
User=yourusername
WorkingDirectory=/home/yourusername
EnvironmentFile=/etc/nuchoate-api-prod.env
ExecStart=/usr/bin/python3 /home/yourusername/sync_sleeper_to_mongodb.py --env prod
```

Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable nuchoate-sync.timer
sudo systemctl start nuchoate-sync.timer
systemctl list-timers
```

---

## Checklist

- [ ] MongoDB installed and running
- [ ] Three databases created with users
- [ ] Authentication enabled
- [ ] Data migrated to all databases
- [ ] FastAPI backend working locally
- [ ] systemd services created and running
- [ ] nginx configured and running
- [ ] Scheduled jobs configured

---

## Troubleshooting

**MongoDB won't start:**
```bash
sudo journalctl -u mongodb -n 50
sudo lsof -i :27017
```

**API service won't start:**
```bash
sudo systemctl status nuchoate-api-staging.service
sudo journalctl -u nuchoate-api-staging.service -n 50
cat /etc/nuchoate-api-staging.env
```

**Can't connect to MongoDB:**
```bash
mongosh -u nuchoate_app -p --authenticationDatabase nu_choate_league_dev
sudo systemctl status mongodb
```

---

## Resources

- [Arch Linux Wiki - MongoDB](https://wiki.archlinux.org/title/MongoDB)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Motor (Async MongoDB) Docs](https://motor.readthedocs.io/)
