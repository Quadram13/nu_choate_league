#!/bin/bash
# Xfce4 Desktop Environment Setup with Windows 95 Theme
# Based on: https://gitlab.com/linux-stuffs/xts-themes/-/tree/main/xts-windows95-theme

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

# Check if running as regular user (not root)
if [ "$EUID" -eq 0 ]; then
    print_error "Please run this script as a regular user (not root)"
    exit 1
fi

# Get user input
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

main() {
    print_info "Xfce4 Desktop Environment Setup with Windows 95 Theme"
    print_info "======================================================"
    echo
    
    # Get configuration
    THEME_REPO_DIR=$(get_input "Enter directory to clone theme repo" "$HOME/xts-themes")
    
    print_info "Starting installation..."
    echo
    
    # Step 1: Install Xfce4 and base packages
    print_info "Step 1: Installing Xfce4 desktop environment..."
    sudo pacman -S --needed --noconfirm \
        xorg-server \
        xorg-xinit \
        xfce4 \
        xfce4-goodies \
        lightdm \
        lightdm-gtk-greeter \
        firefox \
        base-devel \
        git \
        wget \
        yajl \
        gtk-engine-murrine
    
    # Step 2: Install yay (AUR helper) if not present
    print_info "Step 2: Checking for yay (AUR helper)..."
    if ! command -v yay &> /dev/null; then
        print_info "Installing yay..."
        cd /tmp
        git clone https://aur.archlinux.org/yay.git
        cd yay
        makepkg -si --noconfirm
        cd ~
        rm -rf /tmp/yay
    else
        print_info "yay is already installed"
    fi
    
    # Step 3: Install Chicago95 components from AUR
    print_info "Step 3: Installing Chicago95 theme components from AUR..."
    print_warn "This may take a while as it compiles from source..."
    
    yay -S --noconfirm \
        chicago95-gtk-theme-git \
        chicago95-icon-theme-git \
        xcursor-chicago95-git
    
    # Step 4: Install Xfce4 Theme Switcher from AUR
    print_info "Step 4: Installing Xfce4 Theme Switcher from AUR..."
    yay -S --noconfirm xfce4-theme-switcher
    
    # Step 5: Clone and install Windows 95 theme
    print_info "Step 5: Setting up Windows 95 theme..."
    
    if [ -d "$THEME_REPO_DIR" ]; then
        print_warn "Theme directory already exists: $THEME_REPO_DIR"
        read -p "Remove and re-clone? (y/n) [n]: " remove_existing
        if [[ "${remove_existing:-n}" == "y" ]]; then
            rm -rf "$THEME_REPO_DIR"
        else
            print_info "Using existing directory"
        fi
    fi
    
    if [ ! -d "$THEME_REPO_DIR" ]; then
        print_info "Cloning theme repository from GitLab..."
        git clone "https://gitlab.com/linux-stuffs/xts-themes.git" "$THEME_REPO_DIR" || {
            print_error "Failed to clone repository"
            exit 1
        }
    fi
    
    # Navigate to the Windows 95 theme directory
    THEME_DIR="$THEME_REPO_DIR/xts-windows95-theme"
    if [ ! -d "$THEME_DIR" ]; then
        print_error "Theme directory not found: $THEME_DIR"
        exit 1
    fi
    
    cd "$THEME_DIR"
    
    # Build and install the theme
    print_info "Building and installing Windows 95 theme..."
    ./configure
    make
    sudo make install
    
    # Step 6: Run postinstall script
    print_info "Step 6: Running theme postinstall script..."
    if [ -f "theme-src/Windows-95/postinstall.sh" ]; then
        bash theme-src/Windows-95/postinstall.sh
    else
        print_warn "Postinstall script not found, skipping..."
    fi
    
    # Step 7: Set up display manager
    print_info "Step 7: Configuring display manager..."
    
    # Enable lightdm service
    sudo systemctl enable lightdm.service
    
    # Create .xprofile if it doesn't exist (for Xfce4 to start properly)
    if [ ! -f "$HOME/.xprofile" ]; then
        print_info "Creating .xprofile..."
        cat > "$HOME/.xprofile" << 'EOF'
# Xfce4 desktop environment
export DESKTOP_SESSION=xfce
export XDG_SESSION_DESKTOP=xfce
EOF
    fi
    
    # Step 8: Configure Xfce4 to use the theme
    print_info "Step 8: Configuring Xfce4 settings..."
    
    # Set Chicago95 GTK theme
    xfconf-query -c xsettings -p /Net/ThemeName -s "Chicago95" 2>/dev/null || true
    xfconf-query -c xsettings -p /Net/IconThemeName -s "Chicago95" 2>/dev/null || true
    xfconf-query -c xsettings -p /Gtk/CursorThemeName -s "Chicago95" 2>/dev/null || true
    
    # Summary
    echo
    print_info "Setup Complete!"
    print_info "==============="
    echo
    print_info "Next steps:"
    echo "  1. Reboot your system:"
    echo "     sudo reboot"
    echo
    echo "  2. After reboot, you should see the lightdm login screen"
    echo "     Log in and Xfce4 with Windows 95 theme will start"
    echo
    echo "  3. If you want to start the desktop manually without rebooting:"
    echo "     startxfce4"
    echo
    echo "  4. Keyboard shortcuts:"
    echo "     - Find applications: Ctrl+Shift or Super+S"
    echo "     - Run command: Super+R"
    echo "     - Terminal: Super+Return"
    echo "     - Web Browser: Super+W"
    echo "     - Close window: Alt+F4"
    echo "     - Task manager: Ctrl+Shift+Escape"
    echo "     - Logout: Ctrl+Alt+Delete"
    echo
    print_warn "Note: The theme will be fully applied after you log in to Xfce4"
    
    # Ask if user wants to start Xfce4 now
    echo
    read -p "Start Xfce4 now? (y/n) [n]: " start_now
    if [[ "${start_now:-n}" == "y" ]]; then
        print_info "Starting Xfce4..."
        startxfce4
    fi
}

# Run main function
main "$@"

