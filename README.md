# SSHMap (Visual Node Map + SSH Terminal and SFTP manager)

A Python-based desktop application (PySide6) providing an interactive map of your IT infrastructure with direct SSH connections to nodes.

> *"Draw your infrastructure. Organize it. Connect to it."*

![The example map in SSH Map](docs/map-example.png)

***Note:** To view the example map, navigate to `Help → Open the example map`. It demonstrates six cards (one unmanaged), six connection types, groups, notes, and tags using documentation addresses (`192.0.2.0/24`) with emulated statuses; the picture above is generated from that file by `python tests/_gen_docs_image.py`.*

---

## 1. Features

### Map & Canvas
*   **Infinite Canvas:** Navigate a zoomable canvas (0.1–5.0) featuring draggable/resizable server cards, sticky notes, and custom background images.
*   **Connection Types:** Support for six types: `ssh`, `vpn`, `http`, `database`, `nfs`, and `kubernetes`.
*   **Smart Connections:** Create links via `Shift`+drag or the "Connect to…" dialog. Both methods feature autocomplete pickers for names and addresses.
*   **Group Management:**
    *   **Folding:** Fold groups into a grid of badges (undoable). The frame displays the "worst" member status and a count (e.g., *Offline 2 · Warn 1*).
    *   **Arrangement:** Use "Arrange group" or "Arrange Map" to automatically align members or the entire top-level map in a single undoable step.
*   **Selection & Bulk Editing:** Use `Ctrl`+click or rubber-band selection to drag groups, connect/delete nodes, and bulk edit tags or comments in one undo step. Tags filter the sidebar, and a card's primary tag colours its icon and is written on the card.
*   **Quick Launch:** Launch URLs in a browser or execute commands as the first line of an SSH session directly from a card.
*   **Impact Analysis:** `Ctrl`+click a card to highlight all transitive dependencies (the "what breaks if I stop this?" view). This is a non-destructive view change that does not affect the undo stack.
*   **Density Switch:** Toggle between **Comfortable** and **Compact** modes. Compact mode shortens cards and hides the information block while maintaining consistent name/address eliding.
*   **Navigation Aids:** A minimap mirrors the whole map, and a legend samples every connection type's line style and every status shape.
*   **Export & Documentation:** Export to PNG, JPEG, PDF, SVG, or `.drawio`, print-friendly by default with a one-click opt-out to the current theme. Includes a "Save Documentation Image" option for a fixed 1600×900 @2× poster.
*   **Shared Bookmarks:** Access a dedicated bookmarks panel (wiki, dashboards, etc.). Filter by typing, open with `Enter`, and manage in place. Bookmarks are stored globally in `~/.sshmap/bookmarks.json`, keeping project maps clean.

### Statuses, Facts & Diagnostics
*   **Status Monitoring:** `online` / `warn` / `offline` statuses are gathered via parallel SSH probes (TCP + banner) off the GUI thread. Statuses carry an age and turn grey when stale.
*   **Manual Interval:** Set `status_interval_sec = 0` in settings to disable automatic probes at startup.
*   **Hardware Facts:** Gather OS, CPU, RAM, disk, and IP data with age tracking. One click gathers facts for a selection or the entire map via a bounded queue.
*   **Advanced Disk Reporting:**
    *   Reads both the root and the card's specific **data mount** (default: `/opt`).
    *   Monitors the **inode** table; alerts if a volume is >90% used (e.g., `DISK /opt: 48 gb free of 59 gb - inodes 100% used`).
    *   **Physical Disk Pinning:** Pin a card to a specific device (e.g., `SDB`). The `DISK` line will report that device's specific capacity.
*   **Diagnostic Tool:** Right-click a red card to run a "Why is it offline?" diagnosis (DNS → TCP → SSH → ICMP) to identify the first failing step.
*   **Trouble Mode:** One click dims everything except `warn`, `offline`, or `stale` nodes. A floating plaque displays all active filters (search, tag, status, lens).
*   **Unmanaged Nodes:** Mark servers as **unmanaged** to preserve their position without storing credentials or running probes. These appear with a "no ssh" mark and "not monitored" tooltip; the opt-in per-card ping stays a manual note, never a status.

