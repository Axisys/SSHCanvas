# -*- coding: utf-8 -*-
"""The SHIPPED theme packs — one `<id>.json` per pack, pure DATA (never code).

`ui/theme_store.py` owns the schema, the guard and the discovery; the user folder
`~/.sshmap/themes/` shadows a file of the same id and a new file adds a pack. A pack is applied by
`ui/theme.py` (`PACKS`, `theme_for_mode(..., pack=…)`) and offered by the Appearance row of the settings
hub. This package holds no Python logic: it exists so the JSON files ship with the wheel
(`pyproject.toml`, package data). An empty package is a valid state — the registry answers `{}` and the
row offers `Default` only (`AGENTS.md` §4.6)."""
