#!/bin/bash

################################################################################
# MongoDB Installation Script for DigitalOcean Droplet
# Ubuntu 22.04/24.04 LTS
#
# Usage: 
#   1. SSH into your droplet: ssh root@YOUR_DROPLET_IP
#   2. Download this script: wget https://raw.githubusercontent.com/YOUR_USERNAME/nu_choate_league/main/scripts/setup_mongodb_droplet.sh
#   3. Make executable: chmod +x setup_mongodb_droplet.sh
#   4. Run: ./setup_mongodb_droplet.sh
################################################################################

set -e  # Exit on any error

echo "======================================"
echo "MongoDB Setup for Nu Choate League"
echo "======================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    print_error "Please run as root (use: sudo ./setup_mongodb_droplet.sh)"
    exit 1
fi

# Step 1: Update system
print_info "Updating system packages..."
apt update && apt upgrade -y
print_success "System updated"

# Step 2: Install required dependencies
print_info "Installing dependencies..."
apt install -y curl gnupg software-properties-common
print_success "Dependencies installed"

# Step 3: Add MongoDB GPG key
print_info "Adding MongoDB GPG key..."
curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | \
   gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor
print_success "MongoDB GPG key added"

# Step 4: Add MongoDB repository
print_info "Adding MongoDB repository..."
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/8.0 multiverse" | \
    tee /etc/apt/sources.list.d/mongodb-org-8.0.list
apt update
print_success "MongoDB repository added"

# Step 5: Install MongoDB
print_info "Installing MongoDB (this may take a few minutes)..."
apt install -y mongodb-org
print_success "MongoDB installed"

# Step 6: Start MongoDB
print_info "Starting MongoDB service..."
systemctl start mongod
systemctl enable mongod
print_success "MongoDB service started and enabled"

# Step 7: Wait for MongoDB to be ready
print_info "Waiting for MongoDB to be ready..."
sleep 5
print_success "MongoDB is ready"

# Step 8: Create admin user
print_info "Setting up MongoDB authentication..."
echo ""
echo "Please enter a username for MongoDB admin:"
read -p "Username: " MONGO_ADMIN_USER

echo "Please enter a secure password for MongoDB admin:"
read -sp "Password: " MONGO_ADMIN_PASS
echo ""

# Create admin user
mongosh --eval "
use admin;
db.createUser({
  user: '$MONGO_ADMIN_USER',
  pwd: '$MONGO_ADMIN_PASS',
  roles: [
    { role: 'userAdminAnyDatabase', db: 'admin' },
    { role: 'readWriteAnyDatabase', db: 'admin' },
    { role: 'dbAdminAnyDatabase', db: 'admin' }
  ]
});
" > /dev/null 2>&1

print_success "Admin user created"

# Step 9: Create application database user
print_info "Creating application database user..."
echo "Please enter a username for your application:"
read -p "App Username: " MONGO_APP_USER

echo "Please enter a password for your application:"
read -sp "App Password: " MONGO_APP_PASS
echo ""

mongosh --eval "
use nu_choate_league;
db.createUser({
  user: '$MONGO_APP_USER',
  pwd: '$MONGO_APP_PASS',
  roles: [
    { role: 'readWrite', db: 'nu_choate_league' }
  ]
});
" > /dev/null 2>&1

print_success "Application user created"

# Step 10: Enable authentication
print_info "Enabling MongoDB authentication..."
sed -i 's/#security:/security:\n  authorization: enabled/' /etc/mongod.conf
print_success "Authentication enabled in config"

# Step 11: Configure MongoDB to listen on all interfaces (for remote access)
print_info "Configuring MongoDB for remote access..."
sed -i 's/bindIp: 127.0.0.1/bindIp: 0.0.0.0/' /etc/mongod.conf
print_success "MongoDB configured for remote access"

# Step 12: Restart MongoDB to apply changes
print_info "Restarting MongoDB..."
systemctl restart mongod
sleep 3
print_success "MongoDB restarted"

# Step 13: Set up firewall
print_info "Configuring firewall..."
ufw --force enable
ufw allow 22/tcp  # SSH
ufw allow 27017/tcp  # MongoDB (we'll restrict this later)
print_success "Firewall configured"

# Step 14: Display connection information
echo ""
echo "======================================"
echo "MongoDB Setup Complete!"
echo "======================================"
echo ""
echo "Connection Details:"
echo "-------------------"
echo "Host: $(curl -s http://169.254.169.254/metadata/v1/interfaces/public/0/ipv4/address)"
echo "Port: 27017"
echo "Admin User: $MONGO_ADMIN_USER"
echo "App User: $MONGO_APP_USER"
echo "Database: nu_choate_league"
echo ""
echo "Connection String:"
echo "mongodb://$MONGO_APP_USER:$MONGO_APP_PASS@$(curl -s http://169.254.169.254/metadata/v1/interfaces/public/0/ipv4/address):27017/nu_choate_league?authSource=nu_choate_league"
echo ""
echo "IMPORTANT SECURITY NOTES:"
echo "-------------------------"
echo "1. Save your connection string securely (you'll need it for your app)"
echo "2. Restrict MongoDB port 27017 to only your app's IP address"
echo "3. Consider setting up automatic backups"
echo "4. Keep MongoDB updated with: apt update && apt upgrade"
echo ""
echo "Next Steps:"
echo "-----------"
echo "1. Test the connection from your local machine"
echo "2. Add the connection string to your .env file"
echo "3. Run the migration script to import your data"
echo ""
print_success "Setup complete!"
