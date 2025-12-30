#!/bin/bash
# Nu Choate League Backend Setup Script
# Automates Steps 3-9 of BACKEND_DATABASE_PHASE.md

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root for certain operations
check_sudo() {
    if ! sudo -n true 2>/dev/null; then
        print_warn "This script requires sudo privileges. You may be prompted for your password."
    fi
}

# Get user input with prompt
get_input() {
    local prompt="$1"
    local default="$2"
    local result
    
    if [ -n "$default" ]; then
        read -p "$prompt [$default]: " result
        echo "${result:-$default}"
    else
        read -p "$prompt: " result
        echo "$result"
    fi
}

# Get password input (hidden)
get_password() {
    local prompt="$1"
    local password
    read -sp "$prompt: " password
    echo
    echo "$password"
}

# Main setup function
main() {
    print_info "Nu Choate League Backend Setup"
    print_info "=============================="
    echo
    
    # Check prerequisites
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install it first."
        exit 1
    fi
    
    if ! systemctl is-active --quiet mongodb; then
        print_error "MongoDB is not running. Please start it first: sudo systemctl start mongodb"
        exit 1
    fi
    
    # Get Python path
    PYTHON3_PATH=$(command -v python3)
    if [ -z "$PYTHON3_PATH" ]; then
        print_error "python3 not found in PATH"
        exit 1
    fi
    
    # Get configuration
    echo
    print_info "Configuration Setup"
    print_info "-------------------"
    
    USERNAME=$(whoami)
    print_info "Detected username: $USERNAME"
    read -p "Is this correct? (y/n) [y]: " confirm_user
    if [[ "${confirm_user:-y}" != "y" ]]; then
        USERNAME=$(get_input "Enter username")
    fi
    
    HOME_DIR=$(eval echo ~$USERNAME)
    print_info "Using home directory: $HOME_DIR"
    
    # Get project directory
    PROJECT_DIR=$(get_input "Enter project directory" "$HOME_DIR/nu_choate_league")
    if [ ! -d "$PROJECT_DIR" ]; then
        print_warn "Project directory does not exist. Creating it..."
        mkdir -p "$PROJECT_DIR"
    fi
    
    # Get GitHub repository URL
    GITHUB_USER=$(get_input "Enter GitHub username")
    GITHUB_REPO="nu_choate_league"
    GITHUB_URL="https://raw.githubusercontent.com/$GITHUB_USER/$GITHUB_REPO/main"
    
    # Get MongoDB passwords
    echo
    print_info "MongoDB Configuration"
    print_info "---------------------"
    print_warn "You need the passwords for the MongoDB users created in Step 2"
    
    DEV_PASSWORD=$(get_password "Enter password for nu_choate_league_dev database user")
    STAGING_PASSWORD=$(get_password "Enter password for nu_choate_league_staging database user")
    PROD_PASSWORD=$(get_password "Enter password for nu_choate_league_prod database user")
    
    # Get Sleeper League ID
    SLEEPER_LEAGUE_ID=$(get_input "Enter Sleeper League ID" "1251998020954763264")
    
    # Get JWT Secret (generate if not provided)
    JWT_SECRET=$(get_input "Enter JWT Secret (press Enter to generate)" "")
    if [ -z "$JWT_SECRET" ]; then
        JWT_SECRET=$(openssl rand -hex 32)
        print_info "Generated JWT Secret: $JWT_SECRET"
    fi
    
    # Build MongoDB URIs
    DEV_MONGODB_URI="mongodb://nuchoate_app:${DEV_PASSWORD}@localhost:27017/nu_choate_league_dev?authSource=nu_choate_league_dev"
    STAGING_MONGODB_URI="mongodb://nuchoate_app:${STAGING_PASSWORD}@localhost:27017/nu_choate_league_staging?authSource=nu_choate_league_staging"
    PROD_MONGODB_URI="mongodb://nuchoate_app:${PROD_PASSWORD}@localhost:27017/nu_choate_league_prod?authSource=nu_choate_league_prod"
    
    echo
    print_info "Starting setup..."
    echo
    
    # Step 3: Install Python and Dependencies
    print_info "Step 3: Installing Python dependencies..."
    if ! command -v pip3 &> /dev/null; then
        print_info "Installing pip..."
        sudo pacman -S --noconfirm python-pip
    fi
    
    print_info "Installing Python packages..."
    pip3 install --user pymongo requests fastapi uvicorn[standard] motor python-dotenv pydantic pydantic-settings httpx aiohttp python-jose[cryptography] passlib[bcrypt] python-multipart
    
    # Download sync script
    print_info "Downloading sync script..."
    cd "$HOME_DIR"
    curl -fsSL "${GITHUB_URL}/sync_sleeper_to_mongodb.py" -o sync_sleeper_to_mongodb.py
    chmod +x sync_sleeper_to_mongodb.py
    
    # Step 4: Set up FastAPI Backend
    print_info "Step 4: Setting up FastAPI backend..."
    
    BACKEND_DIR="$PROJECT_DIR/misc/backend"
    if [ ! -d "$BACKEND_DIR" ]; then
        print_warn "Backend directory not found. Creating structure..."
        mkdir -p "$BACKEND_DIR/app"
        print_warn "You'll need to clone the repository or copy the backend files manually."
        print_warn "Continuing with setup assuming files will be present..."
    fi
    
    # Create .env file for development
    print_info "Creating development .env file..."
    cat > "$BACKEND_DIR/.env" << EOF
MONGODB_URI=$DEV_MONGODB_URI
SLEEPER_LEAGUE_ID=$SLEEPER_LEAGUE_ID
JWT_SECRET=$JWT_SECRET
API_ENV=development
LOG_LEVEL=debug
PORT=8000
EOF
    
    # Step 5: Create systemd service files
    print_info "Step 5: Creating systemd services..."
    
    # Staging service
    print_info "Creating staging service..."
    sudo tee /etc/systemd/system/nuchoate-api-staging.service > /dev/null << EOF
[Unit]
Description=Nu Choate League API - Staging
After=network.target mongodb.service

[Service]
Type=simple
User=$USERNAME
WorkingDirectory=$BACKEND_DIR
EnvironmentFile=/etc/nuchoate-api-staging.env
ExecStart=$PYTHON3_PATH -m uvicorn app.main:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Staging environment file
    print_info "Creating staging environment file..."
    sudo tee /etc/nuchoate-api-staging.env > /dev/null << EOF
MONGODB_URI=$STAGING_MONGODB_URI
SLEEPER_LEAGUE_ID=$SLEEPER_LEAGUE_ID
JWT_SECRET=$JWT_SECRET
API_ENV=staging
LOG_LEVEL=info
PORT=8001
EOF
    
    # Production service
    print_info "Creating production service..."
    sudo tee /etc/systemd/system/nuchoate-api-prod.service > /dev/null << EOF
[Unit]
Description=Nu Choate League API - Production
After=network.target mongodb.service

[Service]
Type=simple
User=$USERNAME
WorkingDirectory=$BACKEND_DIR
EnvironmentFile=/etc/nuchoate-api-prod.env
ExecStart=$PYTHON3_PATH -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Production environment file
    print_info "Creating production environment file..."
    sudo tee /etc/nuchoate-api-prod.env > /dev/null << EOF
MONGODB_URI=$PROD_MONGODB_URI
SLEEPER_LEAGUE_ID=$SLEEPER_LEAGUE_ID
JWT_SECRET=$JWT_SECRET
API_ENV=production
LOG_LEVEL=warning
PORT=8000
EOF
    
    # Reload systemd and enable services
    print_info "Enabling systemd services..."
    sudo systemctl daemon-reload
    sudo systemctl enable nuchoate-api-staging.service
    sudo systemctl enable nuchoate-api-prod.service
    
    # Step 6: Set up nginx
    print_info "Step 6: Setting up nginx..."
    
    if ! command -v nginx &> /dev/null; then
        print_info "Installing nginx..."
        sudo pacman -S --noconfirm nginx
    fi
    
    # Backup original nginx.conf
    if [ -f /etc/nginx/nginx.conf ]; then
        sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup
    fi
    
    # Create nginx configuration
    print_info "Configuring nginx..."
    FRONTEND_DIR=$(get_input "Enter frontend build directory (or press Enter to skip)" "")
    
    sudo tee /etc/nginx/nginx.conf > /dev/null << EOF
user http;
worker_processes auto;
error_log /var/log/nginx/error.log;
pid /run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    log_format main '\$remote_addr - \$remote_user [\$time_local] "\$request" '
                    '\$status \$body_bytes_sent "\$http_referer" '
                    '"\$http_user_agent" "\$http_x_forwarded_for"';
    
    access_log /var/log/nginx/access.log main;
    
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
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
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }
    }
    
    server {
        listen 80;
        server_name localhost;
        
        location /api {
            proxy_pass http://api_prod;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }
EOF
    
    if [ -n "$FRONTEND_DIR" ] && [ -d "$FRONTEND_DIR" ]; then
        sudo tee -a /etc/nginx/nginx.conf > /dev/null << EOF
        
        location / {
            root $FRONTEND_DIR;
            try_files \$uri \$uri/ /index.html;
        }
EOF
    else
        sudo tee -a /etc/nginx/nginx.conf > /dev/null << EOF
        
        location / {
            return 200 "Nu Choate League API - Frontend not configured";
            add_header Content-Type text/plain;
        }
EOF
    fi
    
    sudo tee -a /etc/nginx/nginx.conf > /dev/null << EOF
    }
}
EOF
    
    # Enable and start nginx
    print_info "Starting nginx..."
    sudo systemctl enable nginx
    sudo systemctl start nginx
    
    # Step 7: Configure scheduled jobs
    print_info "Step 7: Configuring scheduled jobs..."
    
    # Create sync service
    print_info "Creating sync service..."
    sudo tee /etc/systemd/system/nuchoate-sync.service > /dev/null << EOF
