# 🎯 Next Steps - Your Minimal DigitalOcean Setup

You've added the migration roadmap markdown file. Here's what to do now to get your site live on DigitalOcean.

---

## ✅ What's Already Set Up

I've created all the necessary files for your minimal $11/month setup:

### Configuration Files
- ✅ `.env.example` - Environment variables template
- ✅ `.gitignore` - Updated to exclude sensitive files
- ✅ `.do/app.yaml` - DigitalOcean App Platform configuration

### Backend Application
- ✅ `backend/` - Complete FastAPI application
  - `app/main.py` - Main API server
  - `app/config.py` - Settings management
  - `app/database.py` - MongoDB connection
  - `app/routers/` - API endpoints (leagues, stats)
  - `requirements.txt` - Python dependencies
  - `Dockerfile` - Container configuration

### Scripts
- ✅ `scripts/migrate_to_mongodb.py` - Data migration script
- ✅ `scripts/setup_mongodb_droplet.sh` - MongoDB installation script

### Documentation
- ✅ `README.md` - Updated with DigitalOcean instructions
- ✅ `MONGODB_SETUP_GUIDE.md` - Complete MongoDB setup guide
- ✅ `QUICKSTART.md` - 30-minute quick start guide
- ✅ `DIGITALOCEAN_MIGRATION_ROADMAP.md` - Full migration plan
- ✅ `NEXT_STEPS.md` - This file!

---

## 📋 Your Action Plan (In Order)

### Phase 1: Set Up Infrastructure (~20 minutes)

#### 1. Create MongoDB Droplet
**Cost: $6/month**

```
☐ Go to DigitalOcean → Create → Droplets
☐ Choose: Ubuntu 24.04, $6/month, your region
☐ Create droplet and note the IP address
```

**Guide:** See `MONGODB_SETUP_GUIDE.md` for detailed steps

---

#### 2. Install MongoDB on Droplet

```bash
# SSH into your droplet
ssh root@YOUR_DROPLET_IP

# Run the automated setup script
# (You'll need to push to GitHub first, or copy-paste the script)
./setup_mongodb_droplet.sh
```

**Output:** You'll get a connection string. **SAVE IT!**
```
mongodb://nuchoate_app:password@123.45.67.89:27017/nu_choate_league?authSource=nu_choate_league
```

---

### Phase 2: Configure Locally (~10 minutes)

#### 3. Create `.env` File

```bash
# In your project root
cp .env.example .env

# Edit with your connection string
nano .env
```

Update:
```env
MONGODB_URI=mongodb://nuchoate_app:YOUR_PASSWORD@YOUR_IP:27017/nu_choate_league?authSource=nu_choate_league
JWT_SECRET=<generate with: openssl rand -hex 32>
```

---

#### 4. Install Dependencies

```bash
# Install migration script dependencies
pip install motor python-dotenv

# OR use pipenv
pipenv install
```

---

#### 5. Migrate Data to MongoDB

```bash
python scripts/migrate_to_mongodb.py
```

**Expected output:**
```
======================================================================
Nu Choate League - MongoDB Migration
======================================================================

✓ Connected to MongoDB successfully
✓ Found data directory

Migrating Season: 2024
  ✓ League info
  ✓ Rosters (12 teams)
  ✓ Users (12 users)
  ...

Migration Complete!
```

---

### Phase 3: Test Locally (~5 minutes)

#### 6. Run the API Locally

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 7. Test in Browser

Open these URLs:
- http://localhost:8000/ - API info
- http://localhost:8000/health - Health check
- http://localhost:8000/api/docs - Interactive API docs
- http://localhost:8000/api/v1/leagues - Your league data

**If you see data, you're ready to deploy!** 🎉

---

### Phase 4: Deploy to DigitalOcean (~15 minutes)

#### 8. Update Configuration

Edit `.do/app.yaml` and replace:
```yaml
YOUR_GITHUB_USERNAME/nu_choate_league
```
with your actual GitHub username.

---

#### 9. Commit and Push

```bash
git add .
git commit -m "Set up DigitalOcean deployment"
git push origin main
```

---

#### 10. Create App on DigitalOcean
**Cost: $5/month**