### Terminal & SFTP
*   **Built-in Terminal:** Based on a vendored `pyte` fork. Features include:
    *   Scrollback, full keyboard/mouse support, and alternate screen support (preserves state for `vim`, `htop`, `less`).
    *   Wheel passthrough for TUIs, a find bar, and transcript saving.
    *   Grid-aligned glyphs for consistent layout with any monospace font.
    *   A thin blinking bar cursor by default (Bar, Block, or Underline in Settings), and `Ctrl`+wheel font zoom whose size is remembered.
*   **Full-Screen Mode:** Supports mouse protocols (clicks, drags) and `Shift` as a selection override/exit key. Render VT100 line graphics (`mc`, `dialog`).
*   **Terminal Settings:**
    *   Customizable terminal types (e.g., `xterm-256color`, `tmux-256color`, `linux`, `vt100`).
    *   **Clickable Links:** URLs wrapped in `OSC 8` sequences are clickable in the terminal.
    *   **Persistent Sessions:** Right-click a tab to *Reconnect*. The screen state is preserved, and the first command is automatically re-sent.
    *   **Follow the Shell:** Off by default — a hook appended to the shell's `PROMPT_COMMAND` moves the Files listing on every `cd`; it is greyed out while two panes share one shell.
*   **Window Management:** Sessions can exist as tabs in separate windows, in a detachable "Terminals" dock, or in a single shared window.
    *   **Merge Windows:** Consolidates sessions into one window while preserving scrollback and command history.
    *   **Split Terminal:** Create a second shell of the same node below the current tabs.
*   **Guardrails:**
    *   **Production Tags:** Prevent accidental multi-input broadcasts or pastes to sessions marked with "careful" tags.
    *   **Destructive Commands:** Automatically prompt for confirmation before executing commands like `rm -rf`, `reboot`, or `mkfs`.
*   **Command Library:** Convert any historical command into a macro. Supports version history (ring of 10) and JSON import/export. The panel beside the sessions holds **two lists** — `Commands` and `Servers`, the aliases of the map's cards — and its bottom row opens the map window or the profile manager, so a session can start another one without going back to the map (a session inside the map's own dock says so instead of offering the same window twice).
*   **Command History:** A `History` tab per server, kept between sessions — import from disk or the server's `~/.bash_history`, filter and sort, copy a row back to the terminal, merge duplicates, clear the list. A command that looks like a secret is kept **and** marked with a padlock.
*   **Scroll Mode & External Terminal:** `terminal_scroll = "pin"` keeps your reading position while a build talks (the default `"live"` pulls the view back), and an external system terminal (`ssh`) works as an alternative to the built-in one.
*   **SFTP & Files Commander:**
    *   **SFTP:** Integrated over the live SSH transport (no second auth). Supports drag & drop, atomic transfers, and a read-only preview with syntax highlighting.
    *   **Files Commander:** A two-pane directory viewer with shared address bars and shortcuts (`F3` view, `F5` copy, `F6` move, `F7` folder, `F8` delete; `Enter` opens, `Insert` marks and steps down, `Backspace` goes up). The preview opens in the other pane, and an `F3`–`F8` typed into a shell still reaches the shell.
    *   **Sortable Listings:** Click `Name`, `Size`, or `Modified` to sort, click again to reverse — folders stay grouped above the files and `..` stays on top, in both panes.
    *   **Preview Limits:** The preview reads 1 MB by default (up to 250 MB in Settings → Files) and wraps long lines on request; a bigger file opens with its first megabyte named in the header instead of being refused.
    *   **Encodings:** A preview reads eight encodings (automatic, UTF-8, CP1251, CP1252, CP866, KOI8-R, Latin-1, GBK), names the one that really read the file, and re-reads an open file when you switch.
    *   **Local Pane:** Access your local filesystem within the Files Commander with the same UI and shortcuts.
    *   **Elevated Pane:** Read-only access to a server using `sudo`. Passwords are entered via a separate secure channel.
    *   **Cross-Session Transfer:** Send files between two sessions of different servers; the file is relayed through the local machine temporarily.
    *   **Per-Server Memory:** Both panes remember each server's last directory; a row dragged between panes is copied, moved with `Shift`, and a drop from another session is refused and points at *Send to*.
*   **Files Display Mode:** Keep the session's Files tree in its `Files` tab (the default) or as a right-hand panel beside the shell (standalone windows). The panel folds to a 24 px strip and is mutually exclusive with the Commander.

