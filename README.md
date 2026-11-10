# SSHCanvas (Visual Node Map + SSH Terminal and SFTP manager + CLI)

A PySide6 desktop application providing an interactive IT infrastructure map with direct SSH connections.

> *"Draw your infrastructure. Organize it. Connect to it."*

![The example map in SSH Canvas](docs/map-example.png)

***Note:** View the example map via `Help → Open the example map`. It features six cards, six connection types, groups, notes, and status-emulated tags. All addresses use the RFC 5737 documentation range `192.0.2.0/24`. Image generated via `python tests/_gen_docs_image.py`.*

---

## 1. Features

### Map & Canvas
*   **Infinite Canvas:** Zoomable (0.1–5.0) canvas with draggable/resizable cards, sticky notes, and custom backgrounds.
*   **Sticky Notes:** Pin notes to cards (with anchor lines). Double-click headers to **fold** notes into strips. Set note tones in Settings → Appearance (affects paper, frame, and ink).
*   **Connection Types:** Supports `ssh`, `vpn`, `http`, `database`, `nfs`, and `kubernetes`.
*   **Smart Connections:** Create links via `Shift`+drag or the "Connect to…" dialog (includes autocomplete).
*   **Group Management:**
    *   **Folding:** Fold groups into undoable badge grids. Frames display the "worst" member status and count (e.g., *Offline 2 · Warn 1*).
    *   **Arrangement:** Use "Arrange group" or "Arrange Map" for undoable alignment.
*   **Selection & Bulk Editing:** Use `Ctrl`+click or rubber-band selection to drag groups, connect/delete nodes, or bulk-edit tags/comments. Tags filter the sidebar; primary tags color card icons.
*   **Quick Launch:** Launch URLs in a browser or execute commands as the first SSH session line directly from a card.
*   **Impact Analysis:** `Ctrl`+click a card to highlight transitive dependencies. View-only; does not affect undo history.
*   **Density Switch:** Toggle **Comfortable** or **Compact** modes. Compact mode shortens cards and hides info blocks via text eliding.
*   **Navigation Aids:** Minimap for overview; legend for connection styles and status shapes.
*   **Export & Documentation:** Export to PNG, JPEG, PDF, SVG, or `.drawio`. Includes print-friendly themes and a 1600×900 @2× "Save Documentation Image" option.
*   **Shared Bookmarks:** Dedicated panel for bookmarks (wiki, dashboards, etc.). Filter via typing (`Esc` to clear). Stored globally in `~/.sshmap/bookmarks.json`.

### Statuses, Facts & Diagnostics
*   **Status Monitoring:** Asynchronous parallel SSH probes (TCP + banner) gather `online`, `warn`, or `offline` statuses. Statuses include age and turn grey when stale.
*   **Manual Interval:** Set `status_interval_sec = 0` in settings to disable automatic startup probes.
*   **Hardware Facts:** Gather OS, CPU, RAM, disk, and IP data with age tracking. Collect facts for selections or the entire map via a bounded queue.
*   **Advanced Disk Reporting:**
    *   Monitors root and specific **data mounts** (default: `/opt`).
    *   Monitors **inode** tables; alerts if volume usage exceeds 90% (e.g., `DISK /opt: 48 gb free of 59 gb - inodes 100% used`).
    *   **Physical Disk Pinning:** Pin cards to specific devices (e.g., `SDB`) to report device-specific capacity.
*   **Diagnostic Tool:** Right-click red cards to run "Why is it offline?" diagnostics (DNS → TCP → SSH → ICMP).
*   **Trouble Mode:** Dims all nodes except `warn`, `offline`, or `stale`. A floating plaque displays active filters (search, tag, status, lens).
*   **Unmanaged Nodes:** Mark servers as **unmanaged** to preserve position without storing credentials or running probes. Displays "no ssh" mark and "not monitored" tooltip.

### Terminal & SFTP
*   **Built-in Terminal:** Based on a `pyte` fork. Features:
    *   Scrollback, full keyboard/mouse, and alternate screen support (preserves `vim`, `htop`, etc.).
    *   Wheel passthrough for TUIs, a find bar, and transcript saving.
    *   Grid-aligned glyphs for monospace font consistency.
    *   Thin blinking cursor (Bar, Block, or Underline) and `Ctrl`+`wheel` font zoom.
    *   **Wallpaper:** Supports *cover*, *contain*, or *tile* modes (0–100% opacity). Transparency applies only to terminal-background cells; full-screen TUIs override it.
