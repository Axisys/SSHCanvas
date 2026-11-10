# PLUGINS.md — SSH Canvas Plugin API (v1)

---

## 1. Plugin Definition
A plugin is a Python module containing a `MANIFEST` dictionary and optional hook functions. No base classes or decorators are required.

```python
# ~/.sshmap/plugins/hello.py (or my_plugin/__init__.py)
MANIFEST = {
    "name": "hello",              # REQUIRED: Unique identity (config, menus, logs)
    "version": "1.0",             # REQUIRED: Author's version string
    "api_version": 1,             # REQUIRED: Must be 1
    "description": "Says hello",  # Optional: Tooltip text
}

def register_commands(ctx):
    return []
```

## 2. Shipping Methods
| Method | Entry Point (Package) | Folder (Single File) |
| :--- | :--- | :--- |
| **How** | `pip install sshmap-hello-plugin` | Drop `hello.py` into `~/.sshmap/plugins/` |
| **Declaration** | `[project.entry-points."sshmap.plugins/v1"]` | The file itself |
| **Use Case** | Distribution, dependencies, versioning | Experiments, private scripts, local copies |

* **API Versioning:** Defined via the entry point group name (`sshmap.plugins/v1`).
* **Folder Plugins:** Loaded as top-level modules; no relative imports allowed. Files prefixed with `_` are ignored.
* **Reloading:** `Plugins → Reload` bypasses import caches and re-reads the folder immediately.

## 3. Hooks (Optional)
All hooks are wrapped in exception handlers; errors are logged but will not crash the host application.

### `register_commands(ctx) -> [PluginCommand]`
Adds commands to the **Command Palette** (Ctrl+K) and **Hotkeys**.
* **`PluginCommand`:** A record containing `text`, `callback` (receives `ctx`), `description`, and `keywords`.
* **Input Types:** Accepts `PluginCommand` objects, `(text, callback)` tuples, or `{"text": ..., "callback": ...}` dicts.
* **Isolation:** Commands reside in a dedicated palette section and cannot shadow core commands.

### `extend_node_context_menu(menu, nodes) -> None`
Modifies the node context menu (Map or Sidebar).
* **`menu`:** A live `QMenu` instance.
* **`nodes`:** Lightweight node records (not scene objects).
* **Memory Management:** The manager owns all `QActions` created here. Plugins must maintain their own references or hand them to the manager's guard.

### `status_probe(node) -> (kind, detail) | None`
Executes in a worker thread during the parallel `StatusChecker` cycle.
* **Return:** `(kind, detail)` where `kind` is `online`, `warn`, or `offline`.
* **Detail:** An optional string appended to the node's tooltip.
* **Merging:** If both the SSH probe and this hook return values, the **worst severity** wins and details are concatenated.

### `run_on_nodes(nodes, ctx) -> None`
The "Run on selected servers" hook.
* Receives node records and the context.
* Must use `ctx.run_command()` to execute logic via managed worker threads.

## 4. Discovery, States, and Conflicts
Discovery occurs at startup and on `Plugins → Reload`. Order: **Entry points first, then folders.**

* **Conflicts:** Packaged plugins take precedence; folder files with duplicate names are skipped.
* **Error State:** Plugins with import errors, invalid manifests, or incorrect `api_version` enter an "error" state. They appear disabled in the menu with the error reason in the tooltip.
* **Disabled State:** Disabled plugins are imported to read the `MANIFEST` but hooks are never called.
* **Configuration:** Settings reside in `~/.sshmap/config.json` under the `plugins` key (e.g., `{"hello": false}`).

## 5. `PluginContext`
Plugins interact with the core exclusively via the `ctx` object.

### Read-only Properties
* `ctx.app_version`: Current SSH Canvas version.
* `ctx.api_version`: API version (1).
* `ctx.plugin_id`: `MANIFEST["name"]`.
* `ctx.log(message)`: Logs a message prefixed with the plugin ID.

### Services
* **`ctx.run_command(nodes, command)`**: Non-interactive SSH execution.
    * **Credentials:** Resolved automatically by the core.
    * **Callbacks:** `on_result(node, result)` (per node) and `on_finished(results)` (all nodes) execute on the **GUI thread**.
    * **Timeout:** Bounds connection + command (default 30s).
    * **Guard:** Destructive commands trigger a single "Confirm" dialog for the entire selection. Refusal returns an empty result list without error.
