# SSHCanvas (Visual Node Map + SSH Terminal and SFTP manager)

A Python-based desktop application (PySide6) providing an interactive map of your IT infrastructure with direct SSH connections to nodes.

> *"Draw your infrastructure. Organize it. Connect to it."*

![The example map in SSH Canvas](docs/map-example.png)

***Note:** To view the example map, navigate to `Help → Open the example map`. It features six cards, six connection types, groups, notes, and tags using emulated statuses; every address it carries is part of the RFC 5737 documentation range `192.0.2.0/24`. The image above was generated using `python tests/_gen_docs_image.py`.*

---

## 1. Features

### Map & Canvas
*   **Infinite Canvas:** A zoomable canvas (0.1–5.0) featuring draggable/resizable server cards, sticky notes, and custom backgrounds.
*   **Connection Types:** Supports `ssh`, `vpn`, `http`, `database`, `nfs`, and `kubernetes`.
*   **Smart Connections:** Create links via `Shift`+drag or the "Connect to…" dialog. Both include autocomplete for names and addresses.
*   **Group Management:**
    *   **Folding:** Fold groups into a grid of badges (undoable). The frame shows the "worst" member status and a count (e.g., *Offline 2 · Warn 1*).
    *   **Arrangement:** Use "Arrange group" or "Arrange Map" to align members or the entire map in one undoable step.
*   **Selection & Bulk Editing:** Drag groups, connect/delete nodes, or bulk-edit tags/comments using `Ctrl`+click or rubber-band selection. Tags filter the sidebar; a card's primary tag colors its icon and is displayed on the card.
*   **Quick Launch:** Launch URLs in a browser or execute commands as the first line of an SSH session directly from a card.
*   **Impact Analysis:** `Ctrl`+click a card to highlight all transitive dependencies ("what breaks if I stop this?"). This is a non-destructive view change that does not affect the undo stack.
*   **Density Switch:** Toggle between **Comfortable** and **Compact** modes. Compact mode shortens cards and hides info blocks while maintaining consistent text eliding.
*   **Navigation Aids:** A minimap mirrors the whole map, and a legend displays all connection styles and status shapes.
*   **Export & Documentation:** Export to PNG, JPEG, PDF, SVG, or `.drawio`. It is print-friendly by default, with a one-click option to use the current theme. Includes a "Save Documentation Image" option for a fixed 1600×900 @2× poster.
*   **Shared Bookmarks:** Access a dedicated bookmarks panel (wiki, dashboards, etc.). Filter by typing and manage in place. Bookmarks are stored globally in `~/.sshmap/bookmarks.json` to keep project maps clean.

### Statuses, Facts & Diagnostics
*   **Status Monitoring:** Parallel SSH probes (TCP + banner) gather `online` / `warn` / `offline` statuses off the GUI thread. Statuses include an age and turn grey when stale.
*   **Manual Interval:** Set `status_interval_sec = 0` in settings to disable automatic probes at startup.
*   **Hardware Facts:** Gather OS, CPU, RAM, disk, and IP data with age tracking. One click gathers facts for a selection or the entire map via a bounded queue.
*   **Advanced Disk Reporting:**
    *   Reads both the root and the card's specific **data mount** (default: `/opt`).
    *   Monitors the **inode** table; alerts if a volume is >90% used (e.g., `DISK /opt: 48 gb free of 59 gb - inodes 100% used`).
    *   **Physical Disk Pinning:** Pin a card to a specific device (e.g., `SDB`) to report that device's specific capacity.
*   **Diagnostic Tool:** Right-click a red card to run a "Why is it offline?" diagnosis (DNS → TCP → SSH → ICMP) to find the first failing step.
*   **Trouble Mode:** One click dims everything except `warn`, `offline`, or `stale` nodes. A floating plaque displays all active filters (search, tag, status, lens).
*   **Unmanaged Nodes:** Mark servers as **unmanaged** to preserve their position without storing credentials or running probes. They appear with a "no ssh" mark and "not monitored" tooltip; manual pings remain notes rather than statuses.

### Terminal & SFTP
*   **Built-in Terminal:** Based on a vendored `pyte` fork. Features include:
    *   Scrollback, full keyboard/mouse support, and alternate screen support (preserves `vim`, `htop`, etc.).
    *   Wheel passthrough for TUIs, a find bar, and transcript saving.
    *   Grid-aligned glyphs for consistent layout with any monospace font.
    *   A thin blinking bar cursor (Bar, Block, or Underline in Settings) and `Ctrl`+wheel font zoom.
    *   **Wallpaper:** Set a background image (Settings → Terminal → *Wallpaper image*) with *cover*, *contain*, or *tile* modes (0–100% opacity). Only cells using the terminal's own background are transparent; full-screen TUIs paint over it.
