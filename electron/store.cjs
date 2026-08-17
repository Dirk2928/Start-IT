const fs = require('fs');
const path = require('path');
const { app } = require('electron');
const initSqlJs = require('sql.js');

const BROWSER_DEFAULT = 'System Default';
const BROWSER_OPTIONS = [
  BROWSER_DEFAULT,
  'Google Chrome',
  'Brave',
  'Microsoft Edge',
  'Mozilla Firefox',
];

function getDbPath() {
  const userData = app.getPath('userData');
  const dbDir = path.join(userData, 'data');
  fs.mkdirSync(dbDir, { recursive: true });
  return path.join(dbDir, 'links.db');
}

async function getSqlInstance() {
  const wasmPath = path.join(__dirname, '..', 'node_modules', 'sql.js', 'dist', 'sql-wasm.wasm');
  return initSqlJs({
    locateFile: (file) => {
      if (file.endsWith('.wasm')) {
        return wasmPath;
      }
      return path.join(__dirname, '..', 'node_modules', 'sql.js', 'dist', file);
    },
  });
}

function readDbFile(Sql, dbPath) {
  if (!fs.existsSync(dbPath)) {
    return new Sql.Database();
  }

  const buffer = fs.readFileSync(dbPath);
  return new Sql.Database(new Uint8Array(buffer));
}

function saveDatabase(db, dbPath) {
  const data = db.export();
  if (data) {
    fs.writeFileSync(dbPath, Buffer.from(data));
  }
}

function queryAll(db, sql, params = []) {
  const statement = db.prepare(sql);
  const rows = [];

  try {
    while (statement.step()) {
      rows.push(statement.getAsObject());
    }
  } finally {
    statement.free();
  }

  return rows.map((row) => {
    const cleaned = {};
    for (const [key, value] of Object.entries(row)) {
      cleaned[key] = value === null || value === undefined ? null : value;
    }
    return cleaned;
  });
}

function queryOne(db, sql, params = []) {
  const rows = queryAll(db, sql, params);
  return rows[0] || null;
}

async function createStore() {
  const Sql = await getSqlInstance();
  const dbPath = getDbPath();
  const db = readDbFile(Sql, dbPath);

  db.run(`
    CREATE TABLE IF NOT EXISTS groups (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS links (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      url TEXT NOT NULL,
      icon TEXT,
      browser TEXT NOT NULL DEFAULT 'System Default',
      group_id INTEGER,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(group_id) REFERENCES groups(id) ON DELETE SET NULL
    );
  `);
  saveDatabase(db, dbPath);

  return {
    listGroups() {
      return queryAll(db, 'SELECT id, name FROM groups ORDER BY LOWER(name) ASC');
    },
    createGroup(name) {
      const trimmed = String(name || '').trim();
      if (!trimmed) {
        return { ok: false, message: 'Please enter a group name.' };
      }
      try {
        db.run('INSERT INTO groups(name) VALUES (?)', [trimmed]);
        saveDatabase(db, dbPath);
        const created = queryOne(db, 'SELECT id FROM groups WHERE name = ? ORDER BY id DESC LIMIT 1', [trimmed]);
        return { ok: true, id: Number(created?.id ?? 0), message: '' };
      } catch (error) {
        const message = String(error?.message || error || '');
        if (/UNIQUE|constraint/i.test(message)) {
          return { ok: false, message: 'A group with this name already exists.' };
        }
        throw error;
      }
    },
    listLinks(groupId) {
      const baseQuery = `
        SELECT l.id, l.name, l.url, l.icon, l.browser, l.group_id AS groupId, g.name AS groupName
        FROM links l
        LEFT JOIN groups g ON g.id = l.group_id
      `;
      if (groupId == null) {
        return queryAll(db, `${baseQuery} ORDER BY LOWER(l.name) ASC`);
      }
      return queryAll(db, `${baseQuery} WHERE l.group_id = ? ORDER BY LOWER(l.name) ASC`, [groupId]);
    },
    getLink(linkId) {
      const baseQuery = `
        SELECT l.id, l.name, l.url, l.icon, l.browser, l.group_id AS groupId, g.name AS groupName
        FROM links l
        LEFT JOIN groups g ON g.id = l.group_id
      `;
      return queryOne(db, `${baseQuery} WHERE l.id = ?`, [linkId]);
    },
    upsertLink(link) {
      const browser = BROWSER_OPTIONS.includes(link.browser) ? link.browser : BROWSER_DEFAULT;
      const payload = [
        String(link.name || '').trim(),
        String(link.url || '').trim(),
        String(link.icon || '').trim() || null,
        browser,
        link.groupId ?? null,
      ];

      if (link.id == null) {
        db.run('INSERT INTO links(name, url, icon, browser, group_id) VALUES (?, ?, ?, ?, ?)', payload);
        saveDatabase(db, dbPath);
        const created = queryOne(db, 'SELECT id FROM links ORDER BY id DESC LIMIT 1');
        return Number(created?.id ?? 0);
      }

      db.run('UPDATE links SET name = ?, url = ?, icon = ?, browser = ?, group_id = ? WHERE id = ?', [...payload, link.id]);
      saveDatabase(db, dbPath);
      return Number(link.id);
    },
    deleteLinks(ids) {
      if (!Array.isArray(ids) || ids.length === 0) {
        return;
      }
      const params = ids.map(Number);
      const placeholders = params.map(() => '?').join(',');
      db.run(`DELETE FROM links WHERE id IN (${placeholders})`, params);
      saveDatabase(db, dbPath);
    },
  };
}

module.exports = {
  BROWSER_DEFAULT,
  BROWSER_OPTIONS,
  createStore,
};
