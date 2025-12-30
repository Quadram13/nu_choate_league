# MongoDB Self-Hosting Guide for DigitalOcean

This guide walks you through setting up MongoDB on a DigitalOcean Droplet for the Nu Choate League project.

## Prerequisites

- DigitalOcean account with $200 credit
- SSH client (Terminal on Mac/Linux, PuTTY on Windows)
- Basic command-line knowledge

---

## Part 1: Create the Droplet (Web Interface)

### 1.1 Create Droplet

1. Log into [DigitalOcean](https://cloud.digitalocean.com/)
2. Click **"Create"** → **"Droplets"**

### 1.2 Configure Droplet

**Choose an image:**
- Select: **Ubuntu 24.04 (LTS) x64**

**Choose Size:**
- Droplet Type: **Basic**
- CPU Options: **Regular**
- Plan: **$6/month** (1 GB RAM / 25 GB SSD / 1000 GB transfer)

**Choose a datacenter region:**
- Select the region closest to you or your users
- Recommended: **New York** (if in US East)

**Authentication:**

**Option A: SSH Key (Recommended - More Secure)**
- If you already have an SSH key:
  - Click **"New SSH Key"**
  - Paste your public key (usually in `~/.ssh/id_rsa.pub`)
  - Give it a name

- If you don't have an SSH key:
  ```bash
  # On your local machine, generate one:
  ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
  
  # Press Enter for default location
  # Press Enter twice for no passphrase (or set one)
  
  # Display your public key:
  cat ~/.ssh/id_rsa.pub
  
  # Copy the output and paste it into DigitalOcean
  ```

**Option B: Password (Easier but Less Secure)**
- Select **"Password"**
- DigitalOcean will email you a root password

**Finalize:**
- **Hostname**: `nuchoate-mongodb` (or any name you prefer)
- **Tags**: `mongodb`, `production` (optional)
- **Backups**: Check this for automatic weekly backups ($1.20/month extra)

3. Click **"Create Droplet"**

### 1.3 Wait for Droplet Creation

- Wait 1-2 minutes for the droplet to be created
- **Note down the IP address** displayed (e.g., `159.89.123.45`)

---

## Part 2: Connect to Your Droplet

### 2.1 SSH into the Droplet

Open your terminal and connect:

```bash
# If using SSH key:
ssh root@YOUR_DROPLET_IP

# If using password:
ssh root@YOUR_DROPLET_IP
# Then enter the password from your email
```

**First time connecting:**
- You'll see a message about host authenticity
- Type `yes` and press Enter

**Change root password (if using password auth):**
```bash
passwd
# Enter new password twice
```

### 2.2 Add SSH Key from Windows (If Setup Was Done on Another Machine)

If you set up the droplet on a different machine (e.g., Linux/Mac) and need to access it from Windows:

**Step 1: Generate SSH Key on Windows**

Open PowerShell and run:

```powershell
# Generate new SSH key
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# Press Enter to accept default location (C:\Users\YourUsername\.ssh\id_rsa)
# Press Enter twice for no passphrase (or enter a passphrase for extra security)
```

**Step 2: Display Your Public Key**

```powershell
# Display the public key
cat $env:USERPROFILE\.ssh\id_rsa.pub

# Copy the entire output (starts with "ssh-rsa" and ends with your email)
```

**Step 3: Add Key to Droplet**

You have two options:

**Option A: Using Your Arch Linux Machine (Easiest)**

1. Copy the public key you just displayed
2. SSH into the droplet from your Arch Linux machine:
   ```bash
   ssh root@YOUR_DROPLET_IP
   ```
3. On the droplet, add the Windows public key:
   ```bash
   # Append the Windows public key to authorized_keys
   echo "PASTE_YOUR_WINDOWS_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
   
   # Set correct permissions
   chmod 600 ~/.ssh/authorized_keys
   chmod 700 ~/.ssh
   ```

**Option B: Using DigitalOcean Web Console**

1. Log into DigitalOcean dashboard
2. Go to your droplet
3. Click "Access" → "Launch Droplet Console"
4. Run the same commands as Option A

**Step 4: Test Connection from Windows**

```powershell
# Test SSH connection
ssh root@YOUR_DROPLET_IP

# If successful, you'll be logged in without entering a password
```

---

## Part 3: Install MongoDB

### Option A: Automated Setup (Recommended)

We've created a script that automates the entire MongoDB setup.

**On your droplet, run:**

```bash
# Download the setup script
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/nu_choate_league/main/scripts/setup_mongodb_droplet.sh -o setup_mongodb.sh

# Make it executable
chmod +x setup_mongodb.sh

# Run the script
./setup_mongodb.sh
```

**Follow the prompts:**
1. Enter MongoDB admin username (e.g., `admin`)
2. Enter secure admin password
3. Enter application username (e.g., `nuchoate_app`)
4. Enter application password

**Save the connection string shown at the end!** You'll need it later.

---

### Option B: Manual Setup

If you prefer to install manually, follow these steps:

#### 3.1 Update System

```bash
apt update && apt upgrade -y
```

#### 3.2 Install Dependencies

```bash
apt install -y curl gnupg software-properties-common
```

#### 3.3 Add MongoDB Repository

```bash
# Import MongoDB GPG key
curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | \
   gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor

# Add MongoDB repository
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/8.0 multiverse" | \
    tee /etc/apt/sources.list.d/mongodb-org-8.0.list

# Update package list
apt update
```

#### 3.4 Install MongoDB

```bash
apt install -y mongodb-org
```

#### 3.5 Start MongoDB

```bash
systemctl start mongod
systemctl enable mongod
systemctl status mongod
```

#### 3.6 Create Admin User

```bash
mongosh
```

Then in the MongoDB shell:

```javascript
use admin;

db.createUser({
  user: "admin",
  pwd: "YOUR_SECURE_PASSWORD",  // Change this!
  roles: [
    { role: "userAdminAnyDatabase", db: "admin" },
    { role: "readWriteAnyDatabase", db: "admin" },
    { role: "dbAdminAnyDatabase", db: "admin" }
  ]
});

exit
```

#### 3.7 Create Application User

```bash
mongosh
```

```javascript
use nu_choate_league;

db.createUser({
  user: "nuchoate_app",
  pwd: "YOUR_APP_PASSWORD",  // Change this!
  roles: [
    { role: "readWrite", db: "nu_choate_league" }
  ]
});

exit
```

#### 3.8 Enable Authentication

```bash
nano /etc/mongod.conf
```

Find the `#security:` line and uncomment/edit it:

```yaml
security:
  authorization: enabled
```

#### 3.9 Allow Remote Connections

In the same file, find:

```yaml
net:
  port: 27017
  bindIp: 127.0.0.1
```

Change to:

```yaml
net:
  port: 27017
  bindIp: 0.0.0.0
```

Save and exit (Ctrl+X, Y, Enter)

#### 3.10 Restart MongoDB

```bash
systemctl restart mongod
```

#### 3.11 Set Up Firewall

```bash
# Enable firewall
ufw enable

# Allow SSH
ufw allow 22/tcp

# Allow MongoDB (temporarily - we'll restrict this later)
ufw allow 27017/tcp

# Check status
ufw status
```

---

## Part 4: Test the Connection

### 4.1 From the Droplet (Local Test)

```bash
mongosh -u nuchoate_app -p YOUR_APP_PASSWORD --authenticationDatabase nu_choate_league
```

If successful, you'll see the MongoDB shell.

### 4.2 From Your Local Machine

First, install MongoDB tools on your local machine:

**Mac:**
```bash
brew install mongodb-community-shell
```

**Linux:**
```bash
sudo apt install mongodb-mongosh
```

**Windows:**
Download from [MongoDB website](https://www.mongodb.com/try/download/shell)

**Test connection:**
```bash
mongosh "mongodb://nuchoate_app:YOUR_APP_PASSWORD@YOUR_DROPLET_IP:27017/nu_choate_league?authSource=nu_choate_league"
```

If successful, you're connected!

---

## Part 5: Secure Your Database

### 5.1 Restrict MongoDB Access

**IMPORTANT:** Right now, anyone can try to connect to your MongoDB on port 27017. Let's restrict it.

**Option A: Restrict to Your App Platform IP (Coming Soon)**

Once you deploy your FastAPI app to DigitalOcean App Platform, you'll get a static IP. Update firewall:

```bash
# Remove open access
ufw delete allow 27017/tcp

# Allow only from App Platform IP
ufw allow from YOUR_APP_IP to any port 27017
```

**Option B: Use DigitalOcean's Private Network**

Better approach: Put both your app and database on the same private network so they communicate privately.

**Option C: For Development - Use SSH Tunnel**

For now, while developing locally, use SSH tunneling instead of exposing MongoDB:

```bash
# On your local machine, create SSH tunnel:
ssh -L 27017:localhost:27017 root@YOUR_DROPLET_IP

# Now connect to localhost:27017 as if it's your droplet
mongosh "mongodb://nuchoate_app:YOUR_APP_PASSWORD@localhost:27017/nu_choate_league?authSource=nu_choate_league"
```

Then close MongoDB port in firewall:
```bash
# On droplet:
ufw delete allow 27017/tcp
```

### 5.2 Set Up Automatic Backups

Create a backup script:

```bash
nano /root/backup_mongodb.sh
```

Add:

```bash
#!/bin/bash
BACKUP_DIR="/root/mongodb_backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

mongodump --username=admin --password=YOUR_ADMIN_PASSWORD --authenticationDatabase=admin --out=$BACKUP_DIR/backup_$DATE

# Keep only last 7 days of backups
find $BACKUP_DIR -type d -mtime +7 -exec rm -rf {} \;

echo "Backup completed: $DATE"
```

Make it executable:
```bash
chmod +x /root/backup_mongodb.sh
```

Schedule daily backups:
```bash
crontab -e
```

Add this line (runs at 2 AM daily):
```
0 2 * * * /root/backup_mongodb.sh >> /var/log/mongodb_backup.log 2>&1
```

### 5.3 Enable MongoDB Monitoring

```bash
# Check MongoDB logs
tail -f /var/log/mongodb/mongod.log

# Check MongoDB status
systemctl status mongod

# Check resource usage
htop  # or: top
```

---

## Part 6: Connection String for Your App

Your MongoDB connection string should look like:

```
mongodb://nuchoate_app:YOUR_APP_PASSWORD@YOUR_DROPLET_IP:27017/nu_choate_league?authSource=nu_choate_league
```

**Save this in your local `.env` file:**

```bash
MONGODB_URI=mongodb://nuchoate_app:YOUR_APP_PASSWORD@YOUR_DROPLET_IP:27017/nu_choate_league?authSource=nu_choate_league
```

---

## Part 7: Next Steps

Now that MongoDB is set up:

1. ✅ **MongoDB is running** on your droplet
2. ✅ **Users are created** (admin + app user)
3. ✅ **Authentication is enabled**
4. ✅ **Firewall is configured**

**Next:**
1. Create local `.env` file with connection string
2. Run the migration script to import your JSON data
3. Build the FastAPI backend
4. Deploy to App Platform

---

## Troubleshooting

### MongoDB won't start
```bash
# Check logs
journalctl -u mongod -n 50

# Check config syntax
cat /etc/mongod.conf
```

### Can't connect remotely
```bash
# Check if MongoDB is listening on all interfaces
netstat -tulpn | grep 27017

# Should show: 0.0.0.0:27017

# Check firewall
ufw status
```

### Authentication fails
```bash
# Try connecting with admin user first
mongosh -u admin -p --authenticationDatabase admin

# Then check if app user exists
use nu_choate_league
db.getUsers()
```

### Forgot password
```bash
# Disable auth temporarily
nano /etc/mongod.conf
# Comment out the security section

systemctl restart mongod

# Reset password
mongosh
use admin
db.changeUserPassword("admin", "new_password")

# Re-enable auth and restart
```

---

## Cost Summary

- **Droplet**: $6/month
- **Backups** (optional): $1.20/month
- **Total**: ~$7.20/month

With your $200 credit, this runs free for **27+ months**!

---

## Useful Commands Reference

```bash
# Start MongoDB
systemctl start mongod

# Stop MongoDB
systemctl stop mongod

# Restart MongoDB
systemctl restart mongod

# Check status
systemctl status mongod

# View logs
journalctl -u mongod -f

# Connect to MongoDB shell
mongosh -u nuchoate_app -p --authenticationDatabase nu_choate_league

# Check disk usage
df -h

# Check memory
free -h

# Monitor in real-time
htop
```

---

## Support

If you encounter issues:
1. Check the [MongoDB Documentation](https://www.mongodb.com/docs/manual/)
2. Check DigitalOcean's [MongoDB tutorials](https://www.digitalocean.com/community/tags/mongodb)
3. Review system logs: `journalctl -u mongod`

---

**Next Document**: See `MIGRATION_SCRIPT_GUIDE.md` for importing your data into MongoDB.
