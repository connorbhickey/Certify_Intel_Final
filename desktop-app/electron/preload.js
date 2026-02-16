/**
 * Preload Script - Security Bridge
 * Exposes safe APIs to the renderer process
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    // App info
    getVersion: () => ipcRenderer.invoke('get-version'),
    isVersionA: () => ipcRenderer.invoke('is-version-a'),

    // Updates
    checkForUpdates: () => ipcRenderer.send('check-updates'),
    onUpdateAvailable: (callback) => ipcRenderer.on('update-available', callback),
    onUpdateDownloaded: (callback) => ipcRenderer.on('update-downloaded', callback),

    // Window controls
    minimize: () => ipcRenderer.send('window-minimize'),
    maximize: () => ipcRenderer.send('window-maximize'),
    close: () => ipcRenderer.send('window-close'),

    // DAP-003: Secure credential storage
    secureStorage: {
        isAvailable: () => ipcRenderer.invoke('secure-storage-available'),
        setCredential: (key, value) => ipcRenderer.invoke('secure-storage-set', key, value),
        getCredential: (key) => ipcRenderer.invoke('secure-storage-get', key),
        deleteCredential: (key) => ipcRenderer.invoke('secure-storage-delete', key)
    },

    // DESKTOP-002: Auto-update testing APIs
    updateTest: {
        checkForUpdates: () => ipcRenderer.invoke('update-test-check'),
        downloadUpdate: () => ipcRenderer.invoke('update-test-download'),
        installUpdate: () => ipcRenderer.invoke('update-test-install'),
        getVersion: () => ipcRenderer.invoke('update-get-version'),
        getStatus: () => ipcRenderer.invoke('update-get-status')
    },

    // Platform info
    platform: process.platform
});
