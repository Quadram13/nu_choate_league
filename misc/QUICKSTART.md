# 🚀 Quick Start Guide - DigitalOcean Minimal Setup

This guide will get you up and running in **under 30 minutes** with the minimal $11/month setup.

---

## ✅ Checklist

Follow these steps in order:

### ☐ Step 1: Create MongoDB Droplet (5 minutes)

1. Log into [DigitalOcean](https://cloud.digitalocean.com/)
2. Click **Create → Droplets**
3. Select:
   - **Image**: Ubuntu 24.04 LTS
   - **Size**: Basic $6/month (1GB RAM, 25GB SSD)
   - **Region**: Closest to you (e.g., New York)
   - **Authentication**: SSH Key (recommended) or Password
   - **Hostname**: `nuchoate-mongodb`
4. Click **Create Droplet**
5. **Copy the droplet IP address**

---

### ☐ Step 2: Install MongoDB (10 minutes)

1. SSH into your droplet:
   ```bash
   ssh root@YOUR_DROPLET_IP
   ```

2. Run the automated setup script:
   ```bash
   # Option A: If you've already pushed to GitHub
   curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/nu_choate_league/main/scripts/setup_mongodb_droplet.sh -o setup.sh
   chmod +x setup.sh
   ./setup.sh
   
   # Option B: Copy-paste the script manually
   nano setup.sh
   # Paste contents of scripts/setup_mongodb_droplet.sh
   # Press Ctrl+X, Y, Enter to save
   chmod +x setup.sh
   ./setup.sh
   ```

3. When prompted, enter:
   - Admin username: `admin`
   - Admin password: (choose a secure password)
   - App username: `nuchoate_app`
   - App password: (choose a secure password)

4. **IMPORTANT**: Copy the connection string shown at the end!
   ```
   mongodb://nuchoate_app:password@YOUR_IP:27017/nu_choate_league?authSource=nu_choate_league
   ```

---

### ☐ Step 3: Configure Local Environment (2 minutes)

1. In your local project directory, create `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env`:
   ```bash
   nano .env  # or use your favorite editor
   ```

3. Update with your MongoDB connection string from Step 2:
   ```env
   MONGODB_URI=mongodb://nuchoate_app:YOUR_PASSWORD@YOUR_DROPLET_IP:27017/nu_choate_league?authSource=nu_choate_league
   DATABASE_NAME=nu_choate_league
   SLEEPER_LEAGUE_ID=1251998020954763264
   JWT_SECRET=your_secret_key_here
   API_ENV=development
   PORT=8000
   ```

4. Generate a JWT secret:
   ```bash
   openssl rand -hex 32
   ```
   Copy the output and paste it as `JWT_SECRET` in your `.env` file

---

### ☐ Step 4: Install Dependencies (3 minutes)

```bash
# Install Python dependencies for migration script
pip install motor python-dotenv

# Or using pipenv
pipenv install
```

---

### ☐ Step 5: Migrate Data to MongoDB (5 minutes)

```bash
python scripts/migrate_to_mongodb.py
```

You should see output like:
```
======================================================================
Nu Choate League - MongoDB Migration
======================================================================

Connecting to MongoDB...
✓ Connected to MongoDB successfully
✓ Found data directory: /path/to/src/data/unmunged

======================================================================
Migrating Season: 2024
======================================================================
  ✓ League info
  ✓ Rosters (12 teams)
  ✓ Users (12 users)
  ...
```

**If this succeeds**, your data is now in MongoDB! 🎉

---

### ☐ Step 6: Test Locally (2 minutes)

1. Install backend dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. Start the API:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. Open in browser:
   - http://localhost:8000/api/docs
   - http://localhost:8000/api/v1/leagues

If you see data, you're good to go! ✅

---

### ☐ Step 7: Deploy to DigitalOcean App Platform (10 minutes)

1. **Update `.do/app.yaml`:**
   - Replace `YOUR_GITHUB_USERNAME` with your actual GitHub username

2. **Commit and push to GitHub:**
   ```bash
   git add .
   git commit -m "Set up DigitalOcean deployment"
   git push origin main
   ```

3. **Create App on DigitalOcean:**
   - Go to https://cloud.digitalocean.com/apps
   - Click **"Create App"**
   - Select **"GitHub"** as source
   - Choose your repository: `nu_choate_league`
   - Select branch: `main`
   - DigitalOcean will auto-detect your `app.yaml` configuration
   - Click **"Next"**

4. **Configure Environment Variables:**
   - On the Environment Variables screen, add:
     - `MONGODB_URI` → Your connection string (mark as **encrypted**)
     - `JWT_SECRET` → Your generated secret (mark as **encrypted**)
   - Other variables are already set in `app.yaml`

5. **Review and Deploy:**
   - Review the settings
   - Click **"Create Resources"**
   - Wait 5-10 minutes for deployment

6. **Access Your App:**
   - Once deployed, you'll get a URL like:
     `https://nu-choate-league-xxxxx.ondigitalocean.app`
   - Test it:
     - `/health` - Should return `{"status": "ok"}`
     - `/api/v1/leagues` - Should return your league data
     - `/api/docs` - Interactive API documentation

---

## 🎉 You're Done!

Your fantasy football site is now live on DigitalOcean for **$11/month**!

**What you have:**
- ✅ Self-hosted MongoDB database
- ✅ FastAPI backend serving data
- ✅ RESTful API with automatic documentation
- ✅ Automatic deploys on git push
- ✅ HTTPS with SSL certificate (automatic)

---

## 🔧 Next Steps (Optional)

1. **Add Custom Domain:**
   - App Platform → Settings → Domains → Add Domain
   - Update your DNS records as instructed

2. **Set Up Automatic Backups:**
   - Follow backup instructions in `MONGODB_SETUP_GUIDE.md`

3. **Monitor Your App:**
   - App Platform dashboard shows logs, metrics, and costs
   - MongoDB: `ssh root@YOUR_DROPLET_IP` then `htop` to monitor

4. **Update Data:**
   - Re-run migration script anytime: `python scripts/migrate_to_mongodb.py`
   - Or build a scheduled sync (see roadmap)

---

## 🐛 Troubleshooting

### Migration Script Fails

**Error: Cannot connect to MongoDB**
- Check firewall: `ssh root@DROPLET_IP` then `ufw status`
- Make sure port 27017 is open
- Verify connection string is correct in `.env`

**Error: Authentication failed**
- Double-check username/password in connection string
- Try connecting from droplet: `mongosh -u nuchoate_app -p`

### Local API Won't Start

**Error: ModuleNotFoundError**
```bash
cd backend
pip install -r requirements.txt
```

**Error: Cannot connect to database**
- Make sure MongoDB droplet is running
- Test connection: `mongosh "YOUR_CONNECTION_STRING"`

### Deployment Fails

**Build Error:**
- Check logs in App Platform dashboard
- Verify Dockerfile is correct
- Make sure `requirements.txt` has all dependencies

**Connection Error:**
- Verify `MONGODB_URI` environment variable is set correctly
- Make sure droplet IP is accessible from App Platform
- Check firewall rules on droplet

---

## 💡 Pro Tips

1. **Use SSH Tunneling for Development:**
   ```bash
   ssh -L 27017:localhost:27017 root@YOUR_DROPLET_IP
   ```
   Then use `localhost:27017` in your connection string

2. **Monitor Costs:**
   - Check DigitalOcean dashboard regularly
   - With $200 credit: $11/month = **18 months free**

3. **Keep MongoDB Secure:**
   - Restrict port 27017 to only your App Platform IP
   - Use strong passwords
   - Enable automatic backups

---

## 📞 Need Help?

1. Check `MONGODB_SETUP_GUIDE.md` for detailed MongoDB setup
2. Check `README.md` for full documentation
3. Review DigitalOcean docs: https://docs.digitalocean.com/products/app-platform/

---

**Estimated Total Time: 30 minutes**  
**Monthly Cost: $11** ($6 MongoDB + $5 App Platform)  
**Free for 18 months** with $200 credit! 🎉