[Unit]
Description=Nu Choate League Data Sync
After=network.target mongodb.service

[Service]
Type=oneshot
User=$USERNAME
WorkingDirectory=$HOME_DIR
EnvironmentFile=/etc/nuchoate-api-prod.env
ExecStart=$PYTHON3_PATH $HOME_DIR/sync_sleeper_to_mongodb.py --env prod
EOF
    
    # Create sync timer
    print_info "Creating sync timer..."
    sudo tee /etc/systemd/system/nuchoate-sync.timer > /dev/null << EOF
[Unit]
Description=Nu Choate League Data Sync Timer
Requires=nuchoate-sync.service

[Timer]
OnCalendar=daily
OnCalendar=Mon..Sun *-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF
    
    # Enable timer
    print_info "Enabling sync timer..."
    sudo systemctl daemon-reload
    sudo systemctl enable nuchoate-sync.timer
    sudo systemctl start nuchoate-sync.timer
    
    # Summary
    echo
    print_info "Setup Complete!"
    print_info "==============="
    echo
    print_info "Next steps:"
    echo "  1. Test the API services:"
    echo "     sudo systemctl start nuchoate-api-staging.service"
    echo "     sudo systemctl start nuchoate-api-prod.service"
    echo "     curl http://localhost:8001/"
    echo "     curl http://localhost:8000/"
    echo
    echo "  2. Run initial data sync:"
    echo "     export MONGODB_URI=\"$DEV_MONGODB_URI\""
    echo "     python3 $HOME_DIR/sync_sleeper_to_mongodb.py --env dev"
    echo
    echo "  3. Check service status:"
    echo "     sudo systemctl status nuchoate-api-staging.service"
    echo "     sudo systemctl status nuchoate-api-prod.service"
    echo "     sudo systemctl status nuchoate-sync.timer"
    echo
    echo "  4. View logs:"
    echo "     sudo journalctl -u nuchoate-api-staging.service -f"
    echo "     sudo journalctl -u nuchoate-api-prod.service -f"
    echo
    print_warn "Note: Make sure the backend code is in $BACKEND_DIR before starting services."
}

# Run main function
main "$@"