* **`ctx.status(text, timeout_ms=…)`**: Updates the status bar. The core manages widget ownership to prevent stale results from overwriting newer messages.

## 6. Isolation Rules
* **Main Thread Discipline:** UI hooks (`register_commands`, `extend_node_context_menu`) run on the GUI thread.
    * **Budget:** Must complete within **200 ms**. Slower hooks trigger a log warning.
    * **No Blocking:** IO, network, or `time.sleep` are strictly prohibited.
* **Worker Threads:** `status_probe` and `run_on_nodes` run on managed worker threads.
* **Qt Objects:** Plugins must hand `QAction` references to the manager to avoid PySide6 6.11 "detached menu" errors.
* **Never throws:** Every hook call is wrapped (Error Resilience); exceptions are logged but never crash the host or impact neighboring plugins.
* **Forbidden Actions:**
    * Direct GUI manipulation outside designated hooks.
    * Importing `ui.main_window`.
    * Writing directly to `~/.sshmap/config.json`.
    * Storing plain-text passwords/keys.
    * Editing `third_party/pyte`.
* **Process Isolation:** Plugins run in-process; a segfault in a C extension will crash the application.

## 7. Strings & Translation
Strings in `register_commands` and `extend_node_context_menu` are owned by the **author** and are not translated by the core. Only core UI elements use the standard i18n system.

## 8. Out of Scope for API v1
* Event bus / Signal systems.
* Custom settings tabs, panels, or docks.
* Terminal I/O interception.
* Map scene manipulation (drawing, layout).
* Automatic updates / Marketplace / Sandboxing.

**API v2** will be a **separate entry-point group** (`sshmap.plugins/v2`). This ensures v1 plugins remain functional without modification.

## 9. Author Documentation
See **Section 10** for package templates, implementation walkthroughs, and verification checklists.

---

## 10. Writing a Plugin — The 20-Minute Path

### 10.1 Folder Plugin (No Packaging)
Place a `.py` file in `~/.sshmap/plugins/`.

```python
# ~/.sshmap/plugins/k9s_launcher.py
MANIFEST = {
    "name": "k9s_launcher",
    "version": "1.0",
    "api_version": 1,
    "description": "Runs k9s on the servers you select",
}

from PySide6.QtGui import QAction
from modules.plugin_manager import PluginCommand

def register_commands(ctx):
    return [PluginCommand(text="Run k9s on the selection",
                          callback=lambda c: _launch(c),
                          description="opens k9s on every selected server",
                          keywords="k9s kubernetes tui")]

def extend_node_context_menu(menu, nodes):
    act = QAction("k9s here", menu)
    act.triggered.connect(lambda: _launch_single(nodes[0]))
    menu.addAction(act)

def status_probe(node):
    if node.port == 6443:
        return ("online", "kube-apiserver")
    return None

def run_on_nodes(nodes, ctx):
    ctx.status(f"k9s: {len(nodes)} server(s)", 3000)
    ctx.run_command(nodes, "k9s --readonly",
                    on_result=lambda node, res: ctx.log(f"{node.alias}: {res.exit_code}"))

def _launch(ctx):
    _launch_many(ctx, None)

def _launch_many(ctx, node):
    ...
```

### 10.2 Packaged Plugin
Standard Python package structure:
```text
sshmap-hello-plugin/
├── pyproject.toml
└── sshmap_hello_plugin/
    └── __init__.py
```
**`pyproject.toml` excerpt:**
```toml
[project]
name = "sshmap-hello-plugin"
version = "0.1.0"
requires-python = ">=3.10"

[project.entry-points."sshmap.plugins/v1"]
hello = "sshmap_hello_plugin"
```

### 10.3 Dogfooding Checklist
* [ ] `MANIFEST` includes `name`, `version`, and `api_version: 1`.
* [ ] Hook names match §3 exactly.
* [ ] Plugin imports cleanly via `python -c "import my_plugin"`.
* [ ] No IO/Network/Sleep in `register_commands` or `extend_node_context_menu`.
* [ ] `status_probe` avoids Qt objects and returns `(kind, detail)` or `None`.
* [ ] All operations use `ctx` (no direct config/keyring access).
* [ ] Callbacks handle `error` results without interrupting the execution loop.
* [ ] No passwords or keys are stored or logged.