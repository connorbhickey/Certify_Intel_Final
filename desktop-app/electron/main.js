/**
 * Certify Intel Desktop Application
 * Main Electron Process
 *
 * Features:
 * - DESKTOP-003: Sentry crash reporting (free tier)
 * - DESKTOP-002: Auto-update testing support
 */

const { app, BrowserWindow, Tray, Menu, dialog, shell, ipcMain, safeStorage } = require('electron');
const { autoUpdater } = require('electron-updater');
const log = require('electron-log');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

// ============================================================================
// DESKTOP-003: Sentry Crash Reporting Integration (Free Tier)
// ============================================================================
let Sentry = null;
const SENTRY_DSN = process.env.SENTRY_DSN || '';  // Set via environment variable

function initSentry() {
    if (!SENTRY_DSN) {
        log.info('Sentry DSN not configured - crash reporting disabled');
        return;
    }

    try {
        Sentry = require('@sentry/electron');
        Sentry.init({
            dsn: SENTRY_DSN,
            release: `certify-intel@${app.getVersion()}`,
            environment: process.env.NODE_ENV || 'production',

            // Performance monitoring (free tier limits apply)
            tracesSampleRate: 0.1,  // 10% of transactions

            // Only send errors in production
            enabled: process.env.NODE_ENV !== 'development',

            // Filter out noisy errors
            beforeSend(event, hint) {
                const error = hint.originalException;

                // Ignore network errors (common and expected)
                if (error?.message?.includes('net::ERR_') ||
                    error?.message?.includes('ENOTFOUND') ||
                    error?.message?.includes('ECONNREFUSED')) {
                    return null;
                }

                // Ignore update check errors (handled separately)
                if (error?.message?.includes('Unable to find latest')) {
                    return null;
                }

                return event;
            },

            // Add context
            initialScope: {
                tags: {
                    platform: process.platform,
                    arch: process.arch,
                    electron: process.versions.electron,
                    node: process.versions.node
                }
            }
        });

        log.info('Sentry crash reporting initialized');
    } catch (err) {
        log.warn('Sentry initialization failed (package may not be installed):', err.message);
    }
}

// Capture unhandled errors
process.on('uncaughtException', (error) => {
    log.error('Uncaught Exception:', error);
    if (Sentry) {
        Sentry.captureException(error);
    }
});

process.on('unhandledRejection', (reason) => {
    log.error('Unhandled Rejection:', reason);
    if (Sentry) {
        Sentry.captureException(reason);
    }
});

// ============================================================================
// DESKTOP-002: Auto-Update Testing Support
// ============================================================================
const updateTestConfig = {
    enabled: process.env.UPDATE_TEST_MODE === 'true',
    mockServerUrl: process.env.UPDATE_TEST_SERVER || 'http://localhost:9999',
    forceUpdate: process.env.FORCE_UPDATE === 'true'
};

function configureUpdateTesting() {
    if (updateTestConfig.enabled) {
        log.info('=== AUTO-UPDATE TEST MODE ENABLED ===');
        log.info('Mock server URL:', updateTestConfig.mockServerUrl);

        // Override update feed URL for testing
        autoUpdater.setFeedURL({
            provider: 'generic',
            url: updateTestConfig.mockServerUrl
        });

        // Force update check
        if (updateTestConfig.forceUpdate) {
            autoUpdater.forceDevUpdateConfig = true;
        }
    }
}

// IPC handler for update testing from renderer
ipcMain.handle('update-test-check', async () => {
    log.info('Manual update check triggered via IPC');
    try {
        const result = await autoUpdater.checkForUpdates();
        return {
            success: true,
            updateInfo: result?.updateInfo || null,
            cancellationToken: result?.cancellationToken ? 'present' : null
        };
    } catch (error) {
        return {
            success: false,
            error: error.message
        };
    }
});

ipcMain.handle('update-test-download', async () => {
    log.info('Manual update download triggered via IPC');
    try {
        await autoUpdater.downloadUpdate();
        return { success: true };
    } catch (error) {
        return { success: false, error: error.message };
    }
});