*   **Full-Screen Mode:** Supports mouse protocols and `Shift` as a selection/exit override. Renders VT100 line graphics (`mc`, `dialog`).
*   **Terminal Settings:**
    *   Customizable terminal types (e.g., `xterm-256color`, `tmux-256color`).
    *   **Clickable Links:** Supports `OSC 8` sequences.
    *   **Persistent Sessions:** Right-click a tab to *Reconnect*. Preserves screen state and re-sends the initial command.
    *   **Follow the Shell:** Uses a `PROMPT_COMMAND` hook to update File listings on `cd`.
*   **Window Management:** Sessions can be window tabs, a detachable "Terminals" dock, or a single shared window.
    *   **Merge Windows:** Consolidates sessions into one window, preserving scrollback.
    *   **Split Terminal:** Creates a second shell for the same node below current tabs.
*   **Standalone Terminal Mode:** `python main.py --only-terminal` runs the terminal using the **Servers** list from a selected project. Passwords are requested on-demand and never stored in project files.
*   **Guardrails:**
    *   **Production Tags:** Prevents accidental broadcasts or pastes to sessions marked with "careful" tags.
    *   **Destructive Commands:** Prompts for confirmation before executing commands like `rm -rf` or `reboot`.
*   **Command Library:** Converts historical commands to macros (10-version history, JSON export/import). Side panel manages **Commands** and **Servers**. Commands can be marked **Requires confirmation**.
*   **Command History:** Per-server `History` tab. Supports importing from disk or `~/.bash_history` with filtering and deduplication. Secrets are marked with a padlock.
*   **Scroll Mode & External Terminal:** `terminal_scroll = "pin"` maintains reading position. An external `ssh` terminal is available, supporting per-server **jump hosts** via `~/.ssh/config`.
*   **SFTP & Files Commander:**
    *   **SFTP:** Integrated over live SSH transport. Supports drag & drop, atomic transfers, and syntax-highlighted previews (JSON, XML, YAML, and plain text).
    *   **Row Verbs:** Right-click to **Download** or **Upload** files/folders.
    *   **Files Commander:** Two-pane directory viewer with shared address bars and shortcuts (`F3` view, `F5` copy, `F6` move, `F7` folder, `F8` delete).
    *   **Sortable Listings:** Sort by `Name`, `Size`, or `Modified`. Folders and `..` stay grouped at the top.
    *   **Content Search:** Searches current folder or subtree (case-optional). Displays `path:line` hits in the sibling pane. Large searches are capped by a configurable limit.
    *   **Preview Limits:** Default 1 MB preview (up to 250 MB via Settings). Large files show a header for the first megabyte.
    *   **Preview Background:** Tinted preview maintains theme brightness for readability. Includes theme and eight presets via header chip.
    *   **Find in Preview:** `Ctrl`+`F` opens a find bar with match counters and `Enter`/`Shift`+`Enter` stepping.
    *   **`Network ▸`:** Right-click IPv4 or `IPv4:PORT` to **Ping**, **Trace route**, or **Reverse lookup** in a new split terminal. Linux only; requires collected facts.
    *   **Encodings:** Supports eight encodings (e.g., UTF-8, CP1251). Encoding is per-pane and persists per session.
    *   **Archive Viewer:** Right-click archives to **Open Archive** (view contents) or **Extract** (merging on overwrite). Encrypted archives are listed but not accessible.
    *   **Local Pane:** Access local filesystem via the Files Commander UI.
    *   **Elevated Pane:** Provides read-only access via `sudo` using a secure password channel.
    *   **Cross-Session Transfer:** Relay files between servers via a temporary local folder.
    *   **Per-Server Memory:** Panes persist the last directory per server.
*   **Files Display Mode:** Toggle Files tree between a dedicated tab or a right-hand panel beside the shell.
*   **Diff:** Right-click a tab to **Diff** a local or session file: line-based, synchronized-scroll comparison with character-level highlighting. Binary files are refused.

### Reports & Exports
*   **Table View:** Collapsing the map converts the sidebar into a 13-column sortable table (Alias, IP, Port, User, Status, OS, CPU, RAM, Disk, Comment, Tags).
*   **Data Exports:**
    *   **Copy List as TSV / Export List:** (CSV or TSV) in current sorted order.
    *   **Export Connections:** One row per link with endpoint details and bidirectional flags.
    *   **Export Problems:** Report of `warn`, `offline`, or `stale` nodes, including reason and check age.
    *   **Formula-safe:** Cells starting with `=`, `+`, `-`, `@`, tabs, or carriage returns are exported with a leading apostrophe to prevent spreadsheet formula execution.

