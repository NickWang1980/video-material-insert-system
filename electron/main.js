'use strict';

const { app, BrowserWindow, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

const PORT = 8000;

// Dev path: adjust this to wherever your Nuitka output lives relative to project root.
// e.g. '../dist_backend/backend.exe' or '../build/main.exe'
const BACKEND_EXE_DEV = path.join(__dirname, '..', 'dist_backend', 'backend.exe');

let backendProcess = null;
let mainWindow = null;

function getBackendPath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'backend', 'backend.exe');
  }
  return BACKEND_EXE_DEV;
}

function getDataDir() {
  if (app.isPackaged) {
    return path.join(app.getPath('userData'), 'data');
  }
  // Dev: let the backend use its own default (repo ./data)
  return undefined;
}

function startBackend() {
  const exePath = getBackendPath();
  const dataDir = getDataDir();

  const env = { ...process.env };
  if (dataDir) {
    env.DATA_DIR = dataDir;
    env.DATABASE_URL = `sqlite:///${path.join(dataDir, 'database.db').replace(/\\/g, '/')}`;
  }

  backendProcess = spawn(exePath, [], {
    env,
    windowsHide: true,
    detached: false,
  });

  backendProcess.on('error', (err) => {
    dialog.showErrorBox('Backend Error', `Failed to start backend:\n${err.message}\n\nPath: ${exePath}`);
    app.quit();
  });

  backendProcess.on('exit', (code, signal) => {
    if (mainWindow && code !== 0 && signal !== 'SIGTERM') {
      dialog.showErrorBox('Backend Crashed', `Backend exited unexpectedly (code ${code}).`);
      app.quit();
    }
  });
}

function pollBackend(retries = 60, intervalMs = 500) {
  return new Promise((resolve, reject) => {
    const attempt = (remaining) => {
      if (remaining <= 0) {
        reject(new Error(`Backend did not respond on port ${PORT} after ${(retries * intervalMs) / 1000}s`));
        return;
      }
      const req = http.get(`http://localhost:${PORT}`, (res) => {
        res.resume(); // drain
        resolve();
      });
      req.setTimeout(800, () => req.destroy());
      req.on('error', () => setTimeout(() => attempt(remaining - 1), intervalMs));
    };
    attempt(retries);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 960,
    minHeight: 600,
    show: false,
    title: 'Video Material Insert System',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  mainWindow.loadURL(`http://localhost:${PORT}`);
  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.on('closed', () => { mainWindow = null; });
}

app.whenReady().then(async () => {
  startBackend();

  try {
    await pollBackend();
    createWindow();
  } catch (err) {
    dialog.showErrorBox('Startup Error', err.message);
    app.quit();
  }
});

app.on('window-all-closed', () => {
  if (backendProcess) backendProcess.kill();
  app.quit();
});

app.on('before-quit', () => {
  if (backendProcess) backendProcess.kill();
});
