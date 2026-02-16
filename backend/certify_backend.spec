# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller Spec File for Certify Intel Backend

This specification file defines how PyInstaller should bundle the
Certify Intel backend into a standalone executable.

Build commands:
    Windows: pyinstaller certify_backend.spec --clean --noconfirm
    macOS:   pyinstaller certify_backend.spec --clean --noconfirm

Output:
    dist/certify_backend.exe (Windows)
    dist/certify_backend (macOS/Linux)
"""

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all

block_cipher = None

# Collect ALL data, binaries, and hiddenimports for critical packages
fastapi_datas, fastapi_binaries, fastapi_hiddenimports = collect_all('fastapi')
starlette_datas, starlette_binaries, starlette_hiddenimports = collect_all('starlette')
pydantic_datas, pydantic_binaries, pydantic_hiddenimports = collect_all('pydantic')
uvicorn_datas, uvicorn_binaries, uvicorn_hiddenimports = collect_all('uvicorn')

# Collect data files from packages that need them
datas = [
    # Include .env.example as template
    ('.env.example', '.'),
]

# Include the database file if it exists (not in CI environments)
if os.path.exists('certify_intel.db'):
    datas.append(('certify_intel.db', '.'))
else:
    print("INFO: certify_intel.db not found - skipping (will be created on first run)")

# Collect data files for Google GenAI SDK
try:
    google_genai_datas = collect_data_files('google.genai')
    datas += google_genai_datas
except Exception as e:
    print(f"Warning: Could not collect google.genai data files: {e}")
try:
    google_ai_datas = collect_data_files('google.ai.generativelanguage')
    datas += google_ai_datas
except Exception as e:
    print(f"Warning: Could not collect google.ai.generativelanguage data files: {e}")

# Add collected data files from critical packages
datas += fastapi_datas
datas += starlette_datas
datas += pydantic_datas
datas += uvicorn_datas

# Check if templates directory exists
if os.path.exists('templates'):
    datas.append(('templates', 'templates'))

# Hidden imports - packages that PyInstaller can't detect automatically
hiddenimports = [
    # Uvicorn and ASGI
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.websockets_impl',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',

    # FastAPI and Starlette
    'fastapi',
    'starlette',
    'starlette.responses',
    'starlette.routing',
    'starlette.middleware',
    'starlette.middleware.cors',

    # SQLAlchemy + async
    'sqlalchemy',
    'sqlalchemy.sql.default_comparator',
    'sqlalchemy.ext.declarative',
    'sqlalchemy.ext.asyncio',
    'sqlalchemy.orm',
    'sqlalchemy.engine',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.dialects.sqlite.aiosqlite',
    'aiosqlite',

    # Authentication
    'passlib',
    'passlib.handlers',
    'passlib.handlers.bcrypt',
    'jose',
    'jose.jwt',

    # AI/ML Libraries
    'openai',
    'anthropic',
    'tiktoken',
    'tiktoken_ext',
    'tiktoken_ext.openai_public',
    'langchain',

    # Data processing
    'pandas',
    'numpy',
    'openpyxl',
    'reportlab',

    # Web scraping
    'playwright',
    'bs4',
    'lxml',
    'html5lib',

    # HTTP clients
    'httpx',
    'requests',

    # Scheduling
    'apscheduler',
    'apscheduler.schedulers',
    'apscheduler.schedulers.background',

    # Utilities
    'dotenv',
    'tenacity',
    'jinja2',

    # Finance
    'yfinance',

    # Export/Report generation
    'pptx',
    'pptx.util',
    'pptx.dml',
    'pptx.dml.color',
    'pptx.enum',
    'pptx.enum.text',
    'weasyprint',

    # Pydantic
    'pydantic',
    'pydantic_core',

    # Email (for alerts)
    'email',
    'email.mime',
    'email.mime.text',
    'email.mime.multipart',
    'smtplib',

    # PIL/Pillow (needed by some dependencies)
    'PIL',
    'PIL._imaging',
    'PIL.Image',

    # Our custom modules
    'database',
    'database_async',
    'analytics',
    'extended_features',
    'discovery_agent',
    'scheduler',
    'alerts',
    'reports',
    'extractor',
    'scraper',
    'glassdoor_scraper',
    'indeed_scraper',
    'sec_edgar_scraper',
    'uspto_scraper',
    'klas_scraper',
    'appstore_scraper',
    'himss_scraper',

    # v7.0 modules - Google GenAI SDK (comprehensive)
    'google',
    'google.genai',
    'google.genai.types',
    'google.genai._api_client',
    'google.genai._common',
    'google.genai.models',
    'google.genai.chats',
    'google.genai.files',
    'google.genai.live',
    'google.genai.caches',
    'google.genai.batches',
    'google.genai.operations',
    'google.genai.tunings',
    'google.ai',
    'google.ai.generativelanguage',
    'google.ai.generativelanguage_v1beta',
    'google.protobuf',
    'google.protobuf.json_format',
    'google.auth',
    'google.auth.transport',
    'google.auth.transport.requests',
    'grpc',
    'grpc._channel',
    'langgraph',
    'langgraph.graph',
    'langgraph.checkpoint',
    'langgraph.checkpoint.memory',
    'agents',
    'agents.base_agent',
    'agents.orchestrator',
    'agents.dashboard_agent',
    'agents.discovery_agent',
    'agents.battlecard_agent',
    'agents.news_agent',
    'agents.analytics_agent',
    'agents.validation_agent',
    'agents.records_agent',
    'agents.citation_validator',
    'knowledge_base',
    'vector_store',
    'ai_router',
    'performance',
    'observability',
    'source_reconciliation',
    'discovery_engine',
    'gemini_provider',
]

# Collect all submodules for complex packages
hiddenimports += collect_submodules('uvicorn')
hiddenimports += collect_submodules('fastapi')
hiddenimports += collect_submodules('starlette')
hiddenimports += collect_submodules('sqlalchemy')
hiddenimports += collect_submodules('pydantic')

# Export packages - collect submodules for proper bundling
try:
    hiddenimports += collect_submodules('pptx')
except Exception as e:
    print(f"Warning: Could not collect pptx submodules: {e}")

# Anthropic SDK - collect submodules for proper bundling
try:
    hiddenimports += collect_submodules('anthropic')
except Exception as e:
    print(f"Warning: Could not collect anthropic submodules: {e}")

# Google GenAI SDK - collect all submodules for proper bundling
try:
    hiddenimports += collect_submodules('google.genai')
except Exception as e:
    print(f"Warning: Could not collect google.genai submodules: {e}")
try:
    hiddenimports += collect_submodules('google.ai.generativelanguage')
except Exception as e:
    print(f"Warning: Could not collect google.ai.generativelanguage submodules: {e}")
try:
    hiddenimports += collect_submodules('google.protobuf')
except Exception as e:
    print(f"Warning: Could not collect google.protobuf submodules: {e}")

# Add collected hiddenimports from critical packages
hiddenimports += fastapi_hiddenimports
hiddenimports += starlette_hiddenimports
hiddenimports += pydantic_hiddenimports
hiddenimports += uvicorn_hiddenimports

# Remove duplicates
hiddenimports = list(set(hiddenimports))

# Collect binaries from critical packages
binaries = []
binaries += fastapi_binaries
binaries += starlette_binaries
binaries += pydantic_binaries
binaries += uvicorn_binaries

# Analysis
a = Analysis(
    ['__main__.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary packages to reduce size
        'tkinter',
        'matplotlib',
        'scipy',
        'cv2',
        'torch',
        'tensorflow',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Create the PYZ archive
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

# Create the executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='certify_backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Use UPX compression if available
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Show console window (useful for debugging)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='../desktop-app/resources/icons/icon.ico' if sys.platform == 'win32' else None,
)

# For macOS, you might want to create an app bundle
# Uncomment below if needed:
# app = BUNDLE(
#     exe,
#     name='Certify Intel Backend.app',
#     icon='../desktop-app/resources/icons/icon.icns',
#     bundle_identifier='com.certifyhealth.intel.backend',
# )
