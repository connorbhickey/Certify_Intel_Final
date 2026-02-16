#!/usr/bin/env python3
"""
Certify Intel Backend - Entry Point for PyInstaller

This module serves as the entry point when the backend is bundled
with PyInstaller for desktop app distribution.

Usage:
    Development: python -m backend (from project root)
    Production:  certify_backend.exe (bundled executable)
"""
import sys
import os

# =============================================================================
# CRITICAL: Load .env FIRST before ANY other imports!
# This ensures GOOGLE_AI_API_KEY is available when gemini_provider imports
# =============================================================================
def _early_env_load():
    """Load .env file as early as possible, before other modules import."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle - get exe directory
        exe_dir = os.path.dirname(sys.executable)
        env_file = os.path.join(exe_dir, '.env')
    else:
        # Running as normal Python script
        exe_dir = os.path.dirname(os.path.abspath(__file__))
        env_file = os.path.join(exe_dir, '.env')

    if os.path.exists(env_file):
        print(f"[EARLY ENV] Loading .env from: {env_file}")
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # Remove quotes if present
                        if value and value[0] in ('"', "'") and value[-1] == value[0]:
                            value = value[1:-1]
                        os.environ[key] = value
            # Verify critical keys loaded
            google_key = os.environ.get('GOOGLE_AI_API_KEY', '')
            print(f"[EARLY ENV] GOOGLE_AI_API_KEY loaded: {bool(google_key)} (length: {len(google_key)})")
        except Exception as e:
            print(f"[EARLY ENV] Error loading .env: {e}")
    else:
        print(f"[EARLY ENV] No .env file found at {env_file}")

# Execute early env load BEFORE any other imports
_early_env_load()

import logging

logger = logging.getLogger("certify_intel")

def get_bundle_dir():
    """Get the directory where PyInstaller extracts bundled files."""
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller bundle
        # sys._MEIPASS is the temp folder where PyInstaller extracts files
        return sys._MEIPASS
    else:
        # Running as a normal Python script
        return os.path.dirname(os.path.abspath(__file__))

def get_exe_dir():
    """Get the directory where the actual .exe file is located."""
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller bundle - get the directory containing the .exe
        return os.path.dirname(sys.executable)
    else:
        # Running as a normal Python script
        return os.path.dirname(os.path.abspath(__file__))

def setup_environment():
    """Set up the environment for the backend to run correctly."""
    bundle_dir = get_bundle_dir()
    exe_dir = get_exe_dir()

    # Add bundle directory to Python path
    if bundle_dir not in sys.path:
        sys.path.insert(0, bundle_dir)

    # IMPORTANT: Load .env from the exe directory (where user places config files)
    # NOT from the temp extraction directory
    if getattr(sys, 'frozen', False):
        env_file = os.path.join(exe_dir, '.env')
        if os.path.exists(env_file):
            logger.info(f"Loading .env from: {env_file}")
            # Manually load .env file
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            os.environ[key.strip()] = value.strip()
            except Exception as e:
                logger.error(f"Could not load .env file: {e}")
        else:
            logger.warning(f"No .env file found at {env_file}")

        # ALWAYS set database path to exe directory (v5.0.3 fix)
        # This ensures database is created next to exe, not in temp folder
        db_file = os.path.join(exe_dir, 'certify_intel.db')
        os.environ['DATABASE_URL'] = f'sqlite:///{db_file}'
        if os.path.exists(db_file):
            logger.info(f"Using existing database: {db_file}")
        else:
            logger.info(f"Database will be created at: {db_file}")

        # Store exe_dir for later use
        os.environ['CERTIFY_EXE_DIR'] = exe_dir

    # Set working directory to bundle dir for relative file access (internal resources)
    os.chdir(bundle_dir)

    # Set environment variable to indicate we're running bundled
    if getattr(sys, 'frozen', False):
        os.environ['CERTIFY_BUNDLED'] = 'true'

    return bundle_dir

def main():
    """Main entry point for the Certify Intel backend."""
    bundle_dir = setup_environment()
    exe_dir = get_exe_dir()

    logger.info("Certify Intel Backend Starting...")
    logger.info(f"Bundle directory: {bundle_dir}")
    logger.info(f"Executable directory: {exe_dir}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Frozen: {getattr(sys, 'frozen', False)}")

    # Debug: Show loaded environment variables (without secrets)
    logger.info(f"SECRET_KEY loaded: {'Yes' if os.getenv('SECRET_KEY') else 'No'}")
    logger.info(f"OPENAI_API_KEY loaded: {'Yes' if os.getenv('OPENAI_API_KEY') else 'No'}")
    logger.info(f"DATABASE_URL: {os.getenv('DATABASE_URL', 'Not set')}")

    # Import uvicorn and the FastAPI app
    try:
        import uvicorn
        from main import app

        # Configuration for the server
        config = {
            "host": "127.0.0.1",
            "port": 8000,
            "log_level": "info",
            "access_log": True,
        }

        # In production (frozen), disable reload
        if not getattr(sys, 'frozen', False):
            config["reload"] = True

        logger.info(f"Starting server on http://{config['host']}:{config['port']}")

        # Run the server
        uvicorn.run(app, **config)

    except ImportError as e:
        logger.error(f"Error importing dependencies: {e}")
        logger.error("Make sure all dependencies are installed: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
