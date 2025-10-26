#!/usr/bin/env python3
"""
KiCad to Dokuly Plugin Installation Script

This script automates the installation of the KiCad to Dokuly plugin
by detecting the correct KiCad installation directory and copying
the plugin files to the appropriate location.
"""

import os
import sys
import shutil
import platform
from pathlib import Path


def get_kicad_plugin_directory():
    """Detect the correct KiCad plugin directory based on OS and KiCad version"""
    
    # Get user's home directory
    home_dir = Path.home()
    
    if platform.system() == 'Windows':
        # Try KiCad 9.0 first, then 8.0
        possible_paths = [
            home_dir / "Documents" / "KiCad" / "9.0" / "scripting" / "plugins",
            home_dir / "Documents" / "KiCad" / "8.0" / "scripting" / "plugins",
        ]
    elif platform.system() == 'Darwin':  # macOS
        possible_paths = [
            home_dir / "Documents" / "KiCad" / "9.0" / "scripting" / "plugins",
            home_dir / "Documents" / "KiCad" / "8.0" / "scripting" / "plugins",
        ]
    else:  # Linux
        possible_paths = [
            home_dir / "Documents" / "KiCad" / "9.0" / "scripting" / "plugins",
            home_dir / "Documents" / "KiCad" / "8.0" / "scripting" / "plugins",
        ]
    
    # Find the first existing directory
    for path in possible_paths:
        if path.exists():
            return path
    
    # If none exist, create the most recent version directory
    return possible_paths[0]


def create_plugin_directory(plugin_dir):
    """Create the plugin directory if it doesn't exist"""
    plugin_dir.mkdir(parents=True, exist_ok=True)
    print(f"Created plugin directory: {plugin_dir}")


def install_plugin():
    """Install the plugin to the correct KiCad directory"""
    
    print("KiCad to Dokuly Plugin Installer")
    print("=" * 40)
    
    # Get current script directory (where the plugin files are)
    current_dir = Path(__file__).parent
    plugin_name = "kicad-to-dokuly-plugin"
    
    # Get target directory
    target_dir = get_kicad_plugin_directory()
    target_plugin_dir = target_dir / plugin_name
    
    print(f"Source directory: {current_dir}")
    print(f"Target directory: {target_plugin_dir}")
    
    # Check if target directory exists
    if not target_dir.exists():
        print(f"\nKiCad plugin directory not found: {target_dir}")
        create_plugin_directory(target_dir)
    
    # Preserve existing .env file if it exists
    existing_env_file = None
    if target_plugin_dir.exists():
        existing_env = target_plugin_dir / ".env"
        if existing_env.exists():
            print(f"\nPreserving existing .env file...")
            # Read the existing .env file content
            with open(existing_env, 'r') as f:
                existing_env_file = f.read()
            print(f"✅ Found existing .env file with {len(existing_env_file)} characters")
        
        print(f"\nRemoving existing installation...")
        shutil.rmtree(target_plugin_dir)
    
    # Copy plugin files
    print(f"\nInstalling plugin...")
    try:
        shutil.copytree(current_dir, target_plugin_dir)
        print(f"✅ Plugin installed successfully to: {target_plugin_dir}")
        
        # Handle .env file
        env_file = target_plugin_dir / ".env"
        if existing_env_file:
            # Restore the existing .env file
            with open(env_file, 'w') as f:
                f.write(existing_env_file)
            print(f"✅ Restored existing .env file: {env_file}")
        elif not env_file.exists():
            # Create a sample .env file only if none exists
            create_sample_env_file(env_file)
            print(f"✅ Created sample .env file: {env_file}")
        else:
            print(f"✅ Using existing .env file: {env_file}")
        
        print(f"\n🎉 Installation complete!")
        print(f"\nNext steps:")
        print(f"1. Open KiCad")
        print(f"2. Go to Tools > External plugins > Refresh plugins")
        print(f"3. Look for the Dokuly cloud icon in the toolbar")
        print(f"4. Click the icon and use the 'Configure Plugin' button to set up your Dokuly credentials")
        
    except Exception as e:
        print(f"❌ Installation failed: {e}")
        return False
    
    return True


def create_sample_env_file(env_file):
    """Create a sample .env file with default values"""
    
    sample_content = """# KiCad to Dokuly Plugin Configuration
# Replace the values below with your actual Dokuly credentials

# Your Dokuly API Key (obtain from your Dokuly admin page)
DOKULY_API_KEY=your_api_key_here

# Dokuly server URL (use 'dokuly.com' for cloud hosting or 'localhost:8000' for local development)
DOKULY_URL=dokuly.com

# Protocol (https for secure connections, http for local testing)
URL_PROTOCOL=https

# Whether to replace existing files on upload (recommended: true)
REPLACE_FILES=true

# Path to your KiCad theme file (will be auto-detected if possible)
THEME_PATH=

# Path to your KiCad drawing sheet template (will be auto-detected if possible)
DRAWING_SHEET_PATH=
"""
    
    with open(env_file, 'w') as f:
        f.write(sample_content)


def uninstall_plugin():
    """Uninstall the plugin"""
    
    print("KiCad to Dokuly Plugin Uninstaller")
    print("=" * 40)
    
    target_dir = get_kicad_plugin_directory()
    target_plugin_dir = target_dir / "kicad-to-dokuly-plugin"
    
    if target_plugin_dir.exists():
        print(f"Removing plugin from: {target_plugin_dir}")
        shutil.rmtree(target_plugin_dir)
        print("✅ Plugin uninstalled successfully")
    else:
        print("❌ Plugin not found. Nothing to uninstall.")


def main():
    """Main function"""
    
    if len(sys.argv) > 1 and sys.argv[1] == "uninstall":
        uninstall_plugin()
    else:
        install_plugin()


if __name__ == "__main__":
    main()