*   **Full-Screen Mode:** Supports mouse protocols (clicks, drags) and `Shift` as a selection override/exit key. Renders VT100 line graphics (`mc`, `dialog`).
*   **Terminal Settings:**
    *   Customizable terminal types (e.g., `xterm-256color`, `tmux-256color`).
    *   **Clickable Links:** URLs wrapped in `OSC 8` sequences are clickable.
    *   **Persistent Sessions:** Right-click a tab to *Reconnect*. The screen state is preserved, and the first command is automatically re-sent.
    *   **Follow the Shell:** When enabled, a shell `PROMPT_COMMAND` hook moves the Files listing on every `cd`.
*   **Window Management:** Sessions can be tabs in separate windows, in a detachable "Terminals" dock, or in a single shared window.
    *   **Merge Windows:** Consolidates sessions into one window while preserving scrollback and history.
    *   **Split Terminal:** Create a second shell of the same node below the current tabs.
*   **Standalone Terminal Mode:** `python main.py --only-terminal` runs the terminal alone. It opens to the **Servers** list; selecting a project file lists its servers, and choosing one opens a full-featured session. Passwords are never stored in project files and are requested if unknown.
*   **Guardrails:**
    *   **Production Tags:** Prevent accidental multi-input broadcasts or pastes to sessions marked with "careful" tags.
    *   **Destructive Commands:** Automatically prompt for confirmation before executing commands like `rm -rf` or `reboot`.
*   **Command Library:** Convert historical commands into macros with version history (ring of 10) and JSON import/export. The side panel contains two lists: **Commands** (Add/Edit/Delete) and **Servers** (aliases, with Open map/Profiles). This allows starting new sessions without returning to the map. Right-clicking a server provides **Connect to SSH** and **Quick Launch** options.
*   **Command History:** A `History` tab per server is kept between sessions. Import from disk or `~/.bash_history`, filter/sort, and merge duplicates. Secrets are marked with a padlock.
*   **Scroll Mode & External Terminal:** `terminal_scroll = "pin"` keeps your reading position during output. An external `ssh` terminal is available as an alternative, supporting per-server **jump hosts** via `~/.ssh/config`.
*   **SFTP & Files Commander:**
    *   **SFTP:** Integrated over the live SSH transport. Supports drag & drop, atomic transfers, and syntax-highlighted previews.
    *   **Row Verbs:** Right-click a row to **Download** (file or folder) or **Upload** into the current directory.
    *   **Files Commander:** A two-pane directory viewer with shared address bars and shortcuts (`F3` view, `F5` copy, `F6` move, `F7` folder, `F8` delete).
    *   **Sortable Listings:** Click `Name`, `Size`, or `Modified` to sort. Folders and `..` remain grouped at the top.
    *   **Preview Limits:** Reads 1 MB by default (up to 250 MB in Settings). Larger files open with a header indicating the first megabyte.
    *   **Encodings:** Supports eight encodings (automatic, UTF-8, CP1251, etc.). The choice is per-pane and persists.
    *   **Archive Viewer:** Right-click archives (`zip`, `tar`, `jar`, etc.) to **Open Archive**, viewing contents in the other pane. Members open in the read-only preview. **Extract** unpacks the archive into the destination folder (merging files on overwrite). Encrypted archives are listed but not read or extracted.
    *   **Local Pane:** Access your local filesystem within the Files Commander using the same UI.
    *   **Elevated Pane:** Provides read-only access to a server using `sudo` via a secure password channel.
    *   **Cross-Session Transfer:** Send files between different servers via temporary relay through the local machine.
    *   **Per-Server Memory:** Both panes remember each server's last directory.
*   **Files Display Mode:** Keep the Files tree in its `Files` tab or as a right-hand panel beside the shell.
*   **Diff:** Right-click a tab to **Diff** a local file or a file from any open session. This provides a line-based, synchronized-scroll comparison with character-level changes highlighted. It is a read-only view; files are truncated if they exceed size limits and binary files are refused.

### Reports & Exports
*   **Table View:** Collapsing the map converts the sidebar into a 13-column sortable table (Alias, IP, Port, User, Status, OS, CPU, RAM, Disk, Comment, Tags).
*   **Data Exports:**
    *   **Copy List as TSV / Export List:** (CSV or TSV) in current sorted order.
    *   **Export Connections:** One row per link with endpoint details and bidirectional flags.
    *   **Export Problems:** A report of all `warn`, `offline`, or `stale` nodes, including the reason and check age.

