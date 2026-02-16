# Certify Intel Desktop Application

## Overview

This folder contains the Electron-based desktop application wrapper for Certify Intel. It packages the web application as a native desktop app for Windows and Mac.

## Project Structure

```
desktop-app/
├── electron/
│   ├── main.js           # Main Electron process
│   ├── preload.js        # Security bridge
│   ├── splash.html       # Loading screen
│   └── setup-wizard.html # First-run setup (Version B)
├── resources/
│   └── icons/            # App icons
├── package.json          # Dependencies & build config
├── build-windows.bat     # Windows build script
└── build-mac.sh          # Mac build script
```

## Prerequisites

1. **Node.js 18+** - [Download](https://nodejs.org/)
2. **Python 3.9+** - [Download](https://python.org/)
3. **PyInstaller** - `pip install pyinstaller`

## Building the Application

### Version A (Certify Health Client)

Pre-loaded with competitor data and API keys.

```bash
# Windows
build-windows.bat A

# Mac
./build-mac.sh A
```

### Version B (White-Label Template)

Blank template for resale.

```bash
# Windows
build-windows.bat B

# Mac
./build-mac.sh B
```

## Output Files

After building, installers are in the `dist/` folder:

| Platform | File |
|:---------|:-----|
| Windows | `Certify Intel Setup 1.0.0.exe` |
| Mac | `Certify Intel-1.0.0.dmg` |

## Development

Run in development mode (uses existing backend):

```bash
npm install
npm start
```

## Auto-Updates

Updates are delivered via GitHub Releases. To publish an update:

1. Update version in `package.json`
2. Build the application
3. Create a GitHub Release with the installers
4. Users will receive update automatically

## 🚀 Distribution (For Non-Technical Users)

You have two parts:

1. **The Installer File** (`Certify Intel Setup 1.0.0.exe`) - This is the actual app.
2. **The Download Page** (`website/index.html`) - This is what you send to people.

### Step 1: Host the File

1. Upload the `.exe` file to Google Drive.
2. Right-click > Share > "Anyone with the link".
3. Copy the link.

### Step 2: Set up the Download Page

1. Open `website/index.html` in a text editor.
2. Replace `YOUR_GOOGLE_DRIVE_LINK_HERE` with the link you copied.
3. Save the file.

### Step 3: Send it

- You can host the `website` folder on GitHub Pages, Netlify, or your company server.
- Send that link to your team.
- They click "Download", run the file, and it just works. No technical steps required.

## Post-Installation Configuration (IMPORTANT)

After installing the application, users must configure their environment:

### Step 1: Locate the Installation Directory

The app is installed to (Windows):
```
C:\Users\<username>\AppData\Local\Programs\certify-intel\
```

### Step 2: Create the .env File

1. Find `.env.example` in the installation directory
2. Copy it and rename to `.env`
3. Edit `.env` with your configuration:

```env
# Required
SECRET_KEY=your-secret-key-here

# AI Features (at least one required)
OPENAI_API_KEY=sk-your-openai-key
GOOGLE_AI_API_KEY=your-gemini-key

# Optional News APIs
GNEWS_API_KEY=your-gnews-key
MEDIASTACK_API_KEY=your-mediastack-key
```

### Step 3: Restart the Application

Close and reopen the application for changes to take effect.

> **Note**: The database (`certify_intel.db`) will be created automatically in the installation directory on first run.

## Customization (Version B)

The white-label template can be customized by modifying:

- `electron/main.js` - Window title, app name
- `resources/icons/` - App icons
- `package.json` - Product name, appId
- Frontend files - Branding, colors

## Troubleshooting

### "Failed to start the backend server"

1. **Check .env file exists** - Must be in the same directory as the executable
2. **Check SECRET_KEY is set** - Required for authentication
3. **Check console logs** - Run from command line to see error details:
   ```cmd
   cd "C:\Users\<username>\AppData\Local\Programs\certify-intel"
   certify_backend.exe
   ```

### "401 Unauthorized" after login

1. Clear browser cache and cookies
2. Ensure `SECRET_KEY` in `.env` matches what was used when users were created
3. Try resetting the admin password (see SETUP_GUIDE.md)

### Database not found

The database is automatically created in the installation directory. If missing:
1. Check write permissions on the installation folder
2. Run the app as administrator once to create it