ipcMain.handle('update-test-install', () => {
    log.info('Manual update install triggered via IPC');
    autoUpdater.quitAndInstall(false, true);
    return { success: true };
});

ipcMain.handle('update-get-version', () => {
    return {
        version: app.getVersion(),
        platform: process.platform,
        arch: process.arch
    };
});

// Get update status for testing
ipcMain.handle('update-get-status', () => {
    return {
        autoDownload: autoUpdater.autoDownload,
        autoInstallOnAppQuit: autoUpdater.autoInstallOnAppQuit,
        allowPrerelease: autoUpdater.allowPrerelease,
        currentVersion: app.getVersion(),
        testMode: updateTestConfig.enabled,
        feedUrl: autoUpdater.getFeedURL?.() || 'default'
    };
});

// DAP-003: Secure credential storage
const CREDENTIALS_FILE = path.join(app.getPath('userData'), 'secure-credentials.json');

function readSecureCredentials() {
    try {
        if (fs.existsSync(CREDENTIALS_FILE)) {
            const data = fs.readFileSync(CREDENTIALS_FILE, 'utf8');
            return JSON.parse(data);
        }
    } catch (err) {
        log.error('Error reading credentials:', err);
    }
    return {};
}

function writeSecureCredentials(credentials) {
    try {
        fs.writeFileSync(CREDENTIALS_FILE, JSON.stringify(credentials, null, 2), 'utf8');
    } catch (err) {
        log.error('Error writing credentials:', err);
    }
}

// DAP-003: IPC handlers for secure storage
ipcMain.handle('secure-storage-available', () => {
    return safeStorage.isEncryptionAvailable();
});

ipcMain.handle('secure-storage-set', (event, key, value) => {
    try {
        if (safeStorage.isEncryptionAvailable()) {
            const encrypted = safeStorage.encryptString(value);
            const credentials = readSecureCredentials();
            credentials[key] = encrypted.toString('base64');
            writeSecureCredentials(credentials);
            return true;
        }
        return false;
    } catch (err) {
        log.error('Error storing credential:', err);
        return false;
    }
});

ipcMain.handle('secure-storage-get', (event, key) => {
    try {
        if (safeStorage.isEncryptionAvailable()) {
            const credentials = readSecureCredentials();
            if (credentials[key]) {
                const encrypted = Buffer.from(credentials[key], 'base64');
                return safeStorage.decryptString(encrypted);
            }
        }
        return null;
    } catch (err) {
        log.error('Error retrieving credential:', err);
        return null;
    }
});

ipcMain.handle('secure-storage-delete', (event, key) => {
    try {
        const credentials = readSecureCredentials();
        if (credentials[key]) {
            delete credentials[key];
            writeSecureCredentials(credentials);
            return true;
        }
        return false;
    } catch (err) {
        log.error('Error deleting credential:', err);
        return false;
    }
});

// Configure logging
log.transports.file.level = 'info';
autoUpdater.logger = log;
autoUpdater.logger.transports.file.level = 'info';

// DAP-005: Enhanced auto-updater configuration
autoUpdater.autoDownload = false;  // Ask user before downloading
autoUpdater.autoInstallOnAppQuit = true;  // Install when app closes
autoUpdater.allowPrerelease = false;  // Only stable releases
autoUpdater.allowDowngrade = false;  // Don't allow downgrading
autoUpdater.forceDevUpdateConfig = false;  // Use production config

// Set update feed URL from package.json publish config
try {
    const packageInfo = require('../package.json');
    if (packageInfo.build && packageInfo.build.publish) {
        log.info('Update provider:', packageInfo.build.publish.provider);
        log.info('Update repo:', `${packageInfo.build.publish.owner}/${packageInfo.build.publish.repo}`);
    }
} catch (err) {
    log.info('Could not read package.json for update config');
}

// Keep references to prevent garbage collection
let mainWindow = null;
let tray = null;
let backendProcess = null;

// Backend health watchdog state
let healthCheckInterval = null;
let consecutiveFailures = 0;
const MAX_FAILURES = 3;
app.isQuitting = false;

