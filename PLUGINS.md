# PLUGINS.md — SSH Map Plugin API (v1)

---

## 1. Plugin Definition
A plugin is a standard Python module containing a `MANIFEST` dictionary and optional hook functions. No base classes or decorators are required.

```python
# ~/.sshmap/plugins/hello.py (or my_plugin/__init__.py)
MANIFEST = {
    "name": "hello",              # REQUIRED: Unique identity (used in config, menus, and logs)
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

*   **API Versioning:** The entry point group name carries the version (`sshmap.plugins/v1`).
*   **Folder Plugins:** Loaded as top-level modules (no relative imports allowed). Files starting with `_` are ignored.
*   **Reloading:** `Plugins → Reload` re-reads the folder immediately; import caches are bypassed.

## 3. Hooks (All Optional)
Exceptions in hooks are caught and logged; they will never crash the host application.

### `register_commands(ctx) -> [PluginCommand]`
Contributes commands to the **Command Palette** (Ctrl+K) and **Hotkeys**.
*   **`PluginCommand`:** A record with `text`, `callback` (receives `ctx`), `description`, and `keywords`.
*   **Flexibility:** Accepts `PluginCommand` objects, `(text, callback)` tuples, or `{"text": ..., "callback": ...}` dicts.
*   **Isolation:** Commands live in a dedicated palette section; they cannot shadow core commands.

### `extend_node_context_menu(menu, nodes) -> None`
Called during construction of the node context menu (Map or Sidebar).
*   **`menu`:** A live `QMenu`.
*   **`nodes`:** Lightweight node records (not scene objects).
*   **Memory:** The manager owns all `QActions` created here. The plugin must keep its own references alive or hand them to the manager's guard.

### `status_probe(node) -> (kind, detail) | None`
Runs in a worker thread during the parallel `StatusChecker` round.
*   **Return:** `(kind, detail)` where `kind` is `online`, `warn`, or `offline`.
*   **Detail:** Optional string appended to the node's tooltip.
*   **Merging:** If both the SSH probe and this hook return a value, the **worst severity** wins and details are concatenated.

### `run_on_nodes(nodes, ctx) -> None`
The "Run on selected servers" hook.
*   Receives node records and the context.
*   Execution must use `ctx.run_command()`, which runs on managed worker threads.

## 4. Discovery, States, and Conflicts
Discovery occurs at startup and on `Plugins → Reload`. Order: **Entry points first, then folder.**

*   **Conflicts:** If a folder file shares a name with an installed package, the **packaged plugin wins** (the local file is skipped).
*   **Error State:** Plugins with import errors, missing/invalid manifests, or incorrect `api_version` are moved to an "error" state. They are listed in the menu as disabled with the error reason in the tooltip.
*   **Disabled State:** Disabled plugins are still imported (to read the `MANIFEST`) but their hooks are never called.
*   **Configuration:** Settings are stored in `~/.sshmap/config.json` under the `plugins` key (e.g., `{"hello": false}`).

## 5. `PluginContext`
Plugins interact with the core exclusively through the `ctx` object.

### Read-only Properties
*   `ctx.app_version`: Current SSH Map version.
*   `ctx.api_version`: API version (1).
*   `ctx.plugin_id`: The plugin's name from `MANIFEST`.
*   `ctx.log(message)`: Logs a message prefixed with the plugin ID.

### Services
*   **`ctx.run_command(nodes, command)`**: Non-interactive SSH execution.
    *   **Credentials:** Resolved automatically by the core.
    *   **Callbacks:** `on_result(node, result)` (per node) and `on_finished(results)` (all nodes) are delivered on the **GUI thread**.
    *   **Timeout:** Bounds connection + command (default 30s).
    *   **Guard:** Destructive commands trigger a one-time "Confirm" dialog for the whole fleet. Refusal returns an empty result list without throwing an error.
*   **`ctx.status(text, timeout_ms=…)`**: Updates the status bar. The core manages widget ownership and prevents stale results from overwriting newer messages.

## 6. Isolation Rules
*   **Main Thread Discipline:** UI hooks (`register_commands`, `extend_node_context_menu`) run on the GUI thread.
    *   **Budget:** Must complete within **200 ms**. Slower hooks trigger a log warning.
    *   **No Blocking:** No IO, network, or `time.sleep` allowed.
*   **Worker Threads:** `status_probe` and `run_on_nodes` run on managed worker threads.
*   **Qt Objects:** Plugins must hand `QAction` references to the manager to prevent the PySide6 6.11 "detached menu" pitfall.
*   **Never throws:** Every hook call is wrapped — an exception is a log line and a failed call, never a crash of the host and never a broken neighbour plugin.
*   **Forbidden Actions:**
    *   Touching the GUI outside of designated hooks.
    *   Importing `ui.main_window`.
    *   Writing to `~/.sshmap/config.json` directly.
    *   Storing passwords/keys in plain text.
    *   Editing `third_party/pyte`.
*   **Process Isolation:** Plugins run in-process. A segfault in a C extension will crash the application.

## 7. Strings & Translation
Strings in `register_commands` and `extend_node_context_menu` belong to the **author**. The core does not translate them. Only core UI elements (e.g., the "Plugins" menu) use the standard i18n system.

## 8. Out of Scope for API v1
*   Event bus / Signal system.
*   Custom settings tabs/panels or docks.
*   Terminal I/O interception.
*   Map scene manipulation (drawing, layout).
*   Automatic updates / Marketplace / Sandboxing.

**API v2, when it comes, is a SECOND entry-point group — never an edit of this one.** The group name carries the version, so v2 arrives as `sshmap.plugins/v2` BESIDE `sshmap.plugins/v1`: a plugin declares the group it was written for, `ctx.api_version` reports the matching version, and every plugin written against this document keeps working unchanged.

## 9. Author Documentation
The package template, the "plugin in 20 minutes" walkthrough and the checklist of what to verify before sharing a plugin are **Section 10** below.

---

## 10. Writing a Plugin — The 20-Minute Path

### 10.1 Folder Plugin (No Packaging)
Drop a `.py` file into `~/.sshmap/plugins/`.

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
Structure for a standard Python package:
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
*   [ ] `MANIFEST` includes `name`, `version`, and `api_version: 1`.
*   [ ] Hook names are exactly as specified in §3.
*   [ ] Plugin imports cleanly via `python -c "import my_plugin"`.
*   [ ] No IO/Network/Sleep in `register_commands` or `extend_node_context_menu`.
*   [ ] `status_probe` touches no Qt objects and returns `(kind, detail)` or `None`.
*   [ ] All operations use `ctx` (no direct access to config/keyring).
*   [ ] Callbacks handle `error` results without stopping the entire run.
*   [ ] No passwords or keys are stored/logged.