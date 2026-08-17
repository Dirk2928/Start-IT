# Start-IT (Link Launcher)

Desktop link launcher built with **Electron + React + Tailwind + better-sqlite3**.

## Tech stack

- Electron (desktop shell)
- React (UI)
- Tailwind CSS (styling)
- better-sqlite3 (local SQLite storage)

## Features

- Add, edit, and delete links
- Optional groups for organizing links
- Filter links by group
- Launch selected links or launch all visible links
- Per-link browser choice:
  - System Default
  - Google Chrome
  - Brave
  - Microsoft Edge
  - Mozilla Firefox
- Offline local SQLite storage (no login or cloud required)

## Run locally

From repository root:

```bash
npm install
npm --prefix renderer install
npm run dev
```

## Build renderer bundle

```bash
npm run build
```

## Data storage

The app stores data in SQLite under Electron's user data folder:

- `<userData>/data/links.db`