// Path configurations
const isDev = process.env.NODE_ENV === 'development';
const isVersionA = process.env.BUILD_VERSION !== 'B';

function getResourcePath(relativePath) {
    if (isDev) {
        return path.join(__dirname, '..', relativePath);
    }
    return path.join(process.resourcesPath, relativePath);
}

// ============================================================================
// PRE-LAUNCH CLEANUP: Kill orphaned processes and free port 8000
// This prevents "Failed to start backend" errors from orphaned processes
// ============================================================================
async function cleanupBeforeStart() {
    const { execSync } = require('child_process');

    log.info('=== PRE-LAUNCH CLEANUP ===');

    if (process.platform === 'win32') {
        try {
            // Kill any orphaned certify_backend.exe processes
            log.info('Checking for orphaned certify_backend.exe processes...');
            try {
                execSync('taskkill /F /IM certify_backend.exe', { stdio: 'pipe' });
                log.info('Killed orphaned certify_backend.exe');
            } catch (e) {
                // No process found - this is fine
                log.info('No orphaned certify_backend.exe found');
            }

            // Check if port 8000 is in use and kill the process
            log.info('Checking if port 8000 is in use...');
            try {
                const netstatOutput = execSync('netstat -ano | findstr :8000 | findstr LISTENING', { encoding: 'utf8', stdio: 'pipe' });
                const lines = netstatOutput.trim().split('\n');
                for (const line of lines) {
                    const parts = line.trim().split(/\s+/);
                    const pid = parts[parts.length - 1];
                    if (pid && !isNaN(parseInt(pid))) {
                        log.info(`Port 8000 in use by PID ${pid}, killing...`);
                        try {
                            execSync(`taskkill /F /PID ${pid}`, { stdio: 'pipe' });
                            log.info(`Killed process ${pid}`);
                        } catch (killErr) {
                            log.warn(`Could not kill PID ${pid}:`, killErr.message);
                        }
                    }
                }
            } catch (e) {
                // No process on port 8000 - this is fine
                log.info('Port 8000 is free');
            }
        } catch (err) {
            log.warn('Pre-launch cleanup error (non-fatal):', err.message);
        }
    } else {
        // macOS/Linux cleanup
        try {
            try {
                execSync('pkill -f certify_backend', { stdio: 'pipe' });
                log.info('Killed orphaned certify_backend processes');
            } catch (e) {
                log.info('No orphaned certify_backend found');
            }

            try {
                const lsofOutput = execSync('lsof -ti:8000', { encoding: 'utf8', stdio: 'pipe' });
                const pids = lsofOutput.trim().split('\n');
                for (const pid of pids) {
                    if (pid) {
                        execSync(`kill -9 ${pid}`, { stdio: 'pipe' });
                        log.info(`Killed process ${pid} on port 8000`);
                    }
                }
            } catch (e) {
                log.info('Port 8000 is free');
            }
        } catch (err) {
            log.warn('Pre-launch cleanup error (non-fatal):', err.message);
        }
    }

    // Small delay to ensure processes are fully terminated
    await new Promise(resolve => setTimeout(resolve, 500));
    log.info('=== PRE-LAUNCH CLEANUP COMPLETE ===');
}

// Backend server management
function startBackend() {
    const fs = require('fs');
    const backendPath = isDev
        ? path.join(__dirname, '..', '..', 'backend', 'main.py')
        : path.join(getResourcePath('backend-bundle'), process.platform === 'win32' ? 'certify_backend.exe' : 'certify_backend');

    log.info('Starting backend from:', backendPath);
    log.info('isDev:', isDev);
    log.info('resourcesPath:', process.resourcesPath);
    log.info('Backend exists:', fs.existsSync(backendPath));

    // Check if backend file exists
    if (!fs.existsSync(backendPath)) {
        log.error('Backend executable not found at:', backendPath);
        log.error('Directory contents:', fs.readdirSync(path.dirname(backendPath)));
        return;
    }

    const cwd = path.dirname(backendPath);
    log.info('Working directory:', cwd);

    if (isDev) {
        // Development: run Python directly
        backendProcess = spawn('python', ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8000'], {
            cwd: path.join(__dirname, '..', '..', 'backend'),
            env: { ...process.env }
        });
    } else {
        // Production: run bundled executable
        backendProcess = spawn(backendPath, [], {
            cwd: cwd,
            env: { ...process.env, DATA_PATH: getResourcePath('data') },
            stdio: ['pipe', 'pipe', 'pipe']
        });
    }

    // Handle spawn errors
    backendProcess.on('error', (err) => {
        log.error('Failed to start backend:', err.message);
    });

    backendProcess.stdout.on('data', (data) => {
        log.info(`Backend: ${data}`);
    });

    backendProcess.stderr.on('data', (data) => {
        log.error(`Backend Error: ${data}`);
    });

    backendProcess.on('close', (code) => {
        log.info(`[Backend] Process exited with code ${code}`);
        if (code !== 0 && code !== null && mainWindow && !app.isQuitting) {
            handleBackendCrash();
        }
    });
}

