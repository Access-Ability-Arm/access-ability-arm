# UFactory Studio Installation and Setup

UFactory Studio is the official software for configuring and controlling UFactory robotic arms, including the Lite6. It's recommended to install this alongside the Access Ability Arm application.

## What is UFactory Studio?

UFactory Studio provides:
- **Initial arm setup and configuration**
- **Manual control and jogging**
- **Finding the arm's IP address**
- **Firmware updates**
- **Safety configuration**
- **Teaching pendant simulation**
- **Blockly programming interface**

## Installation

### 1. Download UFactory Studio

**Official Download:**
- Visit: https://www.ufactory.cc/download/
- Or direct link: https://www.ufactory.cc/ufactory-studio/
- Select your operating system (Windows, macOS, or Linux)
- Download the latest version

**System Requirements:**
- **Windows**: Windows 10 or later (64-bit)
- **macOS**: macOS 10.14 or later
- **Linux**: Ubuntu 18.04 or later

### 2. Install UFactory Studio

**macOS:**
```bash
# Open the downloaded .dmg file
# Drag UFactory Studio to Applications folder
# On first launch, you may need to allow it in System Preferences > Security & Privacy
```

**Windows:**
```bash
# Run the downloaded installer (.exe)
# Follow the installation wizard
# Launch UFactory Studio from the Start Menu
```

**Linux:**
```bash
# Extract the downloaded archive
tar -xzf ufactory-studio-*.tar.gz
cd ufactory-studio
./ufactory-studio

# Or install via AppImage (if provided)
chmod +x UFactory-Studio-*.AppImage
./UFactory-Studio-*.AppImage
```

## Finding Your Lite6 Arm IP Address

This is the most important step for configuring the Access Ability Arm application.

### Method 1: Using UFactory Studio (Recommended)

1. **Connect the arm to your network**
   - Use an Ethernet cable to connect the Lite6 to your router/switch
   - Power on the arm

2. **Launch UFactory Studio**

3. **Search for arms**
   - Click "Search" or "Scan" button
   - UFactory Studio will discover all arms on your network
   - The IP address will be displayed next to the arm

4. **Note the IP address**
   - Example: `192.168.1.203`
   - You'll need this for the Access Ability Arm configuration

### Method 2: Using the Arm's Display (if available)

1. Power on the Lite6 arm
2. Check the control box display for network settings
3. Navigate to Settings > Network > IP Address

### Method 3: Using Router Admin Panel

1. Log into your router's admin panel
2. Look for connected devices or DHCP client list
3. Find device named "xArm" or with UFactory MAC address
4. Note the assigned IP address

## Initial Arm Setup

Before using with Access Ability Arm, configure the arm in UFactory Studio:

### 1. Connect to the Arm

1. Launch UFactory Studio
2. Click "Search" to find your arm
3. Click "Connect" next to your Lite6

### 2. Configure Safety Settings

1. Go to **Settings > Safety**
2. Set appropriate limits:
   - **Joint Speed Limit**: 180°/s (default)
   - **Joint Acceleration**: 1145°/s² (default)
   - **TCP Speed Limit**: 1000 mm/s (default)
   - **TCP Acceleration**: 10000 mm/s² (default)

3. Configure safety boundaries:
   - Set workspace limits based on your setup
   - Enable collision detection
   - Set reduced mode parameters if needed

### 3. Set Home Position

1. Go to **Manual Control**
2. Use jogging controls to move arm to desired home position
3. Click **"Save as Home"**
4. This position will be used by the Access Ability Arm app

### 4. Test Basic Movements

1. In **Manual Control** tab:
   - Test jogging in all axes (X, Y, Z, Roll, Pitch, Yaw)
   - Test gripper open/close
   - Verify smooth motion without errors

2. If you encounter issues:
   - Check error messages in the log
   - Verify all connections are secure
   - Ensure arm has sufficient power

