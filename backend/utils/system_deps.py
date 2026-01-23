"""
System Dependencies Manager
Ensures required system dependencies are installed
"""
import subprocess
import shutil
import logging
import os

logger = logging.getLogger(__name__)

def check_and_install_libreoffice():
    """
    Check if LibreOffice is installed and install it if not.
    This ensures the PPT conversion always works, even after container restarts.
    """
    # Check if libreoffice is available and working
    libreoffice_path = shutil.which('libreoffice')
    
    if libreoffice_path:
        # Verify it actually works
        try:
            result = subprocess.run(
                [libreoffice_path, '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and 'LibreOffice' in result.stdout:
                logger.info(f"✓ LibreOffice found at: {libreoffice_path}")
                return True
        except Exception as e:
            logger.warning(f"LibreOffice found but not working: {e}")
    
    logger.warning("⚠ LibreOffice not found or not working. Attempting to install...")
    
    try:
        # First, fix any dpkg issues
        logger.info("Fixing any dpkg issues...")
        subprocess.run(
            ['sudo', 'dpkg', '--configure', '-a'],
            capture_output=True,
            timeout=120
        )
        
        # Update package list
        logger.info("Updating package list...")
        subprocess.run(
            ['sudo', 'apt-get', 'update', '-qq'],
            capture_output=True,
            timeout=120
        )
        
        # Install libreoffice and poppler-utils
        logger.info("Installing LibreOffice and poppler-utils...")
        install_cmd = [
            'sudo', 'apt-get', 'install', '-y', '-qq',
            'libreoffice', 'poppler-utils'
        ]
        subprocess.run(install_cmd, check=True, capture_output=True, timeout=300)
        
        # Verify installation
        libreoffice_path = shutil.which('libreoffice')
        if libreoffice_path:
            logger.info(f"✓ LibreOffice installed successfully at: {libreoffice_path}")
            
            # Get version
            try:
                version_result = subprocess.run(
                    ['libreoffice', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                logger.info(f"  Version: {version_result.stdout.strip()}")
            except Exception:
                pass
            
            return True
        else:
            logger.error("✗ LibreOffice installation failed - not found after install")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("✗ LibreOffice installation timed out")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ LibreOffice installation failed: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error installing LibreOffice: {e}")
        return False


def check_and_install_poppler():
    """
    Check if poppler-utils (pdftoppm) is installed.
    """
    pdftoppm_path = shutil.which('pdftoppm')
    
    if pdftoppm_path:
        logger.info(f"✓ poppler-utils found at: {pdftoppm_path}")
        return True
    
    logger.warning("⚠ poppler-utils not found. Attempting to install...")
    
    try:
        install_cmd = [
            'sudo', 'apt-get', 'install', '-y', '-qq', 'poppler-utils'
        ]
        subprocess.run(install_cmd, check=True, capture_output=True, timeout=120)
        
        pdftoppm_path = shutil.which('pdftoppm')
        if pdftoppm_path:
            logger.info(f"✓ poppler-utils installed successfully at: {pdftoppm_path}")
            return True
        else:
            logger.error("✗ poppler-utils installation failed")
            return False
    except Exception as e:
        logger.error(f"✗ Error installing poppler-utils: {e}")
        return False


def ensure_system_dependencies():
    """
    Ensure all required system dependencies are installed.
    Call this at application startup.
    """
    logger.info("=" * 50)
    logger.info("Checking system dependencies...")
    logger.info("=" * 50)
    
    libreoffice_ok = check_and_install_libreoffice()
    poppler_ok = check_and_install_poppler()
    
    if libreoffice_ok and poppler_ok:
        logger.info("=" * 50)
        logger.info("✓ All system dependencies are ready!")
        logger.info("=" * 50)
        return True
    else:
        logger.warning("=" * 50)
        logger.warning("⚠ Some dependencies may be missing. PPT conversion may fail.")
        logger.warning("=" * 50)
        return False


def get_libreoffice_path():
    """
    Get the path to LibreOffice executable.
    Returns None if not found.
    """
    # Try common paths
    common_paths = [
        '/usr/bin/libreoffice',
        '/usr/bin/soffice',
        '/usr/local/bin/libreoffice',
        '/opt/libreoffice/program/soffice',
    ]
    
    # First try which
    path = shutil.which('libreoffice')
    if path:
        return path
    
    path = shutil.which('soffice')
    if path:
        return path
    
    # Try common paths
    for p in common_paths:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    
    return None