### UI & UX
*   **Theming:** Supports Dark, Light, and Auto themes with custom accents. **Theme packs** (JSON) recolor surfaces, text, cards, groups, arrows, and syntax; project settings for status, selection, and fonts are preserved. Includes **Matrix** and **Paper** packs. Uses unique shapes/line styles to ensure meaning is independent of color.
*   **Motion:** Camera flights and scale-in animations can be interrupted by mouse wheel or dragging.
*   **Navigation:** Command palette (`Ctrl`+K), searchable settings, and 63 assignable hotkeys (`?` or `F1`). Full keyboard navigation for the map.

### Projects & Plugins
*   **Project Management:** Single JSON project file (`.json` / `.sshmap`) with autosave and backups.
*   **Reopen the Last Project:** Option in Settings → General to auto-load the last closed map.
*   **First Screen:** Entry points for adding servers, importing lists, opening existing maps, or the example map.
*   **Add/Edit Server:** Four sections (*Identity*, *Connection*, *Hardware*, *Notes*) for required fields and private keys.
*   **Import Tools:** Bulk import from text files, `~/.ssh/config`, or exported `.drawio` maps. Includes a preview of added/skipped rows with reasons. DNS resolution is asynchronous.
*   **Profiles:** SSH profiles with passwords stored in the OS keyring, never in project files. Imports passwordless profiles; skips existing names to prevent overwriting.
*   **Plugins:** System for custom monitors, commands, and menu rows. Broken plugins are reported without freezing the app.
*   **Plugins Window:** Manage plugins, target servers, and execution reports side-by-side.
*   **Internationalization:** Supports English, Russian, Chinese, and German, with custom JSON language support.
*   **Headless CLI:** `sshcanvas-cli` / `sshmap-cli` provides `inventory`, `connections`, `status`, `doctor`, and `exec` verbs as text or `--json`. `hostkey verify` checks `~/.sshmap/known_hosts` against current server keys without pinning. `import` previews sources (`ssh-config`, `drawio`, `profiles`) as draft rows.

---

## 2. Install & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Run the GUI
python main.py