### UI & UX
*   **Theming:** Dark, Light, and Auto themes with customizable accent colors. Every status keeps a unique shape (dot/ring/triangle) and every connection a unique line style to ensure meaning is not reliant on color alone.
*   **Motion:** Camera flights and scale-in animations can be interrupted by mouse wheel or dragging.
*   **Navigation:** Command palette (`Ctrl`+K), searchable settings, and 62 assignable hotkeys (`?` or `F1`). The map is fully navigable via keyboard.

### Projects & Plugins
*   **Project Management:** One JSON project file (`.json` / `.sshmap`) with autosave, backups, and a recent-files list.
*   **Reopen the Last Project:** Settings → General can be toggled to automatically reopen your last closed map.
*   **First Screen:** Four entry points: add a server, import a list, open an existing map, or open the example map.
*   **Add/Edit Server:** Four sections (*Identity*, *Connection*, *Hardware*, *Notes*) with clear labeling for required fields and private keys.
*   **Import Tools:** Bulk import from text files or `~/.ssh/config`. DNS resolution runs off the GUI thread.
*   **Profiles:** SSH profiles with passwords stored in the OS keyring—never in project files.
*   **Plugins:** A system for custom monitors, commands, and menu rows. A broken plugin is reported rather than freezing the application.
*   **Plugins Window:** Manage plugins, target servers, and view execution reports side-by-side.
*   **Internationalization:** Supports English, Russian, Chinese, and German, with custom JSON language support.

---

## 2. Install & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Run the GUI
python main.py

# Install the command-line tool ('sshcanvas'; 'sshmap' is an alias)
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
*   **Groups:** Membership is inferred by the card's position relative to the group rectangle.
*   **Tags/Launch:** Broken arrays are emptied; broken records are dropped.
*   **Notes:** `server_id` is optional; if absent, the note is "free."
*   **Background:** Stores the image path; move the file with the project.

---

## 4. Security & Limitations

### Credential Security
*   **Keyring Integration:** Passwords use secure OS backends (Windows Credential Manager, Linux secret-service, macOS keychain). Plaintext fallbacks are rejected.
*   **Endpoint Binding:** Passwords are bound to `user@host:port`. Changing the address or login triggers a new password prompt.
*   **External Terminal:** The external `ssh` process handles its own password entry; credentials are never passed via command-line.

### Connectivity & Guardrails
*   **Host Keys:** Missing or changed keys trigger a verification window. Fingerprints are stored atomically.
*   **Replaced Host Keys:** Accepting a new key automatically retires old algorithms for that host.
*   **2FA/Passphrases:** Entered via a secure window; closing it cancels the connection.
*   **Guardrails:** "Production tags" and "Command guards" prompt for confirmation before dangerous actions.
*   **Relayed Files:** Files between different servers are relayed via a temporary local folder and deleted immediately. Files > 100 MB are refused.
*   **Archive Viewer:** Archives are copied to a temporary folder for reading/extraction and deleted when closed. The default limit is 256 MB. Extractions are bounded for safety: they are refused if they expand > 1 GB or > 100× their size, contain > 5000 entries, or include invalid names/links.
*   **Diff Copies:** Files compared from other sessions are copied to a temporary folder, decoded, and deleted immediately. Binary files are refused.

### Behavioral Constraints
*   **Undo/Redo:** Covers map elements but **not** node statuses.
*   **Unmanaged Cards:** All monitoring, terminals, and SFTP features are disabled.
*   **File Transfers:** Folder copies are bounded (5000 entries/32 levels). Symlinks are not followed. Both panes share one SFTP channel per session.
*   **Local Pane:** Deletions are permanent (no recycle bin).
*   **Elevated Pane:** Strictly read-only for the remote user's permissions.
*   **Command History:** Stored as plain-text per server under `~/.sshmap/history/`. The padlock marks secrets but does not redact them.
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
| `version.py` | Single source of truth for versioning |
| `models/` | Data models for `ServerData` and SSH profiles |
| `graphics/` | Scene rendering: cards, arrows, notes, groups, minimap |
| `modules/` | Terminal, SFTP, pyte fork, plugins, history, undo, logging |
| `storage/` | Project persistence, example maps, autosave, `.drawio` writer |
| `services/` | Credentials, probes, diagnostics, info gathering, importers |
| `dialogs/` | All UI dialogs (Add/Edit, Connect, Profiles, Export) |
| `ui/` | Main window, sidebar, themes, palettes, icons |
| `i18n/` | Internationalization JSON files |
| `tests/` | 167 test files and the parallel runner |
| `examples/plugins/` | Example plugins and walkthroughs |
| `third_party/` | Managed `pyte` fork and patches |
| `docs/` | Documentation assets |
| `PLUGINS.md` | Plugin API contract (v1) |
| `pyproject.toml`, `requirements.txt` | Project metadata and dependencies |
| `LICENSE` | MIT License |