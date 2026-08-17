# Start-IT (Link Launcher)

Desktop link launcher built with **Electron + React + sql.js**.

## Overview

Start-IT lets you store, organize, and launch your favorite links from a single local desktop app. It keeps everything on the machine in a local SQLite database and supports per-link browser selection.

## Features

- Add, edit, and delete links
- Organize links into named groups
- Filter links by group
- Launch selected links or launch all visible links
- Per-link browser selection:
  - System Default
  - Google Chrome
  - Brave
  - Microsoft Edge
  - Mozilla Firefox
- Local SQLite data storage with no login or cloud service required

## Tech stack

- Electron
- React
- Vite
- sql.js (pure JavaScript SQLite engine for zero native compilation issues)

## Requirements

- Node.js **22 or newer**
- Windows 10/11 for the packaged EXE
- A desktop session for running the Electron app locally

## Run locally in development

From the project root:

```bash
npm install
npm --prefix renderer install
npm run dev
```

This starts the Vite renderer and launches the Electron desktop app.

## Build the renderer bundle

```bash
npm run build
```

## Create a Windows EXE

From the project root:

```bash
npm install
npm --prefix renderer install
npm run dist
```

This creates a portable Windows executable in the `release` folder.

## Windows troubleshooting

If Electron reports that the binary was not installed correctly:

```bash
rmdir /s /q node_modules\electron
rmdir /s /q node_modules
del package-lock.json
npm install
```

If the app still does not launch, remove the existing user data folder before retrying:

```bash
rmdir /s /q %APPDATA%\Start-IT
```

## Data storage

The app stores data in Electron user data storage under a SQLite database:

- Local app data path for the installed app
- inside that folder: `data/links.db`

## Project structure

- `electron/` — Electron main process and local DB layer
- `renderer/` — React + Vite frontend
- `release/` — generated Windows executables