# Install ('sshcanvas' / 'sshmap': the GUI; 'sshcanvas-cli' / 'sshmap-cli': the headless command line)
pipx install .
```

**System Requirements:** Python 3.10+, Windows / Linux / macOS.
**Data Paths:**
- Config: `~/.sshmap/config.json`
- Plugins: `~/.sshmap/plugins/`
- Languages: `~/.sshmap/languages/`
- Logs: `~/.sshmap/logs/sshmap.log`

---

## 3. Project Format (JSON)

The project is stored in a single `.json` or `.sshmap` file:

```json
{
  "version": "0.9",
  "servers":  [{"id": "710602ee", "alias": "...", "host": "...", "user": "...",
                "x": 0.0, "y": 0.0, "cpu": "", "ram": "", "disk": "", "ip": "",
                "comment": "", "ssh_port": 22, "key_path": "", "jump_host": "",
                "os_name": "", "cpu_model": "", "tags": ["prod", "dev"],
                "info_collected_at": 1750000000.0,
                "quick_launch": [{"type": "url", "name": "Webmin", "value": "http://host:10000/"},
                                 {"type": "command", "name": "K9S", "value": "k9s"}]}],
  "connections": [{"source_id": "...", "target_id": "...", "label": "", "type": "ssh", "bidirectional": true}],
  "notes":  [{"id": "...", "text": "", "x": 0.0, "y": 0.0, "width": 240.0, "height": 160.0, "server_id": "..."}],
  "groups": [{"id": "...", "name": "", "x": 0.0, "y": 0.0, "width": 480.0, "height": 320.0}],
  "background": {"path": "/path/to/background.png", "x": 0.0, "y": 0.0, "width": 1920.0, "height": 1080.0},
  "zoom": 1.0, "center_x": 0.0, "center_y": 0.0
}
```

### Format Invariants
*   **Passwords:** Never serialized; stored only in the OS keyring.
*   **Jump host:** Optional per server; used by the external terminal only.
*   **Connections:** Types: `ssh|vpn|http|database|nfs|kubernetes`.
*   **Groups:** Membership is inferred by card position relative to the group rectangle.
*   **Tags/Launch:** Broken arrays are emptied; broken records are dropped.
*   **Notes:** `server_id` and `folded` are optional; `width`/`height` are the unfolded size.
*   **Background:** Stores the image path; move the file with the project.

---

## 4. Security & Limitations

### Credential Security
*   **Keyring Integration:** Uses secure OS backends (Windows Credential Manager, Linux secret-service, macOS keychain); plaintext fallbacks are rejected.
*   **Endpoint Binding:** Passwords are bound to `user@host:port`; address or login changes trigger a new prompt.
*   **External Terminal:** The external `ssh` process handles its own password entry; credentials are never passed via command-line.

### Connectivity & Guardrails
*   **Host Keys:** Missing or changed keys trigger a verification window. Fingerprints are stored atomically.
*   **Replaced Host Keys:** Accepting a new key automatically retires old algorithms for that host.
*   **2FA/Passphrases:** Entered via a secure window; closing it cancels the connection.
*   **Guardrails:** "Production tags" and "Command guards" prompt for confirmation before dangerous actions.
*   **Relayed Files:** Files between different servers are relayed via a temporary local folder and deleted immediately. Files > 100 MB are refused.
*   **Archive Viewer:** Copies archives to temporary folders (max 256 MB) and deletes them on close. Extraction is bounded: limits include >1 GB expanded size, >100x original size, >5000 entries, or invalid names/links.
*   **Diff Copies:** Copies session diff files to temporary folders for decoding and immediate deletion. Binary files are refused.

### Behavioral Constraints
*   **Undo/Redo:** Covers map elements but **not** node statuses.
*   **Unmanaged Cards:** All monitoring, terminals, and SFTP features are disabled.
*   **File Transfers:** Folder copies are bounded (5000 entries/32 levels). Symlinks are not followed. Both panes share one SFTP channel per session.
*   **Local Pane:** Local deletions use the OS trash (Recycle Bin, `gio trash`). If no trash backend exists, deletions are permanent and explicitly confirmed.
*   **Elevated Pane:** Strictly read-only for the remote user's permissions.
*   **Command History:** Stored as plain-text per server in `~/.sshmap/history/`. Padlocks mark secrets but do not redact them.
*   **Profile Store:** Profiles live in `~/.sshmap_profiles.json`. Broken files are reported rather than overwritten.
*   **Plugins:** Run inside the application process; install only trusted plugins.

---

## 5. Development

Everything is plain Python with no build step.

```bash
python main.py                         # Run the GUI
python tests/run_all.py                # Run full test suite
python tests/run_all.py --fast         # Daily profile (skips slow/network tests)
python tests/run_all.py --tag network  # Run network-specific tests
python tests/run_all.py --failed-only  # Re-run previous failures
```

### Contributing Rules
*   **Language:** All code must be in English. Translations are in `i18n/`.
*   **Translations:** New UI strings must be added to all language files simultaneously.
*   **Pyte Fork:** Do not edit `third_party/pyte/` directly. Add patches via `third_party/pyte-patches/`.
*   **Comments:** Explain what the code does today—not what it used to be.

### PySide6 / Qt 6 Reference
| Issue | Solution |
|---|---|
| Mouse input in QGraphicsView tests | Use `PySide6.QtTest.QTest.mousePress/Move/Release/DClick` |
| Monkey-patching C++ slots | **FORBIDDEN**. Use subclass overrides only. |
| `QPropertyAnimation` on `QGraphicsItem` | Use `QVariantAnimation` instead. |
| `QGraphicsItemGroup.boundingRect()` | Requires explicit override. |
| `itemChange(ItemPositionChange)` | Called **before** position is applied; pass target rects explicitly. |
| QGraphicsProxyWidget "eats" mouse | Handle via manual `dragMode` switching. |
| `strokeToFill` / `strokedPath` | Hit zones require a custom `contains()` with curve sampling. |
| `QWidget` focusIn/focusOut | Use `eventFilter` (does not exist in Qt6). |
| `QAction` with `QMenu` | Keep `QAction` permanently; do not use `action.menu()`. |
| `QPdfWriter` coordinates | Draw into `device.width()/height()` using `resolution()`. |

---

## 6. Repository Layout

| Path | Description |
|---|---|
| `main.py` | Entry point: logging, QApplication, and plugin discovery |
| `cli/` | The headless command line: argv, verbs, exit codes and the `--json` envelope (no Qt) |
| `version.py` | Single source of truth for versioning |
| `models/` | Data models for `ServerData` and SSH profiles |
| `graphics/` | Scene rendering: cards, arrows, notes, groups, minimap |
| `modules/` | Terminal, SFTP, pyte fork, plugins, history, undo, logging |
| `storage/` | Project persistence, example maps, autosave, `.drawio` writer |
| `services/` | Credentials, probes, diagnostics, info gathering, importers |
| `dialogs/` | All UI dialogs (Add/Edit, Connect, Profiles, Export) |
| `ui/` | Main window, sidebar, themes, palettes, icons |
| `i18n/` | Internationalization JSON files |
| `themes/` | Theme packs: one JSON file per pack |
| `tests/` | 200 test files and the parallel runner |
| `examples/plugins/` | Example plugins and walkthroughs |
| `third_party/` | Managed `pyte` fork and patches |
| `docs/` | Documentation assets |
| `PLUGINS.md` | Plugin API contract (v1) |
| `pyproject.toml`, `requirements.txt`, `LICENSE` | Project metadata, dependencies and the MIT licence |