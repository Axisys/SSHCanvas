# -*- coding: utf-8 -*-
"""The INVENTORY report — the thirteen columns of the server table and the cells of ONE server.

The map's LIST mode (`ui/sidebar.py`) renders this schema and `sshcanvas-cli inventory` prints it, so the
declaration lives HERE: the Qt side imports the columns and paints them, the headless side writes the same
rows through `storage/table_text.list_table_text()`. `inventory_cell_values()` is PURE (a `ServerData` in,
strings out) and invents no text — an empty field is an EMPTY cell. The HEADER cells are the caller's: the
GUI translates the i18n keys of `INVENTORY_COLUMNS`, and the CLI prints the column IDS, which are the
machine vocabulary and never move with a language (`CLI.md` §7). One writer of a row, one list of columns.
`AGENTS.md` §4.13, §4.35; mechanism — `DOCUMENTATION.md` §37, §80.
"""

#: (field id, i18n key) — the column order of the table AND of the report, declared ONCE.
INVENTORY_COLUMNS = (
    ("alias", "sidebar.list.alias"),
    ("host", "sidebar.list.host"),
    ("port", "sidebar.list.port"),
    ("user", "sidebar.list.user"),
    ("status", "sidebar.list.status"),
    ("status_age", "sidebar.list.status_age"),
    ("os", "sidebar.list.os"),
    ("cpu", "sidebar.list.cpu"),
    ("ram", "sidebar.list.ram"),
    ("disk", "sidebar.list.disk"),
    ("info_age", "sidebar.list.info_age"),
    ("comment", "sidebar.list.comment"),
    ("tags", "sidebar.list.tags"),
)


def inventory_column_ids() -> list:
    """The column IDS, in the order of the table — the schema's machine half."""
    return [field for field, _key in INVENTORY_COLUMNS]


def inventory_cell_values(data, status_text: str = "", status_age_text: str = "",
                          info_age_text: str = "") -> list:
    """The LIST-mode cells of ONE row, one per `INVENTORY_COLUMNS` entry.

    Pure (a `ServerData` in, strings out — no Qt, no scene, no scene item). The rules:

      * an empty field is an EMPTY cell — never the string "None" (the tag caption and the card
        formatting are the only places allowed to invent text);
      * the host cell carries the IP in parentheses when the model has one and it differs
        (`host (ip)`) — the "host (IP)" column, one column instead of two near-identical ones;
      * the port and the user are shown as they are (`ssh_port` is a real field of the model with the
        default 22, so the column answers "which port does this entry use" without opening the editor);
      * the CPU cell falls back to `cpu_model`: the auto-collected data of `SystemInfoCollector` fills
        `cpu_model` while a manually typed one fills `cpu`;
      * the status cell is the caller's already TRANSLATED text (`""` = not checked yet — a status is a
        fact of the probe round, not of the project file);
      * the two age cells are the caller's `list_age_text()` texts (`""` = undated — an emulated demo
        status can never carry one), because a sentence is i18n and this function is not;
      * the tags cell is the same comma-joined list the map cards show.
    """
    def _s(value) -> str:
        return str(value or "").strip()

    host, ip = _s(getattr(data, "host", "")), _s(getattr(data, "ip", ""))
    if ip and ip != host:
        host = f"{host} ({ip})" if host else ip
    cpu = _s(getattr(data, "cpu", "")) or _s(getattr(data, "cpu_model", ""))
    tags = getattr(data, "tags", None) or []
    return [
        _s(getattr(data, "alias", "")),
        host,
        _s(getattr(data, "ssh_port", "")),
        _s(getattr(data, "user", "")),
        str(status_text or ""),
        str(status_age_text or ""),
        _s(getattr(data, "os_name", "")),
        cpu,
        _s(getattr(data, "ram", "")),
        _s(getattr(data, "disk", "")),
        str(info_age_text or ""),
        _s(getattr(data, "comment", "")),
        ", ".join(str(t).strip() for t in tags if str(t).strip()),
    ]


def inventory_rows(servers) -> list:
    """One row per server — the report's body, the header EXCLUDED (the caller owns its captions)."""
    return [inventory_cell_values(data) for data in (servers or ())]
