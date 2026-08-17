# Link Launcher

Lightweight Windows desktop app for managing personal website links and launching them quickly.

## Features

- Add, edit, and delete links
- Link fields: name, URL, optional icon/favicon text, optional category/tag
- Launch one link or launch all saved links
- Per-link browser override:
  - System Default
  - Google Chrome
  - Brave
  - Microsoft Edge
  - Mozilla Firefox
- Local SQLite storage (offline, no login, no cloud)
- Friendly empty states and clear, large-click UI controls

## Run locally

```bash
python /home/runner/work/Start-IT/Start-IT/link_launcher.py
```

## Build a single Windows `.exe`

Install PyInstaller:

```bash
pip install pyinstaller
```

Build:

```bash
pyinstaller --noconfirm --onefile --windowed --name "LinkLauncher" /home/runner/work/Start-IT/Start-IT/link_launcher.py
```

Output executable:

- `dist/LinkLauncher.exe`

No admin rights are required to run the app. SQLite data is stored per-user under `%LOCALAPPDATA%\LinkLauncher\links.db`.
