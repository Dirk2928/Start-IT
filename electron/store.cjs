const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');
const { app } = require('electron');

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

function createStore() {
  const db = new Database(getDbPath());
  db.pragma('journal_mode = WAL');

  db.exec(`
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

  const listGroupsStmt = db.prepare('SELECT id, name FROM groups ORDER BY LOWER(name) ASC');
  const createGroupStmt = db.prepare('INSERT INTO groups(name) VALUES (?)');
  const listLinksBase = `
    SELECT l.id, l.name, l.url, l.icon, l.browser, l.group_id AS groupId, g.name AS groupName
    FROM links l
    LEFT JOIN groups g ON g.id = l.group_id
  `;
  const listLinksStmt = db.prepare(`${listLinksBase} ORDER BY LOWER(l.name) ASC`);
  const listLinksByGroupStmt = db.prepare(`${listLinksBase} WHERE l.group_id = ? ORDER BY LOWER(l.name) ASC`);
  const getLinkStmt = db.prepare(`${listLinksBase} WHERE l.id = ?`);
  const insertLinkStmt = db.prepare(
    'INSERT INTO links(name, url, icon, browser, group_id) VALUES (?, ?, ?, ?, ?)'
  );
  const updateLinkStmt = db.prepare(
    'UPDATE links SET name = ?, url = ?, icon = ?, browser = ?, group_id = ? WHERE id = ?'
  );

  return {
    listGroups() {
      return listGroupsStmt.all();
    },
    createGroup(name) {
      const trimmed = String(name || '').trim();
      if (!trimmed) {
        return { ok: false, message: 'Please enter a group name.' };
      }
      try {
        const result = createGroupStmt.run(trimmed);
        return { ok: true, id: Number(result.lastInsertRowid), message: '' };
      } catch (error) {
        if (error && error.code === 'SQLITE_CONSTRAINT_UNIQUE') {
          return { ok: false, message: 'A group with this name already exists.' };
        }
        throw error;
      }
    },
    listLinks(groupId) {
      if (groupId == null) {
        return listLinksStmt.all();
      }
      return listLinksByGroupStmt.all(groupId);
    },
    getLink(linkId) {
      return getLinkStmt.get(linkId) || null;
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
        const result = insertLinkStmt.run(...payload);
        return Number(result.lastInsertRowid);
      }

      updateLinkStmt.run(...payload, link.id);
      return Number(link.id);
    },
    deleteLinks(ids) {
      if (!Array.isArray(ids) || ids.length === 0) {
        return;
      }
      const placeholders = ids.map(() => '?').join(',');
      db.prepare(`DELETE FROM links WHERE id IN (${placeholders})`).run(...ids.map(Number));
    },
  };
}

module.exports = {
  BROWSER_DEFAULT,
  BROWSER_OPTIONS,
  createStore,
};