### Reports & Exports
*   **Table View:** Collapsing the map converts the sidebar into a 13-column sortable table (Alias, IP, Port, User, Status and its age, OS, CPU, RAM, Disk and the facts' age, Comment, Tags).
*   **Data Exports:**
    *   **Copy List as TSV / Export List:** (CSV or TSV) in your current sorted order.
    *   **Export Connections:** One row per link with endpoint details and bidirectional flags.
    *   **Export Problems:** A report of all `warn`, `offline`, or `stale` nodes including the reason and check age. A map with nothing to report says so instead of writing an empty file.

### UI & UX
*   **Theming:** Dark, Light, and Auto themes, an accent colour picked as a hue, and a "Reduce Motion" switch; the light palette is measured against every surface by contrast tests. Every status keeps its own shape (dot / ring / triangle) and every connection type its own line style, so meaning never rests on a colour alone.
*   **Motion:** Camera flights, the scale-in on add, and hover focus can always be interrupted — the wheel or a drag wins.
*   **Navigation:** Command palette (`Ctrl`+K), searchable settings hub, and 62 assignable hotkeys (`?` or `F1` lists them). The map is fully navigable via keyboard (`Tab`, `Arrows`, `Enter`).

### Projects & Plugins
*   **Project Management:** One JSON project file (`.json` / `.sshmap`) with autosave, a ring of backups, and a recent-files list; a project dropped on the window opens, and an unreadable file offers its newest autosave instead of a dead end.
*   **Reopen the Last Project:** A checkbox on Settings → General (off by default) makes the next launch continue on the map you closed; a project with no file name yet remembers nothing.
*   **First Screen:** Four doors — add your first server, import a list, open an existing map, open the example map. The minimap and the "double-click for node properties" hint stay away while the map is empty.
*   **Add/Edit Server:** Four sections (*Identity*, *Connection*, *Hardware (optional)*, *Notes*) with example placeholders on the fields you meet first, the required alias and host marked, a labelled private-key row, and a footer whose `Save` and *Save & connect* say what each one does.
*   **Import Tools:** Bulk import servers from text files or `~/.ssh/config` (supporting `Include` recursion); DNS resolves off the GUI thread and a whole import is one undo step.
*   **Profiles:** SSH profiles with passwords in the OS keyring — never in a project file.
*   **Plugins:** A plugin system for custom monitors, palette commands, and node-menu rows, with eight working examples in `examples/plugins/` (`examples/README.md` is their table). A broken plugin is reported instead of freezing the window.
*   **Plugins Window:** The plugins with their switch, the servers to run on, and what each run reported — side by side, with a text export of the visible lines. *Plugins → Run a command on servers…* sends one ad-hoc command without writing a plugin.
*   **Internationalization:** Support for English, Russian, Chinese, and German, with the ability to add custom languages via JSON files.

---

## 2. Install & Run

```bash
# Install dependencies
pip install -r requirements.txt   # PySide6, paramiko, keyring, wcwidth (pyte is vendored in third_party/pyte)

# Run the GUI
python main.py

# Install as a command-line tool
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
                "comment": "", "ssh_port": 22, "key_path": "",
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
*   **Connections:** Types: `ssh|vpn|http|database|nfs|kubernetes`. Default is `ssh`.
*   **Groups:** Membership is inferred by the card's center position relative to the group's rectangle.
*   **Tags/Launch:** Broken `tags` arrays are emptied; broken `quick_launch` records are dropped.
*   **Notes:** `server_id` is optional; if absent, the note is "free."
*   **Background:** Stores a path to the image, not the file — move it together with the project.

---

## 4. Security & Limitations

### Credential Security
*   **Keyring Integration:** Passwords are only stored in secure OS backends (Windows Credential Manager, Linux secret-service/netrc, macOS keychain). Plaintext fallbacks are rejected.
*   **External Terminal:** The external `ssh` process handles its own password entry; credentials are never passed via command-line arguments.

### Connectivity & Guardrails
*   **Host Keys:** Missing or changed host keys trigger an explicit verification window. Fingerprints are stored atomically and re-read before every addition.
*   **2FA/Passphrases:** Answered in a secure application window; closing the window cancels the connection.
*   **Guardrails:** "Production tags" and "Command guards" act as confirmation checkpoints for potentially dangerous actions (e.g., multi-line pastes or destructive commands).
*   **Relayed Files:** Files sent between different servers are relayed through the local machine's temporary folder and are deleted immediately after transfer; a file over 100 MB is refused before anything moves.

### Behavioral Constraints
*   **Undo/Redo:** Covers map elements (nodes, connections, notes, groups, edits) but **not** node statuses.
*   **Unmanaged Cards:** All monitoring, terminals, and SFTP features are disabled for unmanaged cards.
*   **File Transfers:** Folder copies are bounded at 5000 entries/32 levels. Symlinks are not followed. The two panes share **one** SFTP channel of their session, so a long transfer queues behind the other pane's work and Cancel stops that shared queue.
*   **Local Pane:** It works on this computer's disk with your own rights — a delete is permanent (no recycle bin), and `F5` never removes an original.
*   **Elevated Pane:** The elevated pane is strictly read-only for the remote user's permissions.
*   **Command History:** Stored as a plain-text file per server under `~/.sshmap/history/`, so it can carry secrets (a token passed as an argument); the padlock marks a secret-shaped line but does not redact it. The file never enters a project, an export, or the log.
*   **Endpoint-Bound Passwords:** A stored password belongs to the `user@host:port` it was saved for — change one of them and the connect dialog asks again.
*   **Plugins:** They run inside the application's process, so a plugin with a broken C extension can take it down — install plugins you trust.

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
*   **Language:** All code text must be in English. Translations for Russian, Chinese, and German are managed in `i18n/`.
*   **Translations:** New UI strings must be added to all language files simultaneously.
*   **Pyte Fork:** Do not edit `third_party/pyte/` directly. Add patches via `third_party/pyte-patches/` and record them in that folder's `MANIFEST.md`.
*   **Comments:** A comment explains what the code does today — never when it changed or what it replaced.

### PySide6 / Qt 6 Reference
| Issue | Solution |
|---|---|
| Mouse input in QGraphicsView tests | Use `PySide6.QtTest.QTest.mousePress/Move/Release/DClick` |
| Monkey-patching C++ slots | **FORBIDDEN**. Use subclass overrides only. |
| `QPropertyAnimation` on `QGraphicsItem` | Use `QVariantAnimation` instead. |
| `QGraphicsItemGroup.boundingRect()` | Requires explicit override (not recomputed from children). |
| `itemChange(ItemPositionChange)` | Called **before** position is applied; pass target rects explicitly. |
| QGraphicsProxyWidget "eats" mouse | Dragging a widget item is handled manually via `dragMode` switching. |
| `strokeToFill` / `strokedPath` | Hit zones require a custom `contains()` with curve sampling. |
| `QWidget` focusIn/focusOut | Do not exist in Qt6; use `eventFilter`. |
| `QAction` with `QMenu` | Keep `QAction` permanently; do not use `action.menu()` (destroys C++ menu). |
| `QPdfWriter` coordinates | Draw into `device.width()/height()` using `resolution()`. |

---

## 6. Repository Layout

| Path | Description |
|---|---|
| `main.py` | Entry point: logging, QApplication, plugin discovery, status checks |
| `version.py` | Single source of truth for versioning |
| `models/` | Data models for `ServerData` and SSH profiles |
| `graphics/` | Scene rendering: cards, arrows, notes, groups, minimap |
| `modules/` | Terminal, SFTP, pyte fork, plugins, history, undo, logging |
| `storage/` | Project persistence, example maps, autosave, `.drawio` writer |
| `services/` | Credentials, probes, diagnostics, info gathering, importers |
| `dialogs/` | All UI dialogs (Add/Edit, Connect, Profiles, Export) |
| `ui/` | Main window, sidebar, themes, palettes, icons |
| `i18n/` | Internationalization JSON files |
| `tests/` | 147 test files, the parallel runner and the harness — map in `tests/INDEX.md` |
| `examples/plugins/` | Example plugins and walkthroughs |
| `third_party/` | Managed `pyte` fork and patches, provenance in `third_party/pyte-patches/MANIFEST.md` |
| `docs/` | Documentation assets (e.g., rendered map images) |
| `PLUGINS.md` | Plugin API contract (v1) |
| `pyproject.toml`, `requirements.txt` | Project metadata and dependencies (`sshmap` command) |
| `LICENSE` | MIT License |
