import sys

# `--only-terminal` imports NO map: `MainWindow` is built inside the branch that uses it, so the
# standalone launch never pays for the scene, the plugins, the dialogs or the graphics tree — the
# mode's own contract ("the standalone builds NO map … its IMPORTS are the enforcement",
# `AGENTS.md` §4.3.9) holds at the ENTRY POINT and not only inside the surface.

# v1.4.3 (ROADMAP task 4): the saved theme is applied through the ONE builder
# (ui/theme_qss.py) before the window is built — the `theme` module itself is no
# longer read here, because the palette and the QSS are both the builder's job.
try:
    from .ui import theme_qss
    from .ui.main_window_settings import apply_saved_ui_font
    from .ui.settings_dialog import (load_theme_settings, theme_from_settings,
                                     apply_motion_setting, apply_density_setting)
except ImportError:
    from ui import theme_qss
    from ui.main_window_settings import apply_saved_ui_font
    from ui.settings_dialog import (load_theme_settings, theme_from_settings,
                                    apply_motion_setting, apply_density_setting)


# ── the launch MODES (the frozen contract of `--only-terminal`: TERMINAL_STANDALONE.md §1) ────────
# ONE row per mode: the map application (the default) or the terminal surface WITHOUT it. The parse
# reads ONLY what it knows — an unknown `--flag` is REPORTED and never stops the launch, because the
# platform and Qt own the rest of the command line. NO mode opens a listening socket.
MODE_MAP = "map"
MODE_TERMINAL = "terminal"
LAUNCH_FLAGS = {"--only-terminal": MODE_TERMINAL}
USAGE = "usage: python main.py [--only-terminal]"


def parse_launch_args(argv) -> dict:
    """The ONE argv parse (PURE): `{"mode", "unknown"}` — the mode and the options nobody owns.

    A future subcommand is ONE row in `LAUNCH_FLAGS` plus its branch in `main()`; a `project` path is
    the API seam of the standalone entry point, never a command-line form of the flag (§1).
    """
    mode, unknown = MODE_MAP, []
    for token in (argv or []):
        if not isinstance(token, str):
            continue
        if token in LAUNCH_FLAGS:
            mode = LAUNCH_FLAGS[token]
        elif token.startswith("--"):
            unknown.append(token)
    return {"mode": mode, "unknown": unknown}


