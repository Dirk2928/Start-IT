const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const { spawn, spawnSync } = require('child_process');
const fs = require('fs');
const { createStore, BROWSER_DEFAULT, BROWSER_OPTIONS } = require('./store.cjs');

const builtAppPath = path.join(__dirname, '../renderer/dist/index.html');
// Drive dev mode off the npm script name (`npm run dev`) rather than the mere
// presence of a build, so a stale renderer/dist folder can't shadow the Vite
// dev server during development.
const isDev = !app.isPackaged && process.env.npm_lifecycle_event === 'dev';
let mainWindow;
let store;

const browserMap = {
  'Google Chrome': {
    command: 'chrome',
    winPaths: [
      path.join(process.env.LOCALAPPDATA || '', 'Google/Chrome/Application/chrome.exe'),
      'C:/Program Files/Google/Chrome/Application/chrome.exe',
      'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    ],
  },
  Brave: {
    command: 'brave',
    winPaths: [
      path.join(process.env.LOCALAPPDATA || '', 'BraveSoftware/Brave-Browser/Application/brave.exe'),
      'C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe',
      'C:/Program Files (x86)/BraveSoftware/Brave-Browser/Application/brave.exe',
    ],
  },
  'Microsoft Edge': {
    command: 'msedge',
    winPaths: [
      'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
      'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    ],
  },
  'Mozilla Firefox': {
    command: 'firefox',
    winPaths: [
      'C:/Program Files/Mozilla Firefox/firefox.exe',
      'C:/Program Files (x86)/Mozilla Firefox/firefox.exe',
    ],
  },
};

function detectBrowsers() {
  const detected = {};
  for (const [name, spec] of Object.entries(browserMap)) {
    if (process.platform === 'win32') {
      const found = spec.winPaths.find((candidate) => candidate && fs.existsSync(candidate));
      if (found) {
        detected[name] = found;
      }
      continue;
    }

    try {
      const check = spawnSync('which', [spec.command], { stdio: 'ignore' });
      if (check.status === 0) {
        detected[name] = spec.command;
      }
    } catch {
      // ignore detection failures
    }
  }
  return detected;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 760,
    minWidth: 980,
    minHeight: 620,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
  } else {
    mainWindow.loadFile(builtAppPath);
  }
}

function normalizeUrl(value) {
  const trimmed = String(value || '').trim();
  if (!trimmed) {
    return '';
  }

  try {
    const url = new URL(trimmed.includes('://') ? trimmed : `https://${trimmed}`);
    return url.toString();
  } catch {
    return '';
  }
}

async function launchLink(link) {
  const normalized = normalizeUrl(link.url);
  if (!normalized) {
    return { ok: false, error: `“${link.name}” has an invalid URL.` };
  }

  if (!link.browser || link.browser === BROWSER_DEFAULT) {
    await shell.openExternal(normalized);
    return { ok: true, error: '' };
  }

  const browser = browserMap[link.browser];
  if (!browser) {
    return { ok: false, error: `Unsupported browser option: ${link.browser}` };
  }

  const browserCommand =
    process.platform === 'win32'
      ? browser.winPaths.find((candidate) => candidate && fs.existsSync(candidate))
      : browser.command;

  if (!browserCommand) {
    return { ok: false, error: `${link.browser} is not installed on this computer.` };
  }

  spawn(browserCommand, [normalized], { detached: true, stdio: 'ignore' }).unref();
  return { ok: true, error: '' };
}

app.whenReady().then(async () => {
  store = await createStore();

  ipcMain.handle('groups:list', () => store.listGroups());
  ipcMain.handle('groups:create', (_event, name) => store.createGroup(name));
  ipcMain.handle('links:list', (_event, groupId) => store.listLinks(groupId));
  ipcMain.handle('links:save', (_event, payload) => {
    const normalized = normalizeUrl(payload.url);
    if (!String(payload.name || '').trim()) {
      return { ok: false, message: 'Please enter a name for this link.' };
    }
    if (!normalized) {
      return { ok: false, message: 'Please enter a valid website URL (example: example.com).' };
    }
    if (!BROWSER_OPTIONS.includes(payload.browser || BROWSER_DEFAULT)) {
      return { ok: false, message: 'Please choose a supported browser option.' };
    }

    const id = store.upsertLink({
      ...payload,
      url: normalized,
      browser: payload.browser || BROWSER_DEFAULT,
    });

    return { ok: true, id };
  });
  ipcMain.handle('links:delete', (_event, ids) => {
    store.deleteLinks(ids || []);
    return { ok: true };
  });
  ipcMain.handle('links:launch-selected', async (_event, ids) => {
    const errors = [];
    for (const id of ids || []) {
      const link = store.getLink(Number(id));
      if (!link) {
        errors.push(`- ID ${id}: Link not found`);
        continue;
      }
      const result = await launchLink(link);
      if (!result.ok) {
        errors.push(`- ${link.name}: ${result.error}`);
      }
    }
    return { ok: errors.length === 0, errors };
  });
  ipcMain.handle('links:launch-visible', async (_event, groupId) => {
    const links = store.listLinks(groupId ?? null);
    const errors = [];
    for (const link of links) {
      const result = await launchLink(link);
      if (!result.ok) {
        errors.push(`- ${link.name}: ${result.error}`);
      }
    }
    return { ok: errors.length === 0, errors };
  });
  ipcMain.handle('app:browsers', () => ({
    options: BROWSER_OPTIONS,
    detected: detectBrowsers(),
  }));

  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
