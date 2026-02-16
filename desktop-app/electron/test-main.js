const { app, BrowserWindow } = require('electron');
const path = require('path');

console.log('Test: Starting minimal Electron app...');
console.log('app exists:', !!app);
console.log('app.whenReady exists:', !!app?.whenReady);

app.whenReady().then(() => {
    console.log('App is ready!');

    const win = new BrowserWindow({
        width: 400,
        height: 300
    });

    win.loadFile(path.join(__dirname, 'splash.html'));
});

app.on('window-all-closed', () => {
    app.quit();
});