function stopBackend() {
    if (backendProcess) {
        log.info('Stopping backend...');
        if (process.platform === 'win32') {
            spawn('taskkill', ['/pid', backendProcess.pid, '/f', '/t']);
        } else {
            backendProcess.kill('SIGTERM');
        }
        backendProcess = null;
    }
}

// Wait for backend to be ready
// Backend takes ~25-35s to fully initialize (Gemini provider, SQLAlchemy, scrapers)
// 60 retries × ~2s each = ~120s max wait time
async function waitForBackend(maxRetries = 60) {
    const http = require('http');

    for (let i = 0; i < maxRetries; i++) {
        try {
            await new Promise((resolve, reject) => {
                const req = http.get('http://127.0.0.1:8000/api/health', (res) => {
                    if (res.statusCode === 200) resolve();
                    else reject();
                });
                req.on('error', reject);
                req.setTimeout(2000, () => { req.destroy(); reject(new Error('timeout')); });
            });
            log.info('Backend is ready!');
            return true;
        } catch {
            if (i % 5 === 0 || i >= maxRetries - 5) {
                log.info(`Waiting for backend... (${i + 1}/${maxRetries})`);
            }
            await new Promise(r => setTimeout(r, 2000));
        }
    }
    return false;
}

// ============================================================================
// Backend Health Watchdog & Crash Recovery
// ============================================================================
function startBackendHealthCheck() {
    if (healthCheckInterval) clearInterval(healthCheckInterval);
    consecutiveFailures = 0;

    healthCheckInterval = setInterval(() => {
        const http = require('http');
        const req = http.get('http://127.0.0.1:8000/api/health', { timeout: 5000 }, (res) => {
            consecutiveFailures = 0;
        });

        req.on('error', () => {
            consecutiveFailures++;
            log.info(`[HealthCheck] Backend unreachable (${consecutiveFailures}/${MAX_FAILURES})`);
            if (consecutiveFailures >= MAX_FAILURES && mainWindow) {
                clearInterval(healthCheckInterval);
                healthCheckInterval = null;
                handleBackendCrash();
            }
        });

        req.on('timeout', () => {
            req.destroy();
            consecutiveFailures++;
            log.info(`[HealthCheck] Backend timeout (${consecutiveFailures}/${MAX_FAILURES})`);
            if (consecutiveFailures >= MAX_FAILURES && mainWindow) {
                clearInterval(healthCheckInterval);
                healthCheckInterval = null;
                handleBackendCrash();
            }
        });
    }, 30000);
}

async function handleBackendCrash() {
    const result = await dialog.showMessageBox(mainWindow, {
        type: 'error',
        title: 'Backend Connection Lost',
        message: 'The backend server stopped responding. Would you like to restart it?',
        buttons: ['Restart', 'Quit'],
        defaultId: 0,
        cancelId: 1
    });

    if (result.response === 0) {
        try {
            if (backendProcess) {
                backendProcess.kill();
                backendProcess = null;
            }

            if (mainWindow) {
                mainWindow.loadURL(`data:text/html,<html><body style="background:#1a1a2e;color:white;display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif"><h2>Restarting backend server...</h2></body></html>`);
            }

            startBackend();

            await waitForBackend();

            if (mainWindow) {
                mainWindow.loadURL('http://127.0.0.1:8000/login.html');
            }

            startBackendHealthCheck();
        } catch (err) {
            log.error('[CrashRecovery] Failed to restart:', err);
            dialog.showErrorBox('Restart Failed', 'Could not restart the backend. Please close and reopen the application.');
        }
    } else {
        app.quit();
    }
}

