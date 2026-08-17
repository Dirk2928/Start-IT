import os
import shutil
import sqlite3
import subprocess
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk
from urllib.parse import urlparse
import webbrowser


BROWSER_DEFAULT = "System Default"
BROWSER_CHROME = "Google Chrome"
BROWSER_BRAVE = "Brave"
BROWSER_EDGE = "Microsoft Edge"
BROWSER_FIREFOX = "Mozilla Firefox"
BROWSER_OPTIONS = [
    BROWSER_DEFAULT,
    BROWSER_CHROME,
    BROWSER_BRAVE,
    BROWSER_EDGE,
    BROWSER_FIREFOX,
]

NO_GROUP_LABEL = "No Group"
ALL_GROUPS_LABEL = "All Groups"


@dataclass
class Link:
    id: int | None
    name: str
    url: str
    icon: str | None
    browser: str
    group_id: int | None
    group_name: str | None


class LinkStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                icon TEXT,
                tag TEXT,
                browser TEXT NOT NULL DEFAULT 'System Default',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
            """
        )

        cols = {row["name"] for row in self.conn.execute("PRAGMA table_info(links)")}
        if "icon" not in cols:
            self.conn.execute("ALTER TABLE links ADD COLUMN icon TEXT")
        if "tag" not in cols:
            self.conn.execute("ALTER TABLE links ADD COLUMN tag TEXT")
        if "browser" not in cols:
            self.conn.execute(
                f"ALTER TABLE links ADD COLUMN browser TEXT NOT NULL DEFAULT '{BROWSER_DEFAULT}'"
            )
        if "group_id" not in cols:
            self.conn.execute("ALTER TABLE links ADD COLUMN group_id INTEGER")

        self._backfill_groups_from_tag()
        self.conn.commit()

    def _backfill_groups_from_tag(self) -> None:
        rows = self.conn.execute(
            "SELECT DISTINCT TRIM(tag) AS tag_name FROM links WHERE tag IS NOT NULL AND TRIM(tag) <> ''"
        ).fetchall()
        for row in rows:
            tag_name = row["tag_name"]
            self.conn.execute("INSERT OR IGNORE INTO groups(name) VALUES (?)", (tag_name,))
            group_row = self.conn.execute("SELECT id FROM groups WHERE name = ?", (tag_name,)).fetchone()
            if not group_row:
                continue
            self.conn.execute(
                "UPDATE links SET group_id = ? WHERE (group_id IS NULL OR group_id = '') AND TRIM(COALESCE(tag, '')) = ?",
                (group_row["id"], tag_name),
            )

    def list_groups(self) -> list[tuple[int, str]]:
        rows = self.conn.execute("SELECT id, name FROM groups ORDER BY LOWER(name) ASC").fetchall()
        return [(row["id"], row["name"]) for row in rows]

    def create_group(self, name: str) -> tuple[bool, str, int | None]:
        value = name.strip()
        if not value:
            return False, "Please enter a group name.", None
        try:
            cur = self.conn.execute("INSERT INTO groups(name) VALUES (?)", (value,))
            self.conn.commit()
            return True, "", int(cur.lastrowid)
        except sqlite3.IntegrityError:
            return False, "A group with this name already exists.", None

    def list_links(self, group_id: int | None = None) -> list[Link]:
        if group_id is None:
            rows = self.conn.execute(
                """
                SELECT l.id, l.name, l.url, l.icon, l.browser, l.group_id, g.name AS group_name
                FROM links l
                LEFT JOIN groups g ON g.id = l.group_id
                ORDER BY LOWER(l.name) ASC
                """
            ).fetchall()
        else:
            rows = self.conn.execute(
                """
                SELECT l.id, l.name, l.url, l.icon, l.browser, l.group_id, g.name AS group_name
                FROM links l
                LEFT JOIN groups g ON g.id = l.group_id
                WHERE l.group_id = ?
                ORDER BY LOWER(l.name) ASC
                """,
                (group_id,),
            ).fetchall()
        return [
            Link(
                id=row["id"],
                name=row["name"],
                url=row["url"],
                icon=row["icon"],
                browser=row["browser"],
                group_id=row["group_id"],
                group_name=row["group_name"],
            )
            for row in rows
        ]

    def get_link(self, link_id: int) -> Link | None:
        row = self.conn.execute(
            """
            SELECT l.id, l.name, l.url, l.icon, l.browser, l.group_id, g.name AS group_name
            FROM links l
            LEFT JOIN groups g ON g.id = l.group_id
            WHERE l.id = ?
            """,
            (link_id,),
        ).fetchone()
        if not row:
            return None
        return Link(
            id=row["id"],
            name=row["name"],
            url=row["url"],
            icon=row["icon"],
            browser=row["browser"],
            group_id=row["group_id"],
            group_name=row["group_name"],
        )

    def upsert_link(self, link: Link) -> None:
        if link.id is None:
            self.conn.execute(
                "INSERT INTO links(name, url, icon, browser, group_id) VALUES (?, ?, ?, ?, ?)",
                (link.name, link.url, link.icon, link.browser, link.group_id),
            )
        else:
            self.conn.execute(
                "UPDATE links SET name=?, url=?, icon=?, browser=?, group_id=? WHERE id=?",
                (link.name, link.url, link.icon, link.browser, link.group_id, link.id),
            )
        self.conn.commit()

    def delete_links(self, link_ids: list[int]) -> None:
        if not link_ids:
            return
        placeholders = ",".join(["?"] * len(link_ids))
        self.conn.execute(f"DELETE FROM links WHERE id IN ({placeholders})", link_ids)
        self.conn.commit()


class BrowserManager:
    def __init__(self):
        self.detected = self._detect_browsers()

    @staticmethod
    def _possible_windows_paths() -> dict[str, list[str]]:
        local = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        program_files_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        return {
            BROWSER_CHROME: [
                os.path.join(local, r"Google\Chrome\Application\chrome.exe"),
                os.path.join(program_files, r"Google\Chrome\Application\chrome.exe"),
                os.path.join(program_files_x86, r"Google\Chrome\Application\chrome.exe"),
            ],
            BROWSER_BRAVE: [
                os.path.join(local, r"BraveSoftware\Brave-Browser\Application\brave.exe"),
                os.path.join(program_files, r"BraveSoftware\Brave-Browser\Application\brave.exe"),
                os.path.join(program_files_x86, r"BraveSoftware\Brave-Browser\Application\brave.exe"),
            ],
            BROWSER_EDGE: [
                os.path.join(program_files, r"Microsoft\Edge\Application\msedge.exe"),
                os.path.join(program_files_x86, r"Microsoft\Edge\Application\msedge.exe"),
            ],
            BROWSER_FIREFOX: [
                os.path.join(program_files, r"Mozilla Firefox\firefox.exe"),
                os.path.join(program_files_x86, r"Mozilla Firefox\firefox.exe"),
            ],
        }

    def _detect_browsers(self) -> dict[str, str]:
        found: dict[str, str] = {}
        command_names = {
            BROWSER_CHROME: "chrome",
            BROWSER_BRAVE: "brave",
            BROWSER_EDGE: "msedge",
            BROWSER_FIREFOX: "firefox",
        }
        for label, cmd in command_names.items():
            cmd_path = shutil.which(cmd)
            if cmd_path:
                found[label] = cmd_path

        for label, candidates in self._possible_windows_paths().items():
            if label in found:
                continue
            for candidate in candidates:
                if candidate and os.path.exists(candidate):
                    found[label] = candidate
                    break
        return found

    def launch_url(self, url: str, browser: str) -> tuple[bool, str]:
        try:
            if browser == BROWSER_DEFAULT:
                webbrowser.open_new_tab(url)
                return True, ""
            path = self.detected.get(browser)
            if not path:
                return False, f"{browser} is not installed on this computer."
            subprocess.Popen([path, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, ""
        except Exception as exc:
            return False, f"Could not open this link: {exc}"


class LinkLauncherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Link Launcher")
        self.root.geometry("1080x680")
        self.root.minsize(980, 620)
        self.store = LinkStore(self._db_path())
        self.browsers = BrowserManager()
        self.selected_id: int | None = None
        self.current_filter_group_id: int | None = None
        self.group_value_to_id: dict[str, int | None] = {}
        self.filter_group_value_to_id: dict[str, int | None] = {}
        self._build_ui()
        self.refresh_group_controls()
        self.refresh_list()

    @staticmethod
    def _db_path() -> Path:
        if sys.platform == "win32":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
            return base / "LinkLauncher" / "links.db"
        return Path.home() / ".link-launcher" / "links.db"

    def _build_ui(self) -> None:
        self.root.configure(bg="#eef2ff")
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("App.TFrame", background="#eef2ff")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Header.TLabel", background="#eef2ff", font=("Segoe UI", 22, "bold"), foreground="#1f2a44")
        style.configure("SubHeader.TLabel", background="#eef2ff", font=("Segoe UI", 10), foreground="#5b647a")
        style.configure("Status.TLabel", background="#ffffff", foreground="#1f7a43", font=("Segoe UI", 9, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 10))
        style.configure("Treeview", rowheight=30, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        wrapper = ttk.Frame(self.root, padding=20, style="App.TFrame")
        wrapper.pack(fill=tk.BOTH, expand=True)
        wrapper.columnconfigure(0, weight=3)
        wrapper.columnconfigure(1, weight=2)
        wrapper.rowconfigure(2, weight=1)

        ttk.Label(wrapper, text="Link Launcher", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            wrapper,
            text="Create groups, save links, and launch multiple links quickly.",
            style="SubHeader.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(0, 8))

        launch_all = ttk.Button(wrapper, text="Launch Visible", style="Accent.TButton", command=self.on_launch_all)
        launch_all.grid(row=0, column=1, sticky="e", padx=(10, 0), rowspan=2)

        left = ttk.Frame(wrapper, padding=(0, 8, 12, 0), style="App.TFrame")
        left.grid(row=2, column=0, sticky="nsew")
        left.rowconfigure(2, weight=1)
        left.columnconfigure(0, weight=1)

        filter_row = ttk.Frame(left, style="App.TFrame")
        filter_row.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        filter_row.columnconfigure(1, weight=1)
        ttk.Label(filter_row, text="Filter Group").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.filter_group_var = tk.StringVar(value=ALL_GROUPS_LABEL)
        self.filter_combo = ttk.Combobox(filter_row, textvariable=self.filter_group_var, state="readonly")
        self.filter_combo.grid(row=0, column=1, sticky="ew")
        self.filter_combo.bind("<<ComboboxSelected>>", self.on_filter_group_change)

        self.empty_label = ttk.Label(
            left,
            text="No links yet.\nAdd a link from the panel on the right.",
            justify=tk.CENTER,
            font=("Segoe UI", 11),
            foreground="#667085",
            background="#eef2ff",
        )

        cols = ("name", "url", "group", "browser")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="extended", height=16)
        self.tree.heading("name", text="Name")
        self.tree.heading("url", text="URL")
        self.tree.heading("group", text="Group")
        self.tree.heading("browser", text="Browser")
        self.tree.column("name", width=200, stretch=True)
        self.tree.column("url", width=360, stretch=True)
        self.tree.column("group", width=130, stretch=True)
        self.tree.column("browser", width=140, stretch=False)
        self.tree.grid(row=2, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select_link)

        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=2, column=1, sticky="ns")

        buttons = ttk.Frame(left, padding=(0, 10, 0, 0), style="App.TFrame")
        buttons.grid(row=3, column=0, sticky="ew")
        buttons.columnconfigure((0, 1, 2), weight=1)

        ttk.Button(buttons, text="Launch Selected", command=self.on_launch_selected).grid(
            row=0, column=0, sticky="ew", padx=(0, 8), ipady=8
        )
        ttk.Button(buttons, text="Delete Selected", command=self.on_delete_links).grid(
            row=0, column=1, sticky="ew", padx=8, ipady=8
        )
        ttk.Button(buttons, text="Clear Form", command=self.clear_form).grid(
            row=0, column=2, sticky="ew", padx=(8, 0), ipady=8
        )

        right = ttk.Frame(wrapper, padding=16, style="Card.TFrame")
        right.grid(row=2, column=1, sticky="nsew")
        right.columnconfigure(1, weight=1)

        ttk.Label(right, text="Link Details", font=("Segoe UI", 14, "bold"), background="#ffffff").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )

        self.name_var = tk.StringVar()
        self.url_var = tk.StringVar()
        self.icon_var = tk.StringVar()
        self.group_var = tk.StringVar(value=NO_GROUP_LABEL)
        self.browser_var = tk.StringVar(value=BROWSER_DEFAULT)
        self.status_var = tk.StringVar(value="")
        self.new_group_var = tk.StringVar()

        fields = [
            ("Name*", self.name_var),
            ("URL*", self.url_var),
            ("Icon/Favicon (optional)", self.icon_var),
        ]

        for i, (label, variable) in enumerate(fields, start=1):
            ttk.Label(right, text=label, background="#ffffff").grid(
                row=i, column=0, sticky="w", padx=(0, 10), pady=6
            )
            ttk.Entry(right, textvariable=variable).grid(row=i, column=1, sticky="ew", pady=6)

        ttk.Label(right, text="Group", background="#ffffff").grid(row=4, column=0, sticky="w", padx=(0, 10), pady=6)
        self.group_combo = ttk.Combobox(right, textvariable=self.group_var, state="readonly")
        self.group_combo.grid(row=4, column=1, sticky="ew", pady=6)

        group_actions = ttk.Frame(right, style="Card.TFrame")
        group_actions.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        group_actions.columnconfigure(0, weight=1)
        ttk.Entry(group_actions, textvariable=self.new_group_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(group_actions, text="Create Group", command=self.on_create_group).grid(row=0, column=1, sticky="ew")

        ttk.Label(right, text="Browser", background="#ffffff").grid(row=6, column=0, sticky="w", padx=(0, 10), pady=6)
        browser_combo = ttk.Combobox(
            right, textvariable=self.browser_var, values=BROWSER_OPTIONS, state="readonly"
        )
        browser_combo.grid(row=6, column=1, sticky="ew", pady=6)

        self.detected_label = ttk.Label(
            right,
            text=self._detected_text(),
            justify=tk.LEFT,
            foreground="#4a5571",
            font=("Segoe UI", 9),
            background="#ffffff",
        )
        self.detected_label.grid(row=7, column=0, columnspan=2, sticky="w", pady=(6, 10))

        ttk.Button(right, text="Save Link", style="Accent.TButton", command=self.on_save_link).grid(
            row=8, column=0, columnspan=2, sticky="ew", ipady=8
        )

        ttk.Label(right, textvariable=self.status_var, style="Status.TLabel").grid(
            row=9, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )

    def _detected_text(self) -> str:
        if not self.browsers.detected:
            return "Detected browsers: none (System Default still works if Windows has a default browser)."
        names = ", ".join(sorted(self.browsers.detected))
        return f"Detected browsers: {names}"

    def refresh_group_controls(self) -> None:
        groups = self.store.list_groups()

        link_values = [NO_GROUP_LABEL]
        self.group_value_to_id = {NO_GROUP_LABEL: None}
        for gid, name in groups:
            link_values.append(name)
            self.group_value_to_id[name] = gid
        self.group_combo.configure(values=link_values)
        if self.group_var.get() not in self.group_value_to_id:
            self.group_var.set(NO_GROUP_LABEL)

        filter_values = [ALL_GROUPS_LABEL]
        self.filter_group_value_to_id = {ALL_GROUPS_LABEL: None}
        for gid, name in groups:
            filter_values.append(name)
            self.filter_group_value_to_id[name] = gid
        self.filter_combo.configure(values=filter_values)
        if self.filter_group_var.get() not in self.filter_group_value_to_id:
            self.filter_group_var.set(ALL_GROUPS_LABEL)

        self.current_filter_group_id = self.filter_group_value_to_id.get(self.filter_group_var.get())

    def refresh_list(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        links = self.store.list_links(self.current_filter_group_id)
        for link in links:
            self.tree.insert(
                "",
                tk.END,
                iid=str(link.id),
                values=(link.name, link.url, (link.group_name or ""), link.browser),
            )

        if links:
            self.empty_label.grid_forget()
            self.tree.grid()
        else:
            self.tree.grid_remove()
            self.empty_label.grid(row=2, column=0, sticky="nsew")

    def clear_form(self) -> None:
        self.selected_id = None
        self.name_var.set("")
        self.url_var.set("")
        self.icon_var.set("")
        self.group_var.set(NO_GROUP_LABEL)
        self.browser_var.set(BROWSER_DEFAULT)
        for sel in self.tree.selection():
            self.tree.selection_remove(sel)

    def on_filter_group_change(self, _event=None) -> None:
        self.current_filter_group_id = self.filter_group_value_to_id.get(self.filter_group_var.get())
        self.refresh_list()

    def on_create_group(self) -> None:
        ok, msg, _group_id = self.store.create_group(self.new_group_var.get())
        if not ok:
            messagebox.showwarning("Cannot Create Group", msg)
            return
        new_name = self.new_group_var.get().strip()
        self.new_group_var.set("")
        self.refresh_group_controls()
        self.group_var.set(new_name)
        self.status_var.set("Group created successfully.")

    def on_select_link(self, _event=None) -> None:
        selection = self.tree.selection()
        if len(selection) != 1:
            self.selected_id = None
            return

        row_id = int(selection[0])
        link = self.store.get_link(row_id)
        if not link:
            return

        self.selected_id = link.id
        self.name_var.set(link.name)
        self.url_var.set(link.url)
        self.icon_var.set(link.icon or "")
        self.browser_var.set(link.browser if link.browser in BROWSER_OPTIONS else BROWSER_DEFAULT)

        group_name = link.group_name if link.group_name in self.group_value_to_id else NO_GROUP_LABEL
        self.group_var.set(group_name)

    @staticmethod
    def _normalize_url(raw_url: str) -> str:
        value = raw_url.strip()
        if not value:
            return ""
        parsed = urlparse(value if "://" in value else f"https://{value}")
        if not parsed.scheme or not parsed.netloc:
            return ""
        return parsed.geturl()

    def _validate_link_input(self) -> tuple[bool, str]:
        if not self.name_var.get().strip():
            return False, "Please enter a name for this link."
        normalized = self._normalize_url(self.url_var.get())
        if not normalized:
            return False, "Please enter a valid website URL (example: example.com)."
        self.url_var.set(normalized)
        if self.browser_var.get() not in BROWSER_OPTIONS:
            return False, "Please choose a supported browser option."
        if self.group_var.get() not in self.group_value_to_id:
            return False, "Please choose a valid group option."
        return True, ""

    def on_save_link(self) -> None:
        ok, msg = self._validate_link_input()
        if not ok:
            messagebox.showwarning("Cannot Save Link", msg)
            return

        link = Link(
            id=self.selected_id,
            name=self.name_var.get().strip(),
            url=self.url_var.get().strip(),
            icon=self.icon_var.get().strip() or None,
            browser=self.browser_var.get().strip() or BROWSER_DEFAULT,
            group_id=self.group_value_to_id.get(self.group_var.get()),
            group_name=self.group_var.get() if self.group_var.get() != NO_GROUP_LABEL else None,
        )

        self.store.upsert_link(link)
        self.refresh_list()
        self.clear_form()
        self.status_var.set("Link saved and form cleared.")

    def _launch(self, link: Link) -> tuple[bool, str]:
        normalized = self._normalize_url(link.url)
        if not normalized:
            return False, f"“{link.name}” has an invalid URL."
        return self.browsers.launch_url(normalized, link.browser)

    def on_launch_selected(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("No Links Selected", "Please select one or more links to open.")
            return

        errors: list[str] = []
        for selected in selection:
            link = self.store.get_link(int(selected))
            if not link:
                errors.append(f"- ID {selected}: Link not found")
                continue
            ok, err = self._launch(link)
            if not ok:
                errors.append(f"- {link.name}: {err}")

        if errors:
            messagebox.showwarning(
                "Some Links Could Not Be Opened",
                "Some links were skipped:\n\n" + "\n".join(errors[:8]),
            )

    def on_delete_links(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("No Links Selected", "Please select one or more links to delete.")
            return

        if not messagebox.askyesno("Delete Links", f"Delete {len(selection)} selected link(s)?"):
            return

        self.store.delete_links([int(item) for item in selection])
        self.refresh_list()
        self.clear_form()
        self.status_var.set("Selected link(s) deleted.")

    def on_launch_all(self) -> None:
        links = self.store.list_links(self.current_filter_group_id)
        if not links:
            messagebox.showinfo("No Links Yet", "Add at least one link before using Launch Visible.")
            return

        errors: list[str] = []
        for link in links:
            ok, err = self._launch(link)
            if not ok:
                errors.append(f"- {link.name}: {err}")

        if errors:
            messagebox.showwarning(
                "Some Links Could Not Be Opened",
                "Some links were skipped:\n\n" + "\n".join(errors[:8]),
            )


def main() -> None:
    root = tk.Tk()
    app = LinkLauncherApp(root)
    _ = app
    root.mainloop()


if __name__ == "__main__":
    main()
