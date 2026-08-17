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


@dataclass
class Link:
    id: int | None
    name: str
    url: str
    icon: str | None
    tag: str | None
    browser: str


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
        cols = {row["name"] for row in self.conn.execute("PRAGMA table_info(links)")}
        if "icon" not in cols:
            self.conn.execute("ALTER TABLE links ADD COLUMN icon TEXT")
        if "tag" not in cols:
            self.conn.execute("ALTER TABLE links ADD COLUMN tag TEXT")
        if "browser" not in cols:
            self.conn.execute(
                f"ALTER TABLE links ADD COLUMN browser TEXT NOT NULL DEFAULT '{BROWSER_DEFAULT}'"
            )
        self.conn.commit()

    def list_links(self) -> list[Link]:
        rows = self.conn.execute(
            "SELECT id, name, url, icon, tag, browser FROM links ORDER BY LOWER(name) ASC"
        ).fetchall()
        return [
            Link(
                id=row["id"],
                name=row["name"],
                url=row["url"],
                icon=row["icon"],
                tag=row["tag"],
                browser=row["browser"],
            )
            for row in rows
        ]

    def upsert_link(self, link: Link) -> None:
        if link.id is None:
            self.conn.execute(
                "INSERT INTO links(name, url, icon, tag, browser) VALUES (?, ?, ?, ?, ?)",
                (link.name, link.url, link.icon, link.tag, link.browser),
            )
        else:
            self.conn.execute(
                "UPDATE links SET name=?, url=?, icon=?, tag=?, browser=? WHERE id=?",
                (link.name, link.url, link.icon, link.tag, link.browser, link.id),
            )
        self.conn.commit()

    def delete_link(self, link_id: int) -> None:
        self.conn.execute("DELETE FROM links WHERE id = ?", (link_id,))
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
        self.root.geometry("980x620")
        self.root.minsize(920, 560)
        self.store = LinkStore(self._db_path())
        self.browsers = BrowserManager()
        self.selected_id: int | None = None
        self._build_ui()
        self.refresh_list()

    @staticmethod
    def _db_path() -> Path:
        if sys.platform == "win32":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
            return base / "LinkLauncher" / "links.db"
        return Path.home() / ".link-launcher" / "links.db"

    def _build_ui(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("vista" if sys.platform == "win32" else "clam")
        except tk.TclError:
            pass

        wrapper = ttk.Frame(self.root, padding=18)
        wrapper.pack(fill=tk.BOTH, expand=True)
        wrapper.columnconfigure(0, weight=3)
        wrapper.columnconfigure(1, weight=2)
        wrapper.rowconfigure(1, weight=1)

        title = ttk.Label(wrapper, text="Link Launcher", font=("Segoe UI", 18, "bold"))
        title.grid(row=0, column=0, sticky="w")

        launch_all = ttk.Button(wrapper, text="Launch All", command=self.on_launch_all)
        launch_all.grid(row=0, column=1, sticky="e", padx=(10, 0))

        left = ttk.Frame(wrapper, padding=(0, 12, 10, 0))
        left.grid(row=1, column=0, sticky="nsew")
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        self.empty_label = ttk.Label(
            left,
            text="No links yet.\nUse “Save Link” to add your first website.",
            justify=tk.CENTER,
            font=("Segoe UI", 11),
            foreground="#666666",
        )

        cols = ("name", "url", "tag", "browser")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse", height=16)
        self.tree.heading("name", text="Name")
        self.tree.heading("url", text="URL")
        self.tree.heading("tag", text="Category")
        self.tree.heading("browser", text="Browser")
        self.tree.column("name", width=190, stretch=True)
        self.tree.column("url", width=360, stretch=True)
        self.tree.column("tag", width=120, stretch=True)
        self.tree.column("browser", width=130, stretch=False)
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self.on_select_link)

        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=1, column=1, sticky="ns")

        buttons = ttk.Frame(left, padding=(0, 10, 0, 0))
        buttons.grid(row=2, column=0, sticky="ew")
        buttons.columnconfigure((0, 1, 2), weight=1)

        ttk.Button(buttons, text="Launch Selected", command=self.on_launch_selected).grid(
            row=0, column=0, sticky="ew", padx=(0, 8), ipadx=8, ipady=8
        )
        ttk.Button(buttons, text="Delete Selected", command=self.on_delete_link).grid(
            row=0, column=1, sticky="ew", padx=8, ipadx=8, ipady=8
        )
        ttk.Button(buttons, text="Clear Form", command=self.clear_form).grid(
            row=0, column=2, sticky="ew", padx=(8, 0), ipadx=8, ipady=8
        )

        right = ttk.LabelFrame(wrapper, text="Link Details", padding=14)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(1, weight=1)

        self.name_var = tk.StringVar()
        self.url_var = tk.StringVar()
        self.icon_var = tk.StringVar()
        self.tag_var = tk.StringVar()
        self.browser_var = tk.StringVar(value=BROWSER_DEFAULT)

        fields = [
            ("Name*", self.name_var),
            ("URL*", self.url_var),
            ("Icon/Favicon (optional)", self.icon_var),
            ("Category (optional)", self.tag_var),
        ]

        for i, (label, variable) in enumerate(fields):
            ttk.Label(right, text=label).grid(row=i, column=0, sticky="w", padx=(0, 10), pady=7)
            ttk.Entry(right, textvariable=variable).grid(row=i, column=1, sticky="ew", pady=7)

        ttk.Label(right, text="Browser").grid(row=4, column=0, sticky="w", padx=(0, 10), pady=7)
        browser_combo = ttk.Combobox(
            right, textvariable=self.browser_var, values=BROWSER_OPTIONS, state="readonly"
        )
        browser_combo.grid(row=4, column=1, sticky="ew", pady=7)

        self.detected_label = ttk.Label(
            right,
            text=self._detected_text(),
            justify=tk.LEFT,
            foreground="#444444",
            font=("Segoe UI", 9),
        )
        self.detected_label.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 12))

        ttk.Button(right, text="Save Link", command=self.on_save_link).grid(
            row=6, column=0, columnspan=2, sticky="ew", ipady=10
        )

    def _detected_text(self) -> str:
        if not self.browsers.detected:
            return "Detected browsers: none (System Default still works if Windows has a default browser)."
        names = ", ".join(sorted(self.browsers.detected))
        return f"Detected browsers: {names}"

    def refresh_list(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        links = self.store.list_links()
        for link in links:
            self.tree.insert(
                "",
                tk.END,
                iid=str(link.id),
                values=(link.name, link.url, (link.tag or ""), link.browser),
            )
        if links:
            self.empty_label.grid_forget()
            self.tree.grid()
        else:
            self.tree.grid_remove()
            self.empty_label.grid(row=1, column=0, sticky="nsew")

    def clear_form(self) -> None:
        self.selected_id = None
        self.name_var.set("")
        self.url_var.set("")
        self.icon_var.set("")
        self.tag_var.set("")
        self.browser_var.set(BROWSER_DEFAULT)
        for sel in self.tree.selection():
            self.tree.selection_remove(sel)

    def on_select_link(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        row_id = int(selection[0])
        link = next((item for item in self.store.list_links() if item.id == row_id), None)
        if not link:
            return
        self.selected_id = link.id
        self.name_var.set(link.name)
        self.url_var.set(link.url)
        self.icon_var.set(link.icon or "")
        self.tag_var.set(link.tag or "")
        self.browser_var.set(link.browser if link.browser in BROWSER_OPTIONS else BROWSER_DEFAULT)

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
            tag=self.tag_var.get().strip() or None,
            browser=self.browser_var.get().strip() or BROWSER_DEFAULT,
        )
        self.store.upsert_link(link)
        self.refresh_list()
        self.clear_form()

    def on_delete_link(self) -> None:
        if self.selected_id is None:
            messagebox.showinfo("No Link Selected", "Please select a link to delete.")
            return
        if not messagebox.askyesno("Delete Link", "Delete this link?"):
            return
        self.store.delete_link(self.selected_id)
        self.refresh_list()
        self.clear_form()

    def _launch(self, link: Link) -> tuple[bool, str]:
        normalized = self._normalize_url(link.url)
        if not normalized:
            return False, f"“{link.name}” has an invalid URL."
        return self.browsers.launch_url(normalized, link.browser)

    def on_launch_selected(self) -> None:
        if self.selected_id is None:
            messagebox.showinfo("No Link Selected", "Please select a link to open.")
            return
        link = next((item for item in self.store.list_links() if item.id == self.selected_id), None)
        if not link:
            messagebox.showerror("Link Not Found", "The selected link no longer exists.")
            self.refresh_list()
            self.clear_form()
            return
        ok, err = self._launch(link)
        if not ok:
            messagebox.showerror("Could Not Open Link", err)

    def on_launch_all(self) -> None:
        links = self.store.list_links()
        if not links:
            messagebox.showinfo("No Links Yet", "Add at least one link before using Launch All.")
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