### 5. Update Firmware (if needed)

1. Go to **Settings > About**
2. Check current firmware version
3. If update available, click **"Update Firmware"**
4. Follow on-screen instructions
5. Do not power off during update

## Configuring Access Ability Arm

After finding your IP address in UFactory Studio:

### Option 1: Interactive Setup
```bash
cd /path/to/access-ability-arm
python scripts/setup_config.py
```
- Select option to configure arm settings
- Enter the IP address from UFactory Studio
- Test the connection

### Option 2: Quick Update
```bash
python scripts/update_config.py
```
- Select option 1: "Arm IP address"
- Enter the IP address
- Test the connection

### Option 3: Manual Configuration
```bash
# Edit config/config.yaml
nano config/config.yaml

# Update the arm section:
arm:
  ip: "192.168.1.203"  # Your arm's IP from UFactory Studio
  port: 502
  auto_connect: true
```

## Network Configuration Tips

### Static IP (Recommended)

For reliable operation, assign a static IP to your Lite6:

**Method 1: Via Router DHCP Reservation**
1. Find the Lite6's MAC address in UFactory Studio
2. Log into your router admin panel
3. Create a DHCP reservation for this MAC address
4. Assign a static IP (e.g., 192.168.1.203)

**Method 2: Via UFactory Studio** (if supported)
1. Connect to arm in UFactory Studio
2. Go to Settings > Network
3. Switch from DHCP to Static
4. Enter desired IP, subnet mask, gateway
5. Save and restart arm

### Firewall Configuration

If you have firewall issues:

**macOS:**
```bash
# Allow UFactory Studio and Python through firewall
# System Preferences > Security & Privacy > Firewall > Firewall Options
# Add UFactory Studio and Python to allowed apps
```

**Windows:**
```bash
# Windows Defender Firewall
# Allow an app through firewall
# Add UFactory Studio and Python
```

**Linux:**
```bash
# Allow Modbus TCP port (502)
sudo ufw allow 502/tcp
```

## Troubleshooting

### Cannot Find Arm in UFactory Studio

1. **Check network connection**
   - Verify Ethernet cable is connected
   - Check router link lights
   - Arm and computer must be on same network

2. **Check arm power**
   - Ensure arm is powered on
   - Check control box LED status

3. **Check firewall**
   - Temporarily disable firewall to test
   - Add UFactory Studio to allowed apps

4. **Try direct connection**
   - Connect arm directly to computer via Ethernet
   - Configure computer's Ethernet to same subnet as arm
   - Default arm IP is often 192.168.1.xxx

### Connection Errors in Access Ability Arm

1. **Verify IP address**
   - Double-check IP in UFactory Studio
   - Ping the arm: `ping 192.168.1.203`

2. **Check port**
   - Modbus TCP port should be 502 (default)
   - Ensure no other app is using the port

3. **Test in UFactory Studio first**
   - If UFactory Studio can connect, Access Ability Arm should too
   - If UFactory Studio cannot connect, fix network issues first

### Arm Not Responding

1. **Check mode and state**
   - Arm must be in position mode (mode 0)
   - Arm must be in ready state (state 0)
   - UFactory Studio shows current mode/state

2. **Check for errors**
   - View error log in UFactory Studio
   - Clear errors if needed
   - Reset arm if persistent issues

3. **Emergency stop**
   - If emergency stop is engaged, release it
   - Wait for arm to initialize

## Reference

- **Official Documentation**: https://help.ufactory.cc/
- **SDK Documentation**: https://github.com/xArm-Developer/xArm-Python-SDK
- **Support**: support@ufactory.cc
- **Forum**: https://forum.ufactory.cc/

## See Also

- [Installation Guide](installation.md) - Setting up Access Ability Arm
- [Configuration Guide](../README.md#configuration) - Configuring the application
- [Lite6 Driver Package](../packages/lite6_driver/README.md) - Python SDK wrapper
