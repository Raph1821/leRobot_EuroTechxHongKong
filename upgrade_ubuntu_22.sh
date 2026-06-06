#!/bin/bash
# Upgrade Ubuntu 20.04 to 22.04 in WSL
# This will allow us to install ROS2 Humble which has all the required features

set -e

echo "========================================="
echo "Upgrading Ubuntu 20.04 to 22.04"
echo "========================================="
echo ""
echo "This will take 30-60 minutes and requires:"
echo "  - Stable internet connection"
echo "  - ~5GB free disk space"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

# Update current packages
echo "Step 1/5: Updating current packages..."
sudo apt update
sudo apt upgrade -y
sudo apt dist-upgrade -y
sudo apt autoremove -y

# Install update-manager-core
echo "Step 2/5: Installing update manager..."
sudo apt install -y update-manager-core

# Ensure we can upgrade to LTS releases
echo "Step 3/5: Configuring release upgrader..."
sudo sed -i 's/Prompt=.*/Prompt=lts/' /etc/update-manager/release-upgrades

# Run the upgrade
echo "Step 4/5: Starting Ubuntu upgrade to 22.04..."
echo "You may be prompted several times during this process."
echo "Choose the default options (press Enter) when asked."
sudo do-release-upgrade -f DistUpgradeViewNonInteractive

echo ""
echo "Step 5/5: Verifying upgrade..."
lsb_release -a

echo ""
echo "========================================="
echo "Ubuntu upgrade complete!"
echo "========================================="
echo ""
echo "Now you can install ROS2 Humble."
echo ""
