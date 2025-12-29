# DigitalOcean Migration Roadmap
## Nu Choate Fantasy Football League Hub

---

## Table of Contents
1. [Current Architecture](#current-architecture)
2. [Target Architecture on DigitalOcean](#target-architecture-on-digitalocean)
3. [Database Design (MongoDB)](#database-design-mongodb)
4. [Migration Phases](#migration-phases)
5. [Cost Breakdown](#cost-breakdown)
6. [Detailed Implementation Steps](#detailed-implementation-steps)

---

## Current Architecture

### Current Stack
- **Hosting**: GitHub Pages (static HTML)
- **Data Storage**: Local JSON files in `src/data/`
- **Data Processing**: Python scripts run locally
- **Data Source**: Sleeper API
- **Frontend**: Static HTML/CSS pages

### Current Workflow
1. Run Python script locally to fetch data from Sleeper API
2. Process data and generate HTML reports
3. Copy reports to `docs/` folder
4. Commit and push to GitHub
5. GitHub Pages serves static site

### Limitations
- No dynamic updates (manual script execution)
- No user authentication
- No database (data stored in JSON files)
- No backend API
- Limited to static content

---

## Target Architecture on DigitalOcean

### Services to Use

#### 1. **DigitalOcean App Platform** (Primary Application)
- Hosts the Python backend (FastAPI/Flask)
- Automatically builds and deploys from GitHub
- Handles SSL certificates
- Scales automatically
- **Cost**: ~$5-12/month (Basic Plan)

#### 2. **MongoDB Atlas** (Database - via DigitalOcean Marketplace)
- Managed MongoDB instance
- Stores all league data (matchups, rosters, standings, etc.)
- Automatic backups
- **Cost**: ~$15-25/month (Shared M2 cluster suitable for your needs)
- **Alternative**: Self-hosted MongoDB on DO Droplet ($6/month)

#### 3. **DigitalOcean Spaces** (Optional - Object Storage)
- Store generated HTML reports, images, assets
- CDN for fast delivery
- **Cost**: ~$5/month (250GB storage + 1TB transfer)
- **Alternative**: Serve directly from App Platform

#### 4. **Custom Domain**
- Already have this setup with CNAME
- Point to App Platform instead of GitHub Pages

### New Architecture Diagram

```
┌─────────────────┐
│   Users/Web     │
│    Browsers     │
└────────┬────────┘
         │
         │ HTTPS
         ▼
┌─────────────────────────────────┐
│  Custom Domain                  │
│  (nuchoateleague.xyz)           │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  DigitalOcean App Platform      │
│  ┌───────────────────────────┐  │
│  │   FastAPI/Flask Backend   │  │
│  │   - API Endpoints         │  │
│  │   - Authentication        │  │
│  │   - Scheduled Jobs        │  │
│  │   - Static File Serving   │  │
│  └───────────┬───────────────┘  │
└──────────────┼──────────────────┘
               │
               ├──────────────┐
               │              │
               ▼              ▼
    ┌──────────────┐   ┌────────────────┐
    │   MongoDB    │   │  Sleeper API   │
    │   (Atlas)    │   │  (External)    │
    │              │   │                │
    │ - Matchups   │   └────────────────┘
    │ - Rosters    │
    │ - Users      │
    │ - Standings  │
    │ - Stats      │
    └──────────────┘
```

---

## Database Design (MongoDB)

### Collections Structure

MongoDB's document-based structure is perfect for your nested JSON data from Sleeper API.

#### 1. **leagues** Collection
```javascript
{
  _id: ObjectId(),
  league_id: "1251998020954763264",
  name: "Nu Choate League",
  season: "2025",
  status: "post_season",
  settings: {
    num_teams: 12,
    playoff_teams: 6,
    playoff_week_start: 15,
    last_scored_leg: 16,
    // ... all other settings
  },
  scoring_settings: {
    pass_yd: 0.04,
    rush_yd: 0.1,
    rec: 1.0,
    // ... all scoring rules
  },
  roster_positions: ["QB", "RB", "RB", ...],
  previous_league_id: "1130723458041856000",
  draft_id: "1251998020963151872",
  created_at: ISODate(),
  updated_at: ISODate()
}
```

#### 2. **rosters** Collection
```javascript
{
  _id: ObjectId(),
  roster_id: 1,
  league_id: "1251998020954763264",
  season: "2025",
  owner_id: "1130723298733744128",
  players: ["11560", "11631", "11786", ...],
  starters: ["11560", "4034", ...],
  settings: {
    wins: 20,
    losses: 8,
    ties: 0,
    fpts: 1974.98,
    fpts_against: 1758.16,
  },
  metadata: {
    record: "LWLWWWWLWWWWLWWWWLLWWWWWWWLL",
    streak: "2L"
  },
  created_at: ISODate(),
  updated_at: ISODate()
}
```

#### 3. **matchups** Collection
```javascript
{
  _id: ObjectId(),
  league_id: "1251998020954763264",
  season: "2025",
  week: 1,
  matchup_id: 4,
  roster_id: 1,
  points: 125.92,
  starters: ["11566", "4034", "6790", ...],
  starters_points: [20.12, 23.2, 9.5, ...],
  players: ["11566", "11631", ...],
  players_points: {
    "11566": 20.12,
    "11631": 9.0,
    // ...
  },
  created_at: ISODate(),
  updated_at: ISODate()
}
```

#### 4. **users** Collection
```javascript
{
  _id: ObjectId(),
  user_id: "1130723298733744128",
  display_name: "ahhowey",
  username: "ahhowey",
  team_name: "Team ahhowey",
  avatar: "https://...",
  metadata: {
    // user preferences, settings
  },
  leagues: ["1251998020954763264", "1130723458041856000"],
  created_at: ISODate(),
  updated_at: ISODate()
}
```

#### 5. **players** Collection
```javascript
{
  _id: ObjectId(),
  player_id: "11566",
  first_name: "Patrick",
  last_name: "Mahomes",
  full_name: "Patrick Mahomes",
  position: "QB",
  team: "KC",
  status: "Active",
  // Cached from Sleeper API
  created_at: ISODate(),
  updated_at: ISODate()
}
```

#### 6. **transactions** Collection
```javascript
{
  _id: ObjectId(),
  transaction_id: "...",
  league_id: "1251998020954763264",
  season: "2025",
  week: 1,
  type: "waiver", // "trade", "free_agent", "waiver"
  status: "complete",
  roster_ids: [1, 5],
  settings: {
    waiver_bid: 15
  },
  adds: {
    "8167": 1  // player_id: roster_id
  },
  drops: {
    "9487": 1
  },
  created: 1234567890000,
  created_at: ISODate(),
  updated_at: ISODate()
}
```

#### 7. **standings** Collection (Computed/Cached Data)
```javascript
{
  _id: ObjectId(),
  league_id: "1251998020954763264",
  season: "2025",
  week: 14,
  standings: [
    {
      rank: 1,
      roster_id: 1,
      team_name: "Team ahhowey",
      wins: 20,
      losses: 8,
      ties: 0,
      points_for: 1974.98,
      points_against: 1758.16,
      // ... other calculated stats
    },
    // ... more teams
  ],
  created_at: ISODate(),
  updated_at: ISODate()
}
```

#### 8. **brackets** Collection (Playoff Brackets)
```javascript
{
  _id: ObjectId(),
  league_id: "1251998020954763264",
  season: "2025",
  bracket_type: "winners", // "winners" or "losers"
  bracket_id: "1304405420613304320",
  rounds: [
    {
      round: 1,
      matchups: [
        {
          team1_roster_id: 1,
          team2_roster_id: 2,
          winner: 1,
          team1_score: 125.5,
          team2_score: 98.3
        }
      ]
    }
  ],
  created_at: ISODate(),
  updated_at: ISODate()
}
```

#### 9. **drafts** Collection
```javascript
{
  _id: ObjectId(),
  draft_id: "1251998020963151872",
  league_id: "1251998020954763264",
  season: "2025",
  status: "complete",
  type: "snake",
  picks: [
    {
      pick_no: 1,
      round: 1,
      roster_id: 3,
      player_id: "8183",
      picked_by: "user_id",
      metadata: {}
    },
    // ... all picks
  ],
  created_at: ISODate(),
  updated_at: ISODate()
}
```

### Indexes (for Performance)
```javascript
// leagues
db.leagues.createIndex({ "league_id": 1 })
db.leagues.createIndex({ "season": 1 })

// rosters
db.rosters.createIndex({ "league_id": 1, "season": 1 })
db.rosters.createIndex({ "owner_id": 1 })

// matchups
db.matchups.createIndex({ "league_id": 1, "season": 1, "week": 1 })
db.matchups.createIndex({ "roster_id": 1, "season": 1 })

// users
db.users.createIndex({ "user_id": 1 }, { unique: true })

// players
db.players.createIndex({ "player_id": 1 }, { unique: true })

// transactions
db.transactions.createIndex({ "league_id": 1, "season": 1, "week": 1 })

// standings
db.standings.createIndex({ "league_id": 1, "season": 1, "week": 1 }, { unique: true })
```

---

## Migration Phases

### Phase 1: Setup & Infrastructure (Week 1)
**Goal**: Set up DigitalOcean infrastructure

- [ ] Create DigitalOcean account (✓ Done)
- [ ] Set up MongoDB Atlas cluster (or DO-hosted MongoDB)
- [ ] Create App Platform project
- [ ] Configure environment variables
- [ ] Set up GitHub integration for auto-deploy

**Deliverables**:
- Working MongoDB cluster
- App Platform connected to GitHub repo
- Basic health check endpoint deployed

---

### Phase 2: Database Migration (Week 2)
**Goal**: Migrate existing JSON data to MongoDB

- [ ] Create database migration script
- [ ] Load historical data from JSON files into MongoDB
  - League info (2024, 2025)
  - Rosters
  - Matchups (all weeks)
  - Users
  - Transactions
  - Players
  - Draft data
- [ ] Validate data integrity
- [ ] Create database indexes

**Deliverables**:
- Migration script: `scripts/migrate_to_mongodb.py`
- All historical data in MongoDB
- Data validation report

---

### Phase 3: Backend API Development (Week 3-4)
**Goal**: Build FastAPI backend to replace static site

#### API Endpoints to Build

**Public Endpoints** (No auth required)
```
GET  /api/v1/leagues                      # List all leagues/seasons
GET  /api/v1/leagues/{season}             # Get league info for season
GET  /api/v1/leagues/{season}/standings   # Get current standings
GET  /api/v1/leagues/{season}/standings/week/{week}  # Historical standings
GET  /api/v1/leagues/{season}/matchups/week/{week}   # Matchups for week
GET  /api/v1/leagues/{season}/rosters     # All rosters
GET  /api/v1/leagues/{season}/rosters/{roster_id}    # Specific roster
GET  /api/v1/leagues/{season}/draft       # Draft results
GET  /api/v1/leagues/{season}/playoffs    # Playoff bracket
GET  /api/v1/leagues/{season}/transactions/week/{week}  # Transactions
GET  /api/v1/stats/all-time/standings     # All-time standings
GET  /api/v1/stats/all-time/head-to-head  # H2H records
GET  /api/v1/stats/all-time/high-scores   # High score records
GET  /api/v1/players/{player_id}          # Player info
```

**Admin Endpoints** (Auth required)
```
POST /api/v1/admin/sync                   # Trigger Sleeper API sync
POST /api/v1/admin/generate-reports       # Generate HTML reports
GET  /api/v1/admin/sync-status            # Check sync job status
POST /api/v1/admin/awards                 # Manually assign awards
```

**Authentication Endpoints**
```
POST /api/v1/auth/login                   # Login with username/password
POST /api/v1/auth/logout                  # Logout
GET  /api/v1/auth/me                      # Get current user info
```

**Tech Stack**:
- **FastAPI**: Modern, fast Python web framework
- **Motor**: Async MongoDB driver for Python
- **Pydantic**: Data validation
- **JWT**: Authentication tokens
- **APScheduler**: Scheduled jobs

**Deliverables**:
- FastAPI application in `backend/` directory
- All API endpoints implemented
- API documentation (auto-generated by FastAPI)
- Unit tests

---

### Phase 4: Scheduled Data Sync (Week 4)
**Goal**: Automate Sleeper API data fetching

**Implementation Options**:

#### Option A: Built-in Scheduler (APScheduler)
```python
# Run every Tuesday at 3 AM EST (after MNF)
@scheduler.scheduled_job('cron', day_of_week='tue', hour=3)
async def sync_weekly_data():
    # Fetch latest data from Sleeper API
    # Update MongoDB
    # Generate updated reports
```

#### Option B: DigitalOcean App Platform Cron Jobs
Configure in `app.yaml`:
```yaml
jobs:
  - name: weekly-sync
    kind: PRE_DEPLOY
    schedule:
      - rule: "0 3 * * TUE"  # Every Tuesday at 3 AM
    run_command: python scripts/sync_sleeper_data.py
```

**Sync Logic**:
1. Check current week in Sleeper API
2. Fetch new matchups, transactions, rosters
3. Update MongoDB collections
4. Recalculate standings
5. Generate updated reports
6. Send notification (optional - email/webhook)

**Deliverables**:
- Automated sync script
- Error handling and logging
- Manual sync endpoint for immediate updates

---

### Phase 5: Frontend Development (Week 5-6)
**Goal**: Build dynamic frontend

**Two Options**:

#### Option A: Keep Static HTML, Make it Dynamic
- Use JavaScript to fetch data from API
- Update existing HTML/CSS
- Minimal changes to current design
- **Pros**: Faster to implement, familiar
- **Cons**: Limited interactivity

#### Option B: Build Modern SPA (React/Vue/Svelte)
- Full rewrite with modern framework
- Rich interactivity
- Better user experience
- **Pros**: Better UX, more features
- **Cons**: More time, steeper learning curve

**Recommended**: Start with Option A, migrate to Option B later

**Features to Add**:
- Real-time standings updates
- Search/filter teams
- Player stats lookup
- Responsive mobile design
- Dark mode toggle

**Deliverables**:
- Updated frontend code
- API integration
- Mobile-responsive design

---

### Phase 6: Authentication System (Week 7)
**Goal**: Add user authentication for league members

**Authentication Strategy**:

#### Option A: Simple JWT Auth
- Username/password for league members
- JWT tokens for session management
- Simple to implement

#### Option B: OAuth Integration
- "Sign in with Google"
- "Sign in with GitHub"
- More user-friendly, no password management

**Recommended**: Start with JWT, add OAuth later

**User Roles**:
- **Public**: Can view all data
- **Member**: League members (future: can comment, vote on awards)
- **Admin**: Can trigger syncs, edit content, manage users

**Features**:
- Member-only pages (future)
- Commissioner controls
- Custom team pages

**Deliverables**:
- Authentication system
- User management endpoints
- Protected routes

---

### Phase 7: Domain & SSL Setup (Week 7)
**Goal**: Point custom domain to DigitalOcean

**Steps**:
1. Update DNS records (CNAME or A record)
2. Configure custom domain in App Platform
3. SSL certificate (automatic with App Platform)
4. Test domain

**Deliverables**:
- Custom domain pointing to App Platform
- HTTPS enabled

---

### Phase 8: Testing & Optimization (Week 8)
**Goal**: Test, optimize, and prepare for launch

- [ ] Load testing
- [ ] API response time optimization
- [ ] Database query optimization
- [ ] Caching strategy (Redis optional)
- [ ] Error monitoring setup (Sentry optional)
- [ ] Backup strategy

**Deliverables**:
- Performance benchmarks
- Monitoring dashboard
- Backup procedures documented

---

### Phase 9: Deployment & Migration (Week 9)
**Goal**: Go live on DigitalOcean

**Migration Day Checklist**:
1. [ ] Final data sync from Sleeper API
2. [ ] Update DNS to point to DigitalOcean
3. [ ] Monitor for issues (DNS propagation takes 24-48hrs)
4. [ ] Keep GitHub Pages live as backup during transition
5. [ ] Send announcement to league members

**Rollback Plan**:
- If issues arise, revert DNS to GitHub Pages
- Fix issues, try again

**Deliverables**:
- Live site on DigitalOcean
- GitHub Pages decommissioned (or kept as backup)

---

## Cost Breakdown

### Monthly Costs (Estimated)

| Service | Plan | Cost | Notes |
|---------|------|------|-------|
| **App Platform** | Basic | $5-12/month | 1 container, auto-scaling |
| **MongoDB Atlas** | M2 Shared | $15-25/month | 2GB storage, suitable for your needs |
| **Spaces (Optional)** | Standard | $5/month | 250GB + 1TB transfer |
| **Domain** | Existing | $0 | Already have |
| **SSL Certificate** | Included | $0 | Auto with App Platform |
| **Total** | | **$25-40/month** | With $200 credit = 5-8 months free |

### Alternative (Budget Option)

| Service | Plan | Cost | Notes |
|---------|------|------|-------|
| **Droplet** | Basic | $6/month | 1GB RAM, 25GB SSD |
| **Managed MongoDB** | Self-hosted on Droplet | $0 | Included in Droplet |
| **Total** | | **$6/month** | With $200 credit = 33 months free! |

**Trade-offs**: More manual setup, less automation, you manage backups

### Recommended Approach
Start with **App Platform + MongoDB Atlas** for ease of use. Your $200 credit covers 5-8 months. By then, you'll know your actual usage and can optimize.

---

## Detailed Implementation Steps

### Step 1: MongoDB Setup

#### Using MongoDB Atlas (Recommended)
```bash
# 1. Go to MongoDB Atlas (https://www.mongodb.com/cloud/atlas)
# 2. Sign up/login
# 3. Create new cluster (select DigitalOcean as cloud provider for lower latency)
# 4. Choose region closest to your App Platform (probably NYC)
# 5. Get connection string
```

#### Environment Variables
```bash
# .env file (local development)
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/nu_choate_league
SLEEPER_LEAGUE_ID=1251998020954763264
JWT_SECRET=your-secret-key-here
API_ENV=development
```

---

### Step 2: Project Restructure

Reorganize project for backend + frontend separation:

```
nu_choate_league/
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI app entry
│   │   ├── config.py        # Configuration
│   │   ├── database.py      # MongoDB connection
│   │   ├── models/          # Pydantic models
│   │   │   ├── league.py
│   │   │   ├── roster.py
│   │   │   ├── matchup.py
│   │   │   └── user.py
│   │   ├── routers/         # API routes
│   │   │   ├── leagues.py
│   │   │   ├── standings.py
│   │   │   ├── stats.py
│   │   │   ├── admin.py
│   │   │   └── auth.py
│   │   ├── services/        # Business logic
│   │   │   ├── sleeper_sync.py
│   │   │   ├── standings_calculator.py
│   │   │   └── report_generator.py
│   │   ├── scheduler/       # Scheduled jobs
│   │   │   └── jobs.py
│   │   └── utils/           # Utility functions
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                # Frontend (HTML/JS or React)
│   ├── public/
│   ├── src/
│   └── package.json
├── scripts/                 # Migration & utility scripts
│   ├── migrate_to_mongodb.py
│   ├── sync_sleeper_data.py
│   └── seed_database.py
├── docs/                    # Current static site (keep during transition)
├── src/                     # Current Python scripts (migrate to backend/)
├── .env.example
├── .gitignore
├── app.yaml                 # DigitalOcean App Platform config
├── README.md
└── DIGITALOCEAN_MIGRATION_ROADMAP.md  # This file
```

---

### Step 3: Sample FastAPI Code

#### `backend/app/main.py`
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import connect_to_mongo, close_mongo_connection
from app.routers import leagues, standings, stats, admin, auth

app = FastAPI(
    title="Nu Choate League API",
    description="Fantasy Football League Hub API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
@app.on_event("startup")
async def startup_db_client():
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_db_client():
    await close_mongo_connection()

# Health check
@app.get("/")
async def root():
    return {"status": "healthy", "message": "Nu Choate League API"}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Include routers
app.include_router(leagues.router, prefix="/api/v1", tags=["leagues"])
app.include_router(standings.router, prefix="/api/v1", tags=["standings"])
app.include_router(stats.router, prefix="/api/v1", tags=["stats"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
```

#### `backend/app/database.py`
```python
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

class Database:
    client: AsyncIOMotorClient = None
    
db = Database()

async def connect_to_mongo():
    db.client = AsyncIOMotorClient(settings.MONGODB_URI)
    print("Connected to MongoDB")
    
async def close_mongo_connection():
    db.client.close()
    print("Closed MongoDB connection")

def get_database():
    return db.client[settings.DATABASE_NAME]
```

#### `backend/app/config.py`
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGODB_URI: str
    DATABASE_NAME: str = "nu_choate_league"
    SLEEPER_LEAGUE_ID: str
    JWT_SECRET: str
    API_ENV: str = "development"
    
    class Config:
        env_file = ".env"

settings = Settings()
```

---

### Step 4: Migration Script

#### `scripts/migrate_to_mongodb.py`
```python
"""
Migrate JSON data from src/data/unmunged to MongoDB
"""
import asyncio
import json
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))
from app.config import settings

async def migrate_data():
    # Connect to MongoDB
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.DATABASE_NAME]
    
    unmunged_dir = Path(__file__).parent.parent / 'src' / 'data' / 'unmunged'
    
    print("Starting migration...")
    
    # Migrate each season
    for season_dir in unmunged_dir.iterdir():
        if not season_dir.is_dir():
            continue
            
        season = season_dir.name
        print(f"\n=== Migrating Season {season} ===")
        
        # Migrate league info
        league_info_path = season_dir / 'league_info.json'
        if league_info_path.exists():
            with open(league_info_path) as f:
                league_data = json.load(f)
                league_data['season'] = season
                league_data['created_at'] = datetime.utcnow()
                league_data['updated_at'] = datetime.utcnow()
                
                await db.leagues.update_one(
                    {'league_id': league_data['league_id'], 'season': season},
                    {'$set': league_data},
                    upsert=True
                )
                print(f"✓ Migrated league info for {season}")
        
        # Migrate rosters
        rosters_path = season_dir / 'rosters.json'
        if rosters_path.exists():
            with open(rosters_path) as f:
                rosters_data = json.load(f)
                for roster in rosters_data:
                    roster['season'] = season
                    roster['league_id'] = league_data['league_id']
                    roster['created_at'] = datetime.utcnow()
                    roster['updated_at'] = datetime.utcnow()
                    
                    await db.rosters.update_one(
                        {
                            'roster_id': roster['roster_id'],
                            'league_id': roster['league_id'],
                            'season': season
                        },
                        {'$set': roster},
                        upsert=True
                    )
                print(f"✓ Migrated {len(rosters_data)} rosters for {season}")
        
        # Migrate users
        users_path = season_dir / 'users.json'
        if users_path.exists():
            with open(users_path) as f:
                users_data = json.load(f)
                for user in users_data:
                    user['created_at'] = datetime.utcnow()
                    user['updated_at'] = datetime.utcnow()
                    
                    await db.users.update_one(
                        {'user_id': user['user_id']},
                        {'$set': user},
                        upsert=True
                    )
                print(f"✓ Migrated {len(users_data)} users for {season}")
        
        # Migrate weekly matchups
        for week_dir in season_dir.glob('week_*'):
            week_num = int(week_dir.name.split('_')[1])
            
            matchups_path = week_dir / 'matchups.json'
            if matchups_path.exists():
                with open(matchups_path) as f:
                    matchups_data = json.load(f)
                    for matchup in matchups_data:
                        matchup['season'] = season
                        matchup['week'] = week_num
                        matchup['league_id'] = league_data['league_id']
                        matchup['created_at'] = datetime.utcnow()
                        matchup['updated_at'] = datetime.utcnow()
                        
                        await db.matchups.update_one(
                            {
                                'league_id': matchup['league_id'],
                                'season': season,
                                'week': week_num,
                                'roster_id': matchup['roster_id']
                            },
                            {'$set': matchup},
                            upsert=True
                        )
                    print(f"✓ Migrated week {week_num} matchups ({len(matchups_data)} entries)")
            
            # Migrate transactions
            transactions_path = week_dir / 'transactions.json'
            if transactions_path.exists():
                with open(transactions_path) as f:
                    transactions_data = json.load(f)
                    for transaction in transactions_data:
                        transaction['season'] = season
                        transaction['week'] = week_num
                        transaction['league_id'] = league_data['league_id']
                        transaction['created_at'] = datetime.utcnow()
                        transaction['updated_at'] = datetime.utcnow()
                        
                        await db.transactions.insert_one(transaction)
                    if transactions_data:
                        print(f"✓ Migrated week {week_num} transactions ({len(transactions_data)} entries)")
        
        # Migrate draft
        draft_path = season_dir / 'draft.json'
        if draft_path.exists():
            with open(draft_path) as f:
                draft_data = json.load(f)
                for draft in draft_data:
                    draft['season'] = season
                    draft['league_id'] = league_data['league_id']
                    draft['created_at'] = datetime.utcnow()
                    draft['updated_at'] = datetime.utcnow()
                    
                    await db.drafts.update_one(
                        {'draft_id': draft['draft_id']},
                        {'$set': draft},
                        upsert=True
                    )
                print(f"✓ Migrated draft data for {season}")
    
    # Migrate players
    players_path = unmunged_dir / 'players.json'
    if players_path.exists():
        with open(players_path) as f:
            players_data = json.load(f)
            # Players data is a dict with player_id as key
            player_count = 0
            for player_id, player_info in players_data.items():
                player_info['player_id'] = player_id
                player_info['created_at'] = datetime.utcnow()
                player_info['updated_at'] = datetime.utcnow()
                
                await db.players.update_one(
                    {'player_id': player_id},
                    {'$set': player_info},
                    upsert=True
                )
                player_count += 1
            print(f"\n✓ Migrated {player_count} players")
    
    print("\n=== Creating Indexes ===")
    # Create indexes
    await db.leagues.create_index([("league_id", 1), ("season", 1)])
    await db.rosters.create_index([("league_id", 1), ("season", 1)])
    await db.matchups.create_index([("league_id", 1), ("season", 1), ("week", 1)])
    await db.users.create_index("user_id", unique=True)
    await db.players.create_index("player_id", unique=True)
    print("✓ Indexes created")
    
    print("\n✅ Migration complete!")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(migrate_data())
```

---

### Step 5: DigitalOcean App Platform Configuration

#### `app.yaml`
```yaml
name: nu-choate-league
region: nyc

# Database
databases:
  - name: mongodb
    engine: MONGODB
    version: "6"
    size: db-s-1vcpu-1gb

# Backend service
services:
  - name: api
    github:
      repo: YOUR_USERNAME/nu_choate_league
      branch: main
      deploy_on_push: true
    source_dir: /backend
    dockerfile_path: backend/Dockerfile
    
    envs:
      - key: MONGODB_URI
        scope: RUN_TIME
        value: ${mongodb.DATABASE_URL}
      - key: DATABASE_NAME
        scope: RUN_TIME
        value: nu_choate_league
      - key: SLEEPER_LEAGUE_ID
        scope: RUN_TIME
        value: "1251998020954763264"
      - key: JWT_SECRET
        scope: RUN_TIME
        type: SECRET
        value: YOUR_JWT_SECRET_HERE
      - key: API_ENV
        scope: RUN_TIME
        value: production
    
    health_check:
      http_path: /health
    
    http_port: 8000
    
    instance_count: 1
    instance_size_slug: basic-xxs  # $5/month
    
    routes:
      - path: /api
      - path: /docs
      - path: /redoc

# Static site (frontend)
  - name: web
    github:
      repo: YOUR_USERNAME/nu_choate_league
      branch: main
    source_dir: /frontend
    
    static_sites:
      - name: frontend
        build_command: npm run build
        output_dir: dist
        catchall_document: index.html
    
    routes:
      - path: /

# Scheduled jobs
jobs:
  - name: weekly-sync
    kind: PRE_DEPLOY
    github:
      repo: YOUR_USERNAME/nu_choate_league
      branch: main
    source_dir: /backend
    
    envs:
      - key: MONGODB_URI
        scope: RUN_TIME
        value: ${mongodb.DATABASE_URL}
    
    run_command: python scripts/sync_sleeper_data.py
    
    schedule:
      - rule: "0 3 * * TUE"  # Every Tuesday at 3 AM
```

---

## Next Steps

1. **Review this roadmap** - Make sure you understand each phase
2. **Set up MongoDB Atlas** - Get your database ready
3. **Create `.env` file** - Configure local development environment
4. **Run migration script** - Move JSON data to MongoDB
5. **Start building the FastAPI backend** - Begin with Phase 3

Would you like me to help you start with any specific phase?

---

## Resources

### Documentation
- [DigitalOcean App Platform Docs](https://docs.digitalocean.com/products/app-platform/)
- [MongoDB Atlas Documentation](https://www.mongodb.com/docs/atlas/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Motor (Async MongoDB) Docs](https://motor.readthedocs.io/)

### Tutorials
- [Deploy FastAPI to DigitalOcean](https://www.digitalocean.com/community/tutorials/how-to-deploy-a-fastapi-application-with-docker-to-digitalocean-app-platform)
- [MongoDB with Python](https://www.mongodb.com/languages/python)

### Cost Calculators
- [DigitalOcean Pricing](https://www.digitalocean.com/pricing)
- [MongoDB Atlas Pricing](https://www.mongodb.com/pricing)

---

**Questions? Issues? Updates?**
Document any changes or decisions in this file as you progress through the migration.