def main(argv=None):
    args = parse_launch_args(sys.argv[1:] if argv is None else argv)
    # ── Setup logging (before anything else) ──────────────────
    log = None  # so that if logging fails, the code below does not crash with a NameError
    try:
        from modules.logger import setup_logging, get_log_file_path
        log = setup_logging()

        log.info("=" * 60)
        # AUDIT v0.8.3 (#1): the version is centralized in version.py — the log
        # reads it from there, so drift from the release is no longer possible.
        try:
            from version import APP_NAME, APP_VERSION
        except ImportError:
            from .version import APP_NAME, APP_VERSION
        # the release feature line is no longer hardcoded here —
        # it went stale with every next release; the version comes from version.py,
        # the release description lives in CHANGELOG.md/DOCUMENTATION.md.
        log.info(f"{APP_NAME} v{APP_VERSION} starting up")
        log.info(f"Log file: {get_log_file_path()}")
        if args["unknown"]:
            # An option this parser does not own: reported, never fatal (Qt and the platform read
            # the rest of the command line themselves).
            log.warning(f"Unknown launch option(s) ignored: {', '.join(args['unknown'])} — {USAGE}")
    except Exception as e:
        print(f"[FATAL] Failed to setup logging: {e}", flush=True)

    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication(sys.argv)
        app.setStyle('Fusion')

        # v1.10rc1: the SAVED UI font goes on BEFORE the first widget exists — the theme's own rule
        # extended to the font. A widget is polished with the application font it finds at that
        # moment and Qt does not re-resolve it for a later `setFont()`, so a window built first keeps
        # the system size however correct `app.font()` is afterwards (N89).
        apply_saved_ui_font(app)

        # v1.8.1 (ROADMAP v1.8.1): the interactive TRUST SURFACE. A host key is verified and a private
        # key is unlocked on the CONNECT thread, so those questions are answered from a window here
        # (`ui/trust_surface.py` + `modules/interactive_ask.py`). Without this install the shipped TOFU
        # fallback applies — which is exactly what a headless run and the suite rely on.
        try:
            from ui.trust_surface import install as _install_trust_surface
        except ImportError:
            from .ui.trust_surface import install as _install_trust_surface
        try:
            _install_trust_surface()
        except Exception as e:
            if log is not None:
                log.warning(f"The interactive trust surface did not install: {e}")

        # The base palette AND the application QSS are built from the ACTIVE theme, and the ACTIVE
        # theme is the SAVED one, applied BEFORE the window exists, so nothing is ever constructed
        # with the wrong palette; an `auto` mode is resolved here too (the platform's colour scheme
        # decides, and `MainWindow` keeps following it live). `ui/theme_qss.apply_theme()` is the ONE
        # place that turns a Theme into the application's look; every later switch is `apply_theme()`.
        _saved_theme = load_theme_settings()
        theme_qss.apply_theme(theme_from_settings(_saved_theme), app=app,
                              refresh_windows=False)
        # v1.5rc1 (ROADMAP task 6): the "Reduce motion" flag of the same key,
        # installed BEFORE the window exists so no gesture can start un-flagged.
        apply_motion_setting(_saved_theme)
        # v1.6 (ROADMAP task 2): the card density of the same nested key — installed
        # before the first card is built, so no card is ever born in the other mode.
        apply_density_setting(_saved_theme)

        # v1.7.3 (ROADMAP v1.7.3, task 1): the cross-session relay spools ONE file under the OS
        # temp — a crash must not leave a copy of a remote file behind, so the stale spools of a
        # previous run are swept BEFORE the first window exists (a spool that outlives its run is
        # swept here). v1.13.1: the same rule for the tree an archive extraction stages. Never fatal.
        try:
            try:
                from modules.archive_extract import sweep_stages
                from modules.sftp_send import sweep_spools
            except ImportError:
                from .modules.archive_extract import sweep_stages
                from .modules.sftp_send import sweep_spools
            sweep_spools()
            sweep_stages()
        except Exception as e:
            if log is not None:
                log.warning(f"The spool sweep did not run: {e}")

        if args["mode"] == MODE_TERMINAL:
            # `--only-terminal`: the terminal surface WITHOUT the map (`TERMINAL_STANDALONE.md` §5) —
            # no scene, no plugins, no probes, no autosave, no undo and no info collection. The ONE
            # window shows the shipped container (born EMPTY) and its panel lists the servers of a
            # project file the user picks in it; closing that window ends the run (§2).
            try:
                from modules.terminal_standalone import start_standalone
            except ImportError:
                from .modules.terminal_standalone import start_standalone
            # The surface is the ONE owner of the window and lives as long as its run: the value is
            # bound to the application, because a top-level widget nobody references is collected by
            # Python and destroys its own window before the loop starts (the `win` path below keeps
            # its own reference the same way).
            app.standalone_surface = start_standalone()
            if log is not None:
                log.info("Standalone terminal shown")
        else:
            try:
                from .ui.main_window import MainWindow
            except ImportError:
                from ui.main_window import MainWindow
            win = MainWindow()
            win.show()

            # v1.4rc1 (plugin foundation, rc series): the plugin discovery — after the
            # window exists and BEFORE the event loop (ROADMAP rc1: "after MainWindow
            # creation, before app.exec()"). A broken plugin is reported in the status bar
            # and in the log; it can never stop the application (the call itself is
            # defensive as well — a plugin must not be able to break the startup).
            try:
                win.start_plugin_discovery()
            except Exception as e:
                if log is not None:
                    log.warning(f"Plugin discovery did not run: {e}")

            # v0.7.1: periodic node status checks (online/warn/offline) —
            # started once after show(): the first round in ~2 s, then driven by QTimer.
            try:
                win.start_status_checks()
            except Exception as e:
                if log is not None:
                    log.warning(f"Status checks did not start: {e}")

            if log is not None:
                log.info("MainWindow shown")
        sys.exit(app.exec())
    except Exception:
        if log is not None:
            log.exception("Fatal error during startup")
        else:
            import traceback
            traceback.print_exc()
        # a fatal error after QApplication creation would otherwise be
        # swallowed and the process exited with code 0 — now a non-zero exit code,
        # so a launcher/CI can detect a failed startup.
        sys.exit(1)


if __name__ == "__main__":
    main()