1. Go to https://cloud.digitalocean.com/apps
2. Click **"Create App"**
3. Select **GitHub** as source
4. Choose your repository: `nu_choate_league`
5. Choose branch: `main`
6. DigitalOcean detects `app.yaml` automatically
7. Click **"Next"**

---

#### 11. Set Environment Variables

In the App Platform setup, add these **encrypted** variables:

```
MONGODB_URI = mongodb://nuchoate_app:password@YOUR_IP:27017/nu_choate_league?authSource=nu_choate_league
JWT_SECRET = <your generated secret>
```

Other variables are already in `app.yaml`.

---

#### 12. Deploy!

1. Review settings
2. Click **"Create Resources"**
3. Wait 5-10 minutes for deployment
4. You'll get a URL: `https://your-app.ondigitalocean.app`

---

### Phase 5: Verify Deployment (~2 minutes)

#### 13. Test Your Live Site

Visit:
- `https://your-app.ondigitalocean.app/health`
- `https://your-app.ondigitalocean.app/api/v1/leagues`
- `https://your-app.ondigitalocean.app/api/docs`

**If these work, you're live!** 🚀

---

## 📊 Cost Summary

| Component | Cost/Month | What It Does |
|-----------|------------|--------------|
| MongoDB Droplet | $6 | Stores all your data |
| App Platform | $5 | Runs FastAPI backend + frontend |
| **Total** | **$11/month** | Complete hosting solution |

**With $200 credit = 18 months free!** 🎉

---

## 🎓 What You've Built

After completing these steps, you'll have:

✅ **Self-hosted MongoDB database** with all your fantasy league data  
✅ **RESTful API** serving league data via FastAPI  
✅ **Automatic deploys** - push to GitHub = auto-deploy  
✅ **HTTPS with SSL** - automatic and free  
✅ **API documentation** - auto-generated at `/api/docs`  
✅ **Scalable infrastructure** - can upgrade anytime  

---

## 🔜 Optional Improvements (Later)

Once your site is live, you can:

1. **Add Custom Domain**
   - App Platform → Settings → Domains
   - Point your domain to DigitalOcean

2. **Set Up Automatic Backups**
   - See `MONGODB_SETUP_GUIDE.md` for backup script
   - Or enable DigitalOcean droplet backups (+$1.20/month)

3. **Build a Frontend**
   - Create a React/Vue app
   - Fetch data from your API
   - Deploy alongside backend

4. **Add Scheduled Data Sync**
   - Fetch latest data from Sleeper API automatically
   - Update MongoDB weekly

5. **Add Authentication**
   - Member-only pages
   - Commissioner admin panel

---

## 📚 Documentation Reference

- **Quick Start:** `QUICKSTART.md` - 30-minute setup guide
- **MongoDB Setup:** `MONGODB_SETUP_GUIDE.md` - Detailed MongoDB instructions
- **Full Roadmap:** `DIGITALOCEAN_MIGRATION_ROADMAP.md` - Complete migration plan
- **Main README:** `README.md` - Project overview and documentation

---

## 🐛 Common Issues

### "Cannot connect to MongoDB"
- Check firewall on droplet: `ssh root@IP` then `ufw status`
- Verify connection string in `.env`
- Make sure MongoDB is running: `systemctl status mongod`

### "Migration script fails"
- Make sure `.env` file exists with correct `MONGODB_URI`
- Install dependencies: `pip install motor python-dotenv`
- Check MongoDB is accessible: `mongosh "YOUR_CONNECTION_STRING"`

### "Deployment fails"
- Check logs in App Platform dashboard
- Verify environment variables are set correctly
- Make sure `app.yaml` has correct GitHub username

---

## ✨ You're All Set!

Follow the action plan above and you'll have your fantasy football site live on DigitalOcean in about an hour.

**Current Status:** 
- ✅ All code and configuration files created
- ☐ MongoDB droplet setup (you need to do this)
- ☐ Data migration (you need to do this)
- ☐ App Platform deployment (you need to do this)

**Start with:** `QUICKSTART.md` or `MONGODB_SETUP_GUIDE.md`

Good luck! 🚀