// Create main window
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1024,
        minHeight: 768,
        title: isVersionA ? 'Certify Intel' : 'CompetitorIQ',
        icon: path.join(__dirname, '..', 'resources', 'icons', 'icon.png'),
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: false,
            contextIsolation: true
        },
        show: false // Show after ready
    });

    // v7.0.5: Force clear browser and service worker cache on startup
    // This prevents stale cached versions from being served
    log.info('Clearing browser cache and service worker storage...');
    mainWindow.webContents.session.clearCache().then(() => {
        log.info('Browser cache cleared');
    }).catch(err => {
        log.warn('Failed to clear browser cache:', err.message);
    });
    mainWindow.webContents.session.clearStorageData({
        storages: ['serviceworkers', 'cachestorage']
    }).then(() => {
        log.info('Service worker cache cleared');
    }).catch(err => {
        log.warn('Failed to clear service worker cache:', err.message);
    });

    // DAP-001 FIX: Load login page first, not /app directly
    // This ensures users must authenticate before accessing the dashboard
    mainWindow.loadURL('http://127.0.0.1:8000/login.html');

    // Show when ready
    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
        mainWindow.focus();
    });

    // Handle external links
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        shell.openExternal(url);
        return { action: 'deny' };
    });

    // Cleanup on close
    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

// System tray
function createTray() {
    const iconPath = path.join(__dirname, '..', 'resources', 'icons', 'icon.png');

    if (fs.existsSync(iconPath)) {
        tray = new Tray(iconPath);

        const contextMenu = Menu.buildFromTemplate([
            { label: 'Open Certify Intel', click: () => mainWindow?.show() },
            { type: 'separator' },
            { label: 'Check for Updates', click: () => autoUpdater.checkForUpdates() },
            { type: 'separator' },
            { label: 'Quit', click: () => app.quit() }
        ]);

        tray.setToolTip(isVersionA ? 'Certify Intel' : 'CompetitorIQ');
        tray.setContextMenu(contextMenu);

        tray.on('double-click', () => mainWindow?.show());
    }
}

// Auto-updater events
autoUpdater.on('checking-for-update', () => {
    log.info('Checking for updates...');
});

autoUpdater.on('update-available', (info) => {
    log.info('Update available:', info.version);

    dialog.showMessageBox({
        type: 'info',
        title: 'Update Available',
        message: `A new version (${info.version}) is available!`,
        detail: 'Would you like to download and install it now?',
        buttons: ['Download Now', 'Later'],
        defaultId: 0
    }).then((result) => {
        if (result.response === 0) {
            autoUpdater.downloadUpdate();
        }
    });
});

autoUpdater.on('update-not-available', () => {
    log.info('No updates available - app is up to date');
});

autoUpdater.on('download-progress', (progress) => {
    log.info(`Download progress: ${Math.round(progress.percent)}%`);

    // Show progress in taskbar/dock
    if (mainWindow) {
        mainWindow.setProgressBar(progress.percent / 100);
    }
});

autoUpdater.on('update-downloaded', (info) => {
    log.info('Update downloaded:', info.version);

    // Clear progress bar
    if (mainWindow) {
        mainWindow.setProgressBar(-1);
    }

    // Check if this is a critical update
    const isCritical = info.releaseNotes?.includes('[CRITICAL]') ||
                       info.releaseNotes?.includes('[SECURITY]');

    if (isCritical) {
        dialog.showMessageBox({
            type: 'warning',
            title: 'Critical Security Update',
            message: 'A critical security update must be installed now.',
            detail: `Version ${info.version} contains important security fixes.`,
            buttons: ['Install Now'],
            defaultId: 0
        }).then(() => {
            autoUpdater.quitAndInstall(true, true);
        });
    } else {
        dialog.showMessageBox({
            type: 'info',
            title: 'Update Ready',
            message: 'Update downloaded!',
            detail: 'The update will be installed when you close the app. Restart now?',
            buttons: ['Restart Now', 'Later'],
            defaultId: 0
        }).then((result) => {
            if (result.response === 0) {
                autoUpdater.quitAndInstall(false, true);
            }
        });
    }
});

