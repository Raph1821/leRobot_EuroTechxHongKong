#!/bin/bash
# Install ROS2 Humble on Ubuntu 20.04
# This uses the newer ROS2 Humble which has all required features

set -e

echo "========================================="
echo "ROS2 Humble Installation for Ubuntu 20.04"
echo "========================================="
echo ""
echo "Note: ROS2 Humble is officially for Ubuntu 22.04,"
echo "but we'll try to install compatible packages."
echo ""

# First, let's try upgrading to Ubuntu 22.04
echo "We need Ubuntu 22.04 for ROS2 Humble."
echo "Would you like to upgrade Ubuntu 20.04 to 22.04?"
echo ""
read -p "Upgrade to Ubuntu 22.04? (y/n): " -n 1 -r
echo

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting Ubuntu upgrade..."
    
    # Update current system
    sudo apt update
    sudo apt upgrade -y
    sudo apt dist-upgrade -y
    
    # Install update-manager
    sudo apt install -y update-manager-core
    
    # Configure for LTS upgrades
    sudo sed -i 's/Prompt=.*/Prompt=lts/' /etc/update-manager/release-upgrades
    
    # Upgrade to 22.04
    echo ""
    echo "Starting upgrade to Ubuntu 22.04 (Jammy)..."
    echo "This will take 30-60 minutes. You'll be prompted several times."
    echo "Press Enter to accept defaults when asked."
    echo ""
    sudo do-release-upgrade
    
    echo ""
    echo "Upgrade complete! Please reboot WSL and run this script again."
    echo "To reboot: Exit WSL and run 'wsl --shutdown' then restart."
    exit 0
else
    echo "Cannot install ROS2 Humble without Ubuntu 22.04."
    echo "Please upgrade manually or use ROS2 Foxy."
    exit 1
fi