autoUpdater.on('error', (err) => {
    log.error('AutoUpdater error:', err);

    // DAP-004 & DAP-006 FIX: Graceful error handling - suppress popup for common/expected errors
    // Only show error dialog for truly unexpected errors, not network issues or missing releases
    const errorMessage = err?.message || '';
    const suppressedErrors = [
        'net::ERR',                    // Network connectivity issues
        'ENOTFOUND',                   // DNS resolution failure
        'ECONNREFUSED',                // Connection refused
        'ETIMEDOUT',                   // Connection timeout
        'Unable to find latest',       // No releases published yet
        'Cannot find latest',          // No releases published yet
        '404',                         // Release not found
        'getaddrinfo',                 // DNS issues
        'socket hang up',              // Connection dropped
        'CERT_',                       // SSL certificate issues
        'self signed',                 // Self-signed cert
        'HttpError'                    // Generic HTTP errors during update check
    ];

    const shouldSuppress = suppressedErrors.some(pattern => errorMessage.includes(pattern));

    if (!shouldSuppress) {
        // Only show dialog for unexpected errors
        dialog.showMessageBox({
            type: 'warning',
            title: 'Update Check Issue',
            message: 'Could not check for updates',
            detail: 'The app will continue to work normally. You can check for updates later from the system tray.',
            buttons: ['OK']
        });
    } else {
        // Log silently for expected errors
        log.info('Update check skipped (expected):', errorMessage.substring(0, 100));
    }
});

// App lifecycle
app.whenReady().then(async () => {
    log.info('App starting...');
    log.info('Version:', app.getVersion());
    log.info('Build type:', isVersionA ? 'Certify Health Edition' : 'White-Label Template');

    // DESKTOP-003: Initialize Sentry crash reporting
    initSentry();

    // DESKTOP-002: Configure update testing if enabled
    configureUpdateTesting();

    // Show loading splash
    const splash = new BrowserWindow({
        width: 400,
        height: 300,
        frame: false,
        transparent: true,
        alwaysOnTop: true,
        webPreferences: { nodeIntegration: false }
    });

    splash.loadFile(path.join(__dirname, 'splash.html'));
    splash.center();

    // CRITICAL: Clean up orphaned processes and free port 8000 before starting
    await cleanupBeforeStart();

    // Start backend server
    startBackend();

    // Wait for backend to be ready
    const backendReady = await waitForBackend();

    if (!backendReady) {
        splash.close();
        dialog.showErrorBox('Startup Error', 'Failed to start the backend server. Please try again.');
        app.quit();
        return;
    }

    // Create main window
    createWindow();
    createTray();

    // Start backend health monitoring
    startBackendHealthCheck();

    // Close splash
    splash.close();

    // Check for updates (production only)
    if (!isDev) {
        // Initial check 10 seconds after startup
        setTimeout(() => {
            log.info('Performing initial update check...');
            autoUpdater.checkForUpdates();
        }, 10000);

        // Check every 4 hours while app is running
        setInterval(() => {
            log.info('Performing periodic update check...');
            autoUpdater.checkForUpdates();
        }, 4 * 60 * 60 * 1000);
    }
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (mainWindow === null) {
        createWindow();
    }
});

app.on('before-quit', () => {
    app.isQuitting = true;
    if (healthCheckInterval) {
        clearInterval(healthCheckInterval);
        healthCheckInterval = null;
    }
    stopBackend();
});

// Prevent multiple instances
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
    app.quit();
} else {
    app.on('second-instance', () => {
        if (mainWindow) {
            if (mainWindow.isMinimized()) mainWindow.restore();
            mainWindow.focus();
        }
    });
}
