# Changelog

All notable changes are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project
follows [Semantic Versioning](https://semver.org/).

## [1.0.9] - 2026-05-21

### Added

- `whole_dashboard_height_px` now accepts the literal string `'auto'`
  in addition to ints. In auto mode the plugin fetches the dashboard
  JSON server-side via Grafana's
  `GET /api/dashboards/uid/<uid>`, walks every panel's `gridPos`,
  computes `max(panel.y + panel.h) * whole_dashboard_cell_height_px
  + whole_dashboard_padding_px`, and uses that as the iframe height.
  The result is cached per-uid via `functools.lru_cache` for the
  lifetime of the worker process.

- Four new global settings supporting auto mode:

  | Setting | Default | Purpose |
  | --- | --- | --- |
  | `grafana_internal_url` | `''` (falls back to `grafana_url`) | URL the NetBox process uses to reach Grafana's API. In docker-compose this is usually the service name (`http://grafana:3000`), not the browser-facing localhost URL. |
  | `grafana_api_token` | `''` | Optional Bearer token, omitted when empty. Empty works when Grafana has anonymous viewer access. |
  | `whole_dashboard_cell_height_px` | `32` | Grafana renders one grid row at 30 px + small spacing; 32 covers both. |
  | `whole_dashboard_padding_px` | `120` | Fixed pixels added to the grid total. Covers the subnav, outer padding, and the "Powered by Grafana" footer. |
  | `whole_dashboard_fetch_timeout_s` | `2.0` | HTTP timeout for the dashboard JSON fetch. |

  On any HTTP / parse error the embed falls back to a safe 800 px
  default and logs a warning under `netbox_grafana_embed`.

### Notes

- Auto mode requires the `requests` package to be importable inside
  the NetBox process. NetBox already depends on it, so this is a
  no-op in any normal install.
- Browsers cannot auto-grow cross-origin iframes to their content
  (same-origin policy on `iframe.contentDocument.scrollHeight`), so
  the iframe height must be set in the parent document. Auto mode
  computes the right value server-side instead of asking operators
  to eyeball it.

## [1.0.8] - 2026-05-21

### Added

- Three new per-embed booleans (also valid as global defaults) that
  selectively hide pieces of the dashboard subnav inside a
  whole-dashboard embed by appending Grafana 11+ Scenes
  `_dash.hideX=true` URL params:

  | Setting             | Hides                                                  |
  | ------------------- | ------------------------------------------------------ |
  | `hide_variables`    | The variable dropdowns (typical `var-*` template selectors). |
  | `hide_time_picker`  | The time-range picker and the auto-refresh dropdown.   |
  | `hide_links`        | Custom dashboard links / external buttons.             |

  All three default `False` (subnav stays visible — no behaviour
  change for existing setups). Most useful when the embed already
  has equivalent context from NetBox — for example, on a device
  page the parent breadcrumb already says which server the user is
  looking at, so `hide_variables: True` removes the redundant
  Grafana `Server: <name>` dropdown.

## [1.0.7] - 2026-05-21

### Fixed

- `kiosk_prefix` (introduced in v1.0.6) was computed in
  `template_content.py` and passed into the block context, but the
  device-level and inventory-item-level template wrappers forgot to
  forward it to the `_whole_dashboard_iframe.html` include. The
  partial then raised `VariableDoesNotExist('Failed lookup for key
  [%s] in %r', ('kiosk_prefix', …))` and the whole embed card
  rendered as a "plugin error" panel.
  Forward `block.kiosk_prefix` explicitly in both `device_panels.html`
  and `inventory_item_panels.html` `{% include … with %}` lines.

## [1.0.6] - 2026-05-21

### Added

- New setting `kiosk_mode` (global default `''`, overridable per-embed).
  Controls the Grafana `?kiosk=` URL param for whole-dashboard mode:

  | Value           | Resulting URL fragment | Grafana effect                                              |
  | --------------- | ---------------------- | ----------------------------------------------------------- |
  | `''` *(default)*| `?kiosk`               | Hides top nav + hamburger, keeps dashboard's own subnav.    |
  | `'tv'`          | `?kiosk=tv`            | Legacy alias for the same hide-top-nav behaviour.           |
  | `None` / `False`| *(omitted)*            | Embed shows full Grafana chrome (breadcrumb, search, etc.). |
  | other string    | `?kiosk=<value>`       | Forwarded verbatim — for future Grafana kiosk values.       |

### Changed

- **Whole-dashboard mode now defaults to `?kiosk` (bare) instead of
  `?kiosk=tv`.** In Grafana 13 the two values are documented as
  equivalent but `?kiosk=tv` still rendered the top breadcrumb +
  hamburger toggle inside the embedded iframe, while `?kiosk` (bare,
  boolean true) hides them. The new default produces a much cleaner
  embed. Existing setups that prefer the v1.0.5 behaviour can opt
  back in with `'kiosk_mode': 'tv'`.

## [1.0.5] - 2026-05-21

### Added

- New per-embed option `whole_dashboard: True` renders the configured
  dashboard as a single iframe (`/d/<uid>/<slug>?kiosk=tv&var-...`)
  instead of one `d-solo` iframe per panel ID. One Grafana boot and
  one batch of Prometheus queries instead of 2 × `len(stat_panels +
  timeseries_panels)`, at the cost of giving up per-panel height
  control and the stat-tile bootstrap row — Grafana lays the panels
  out using the dashboard's own grid.

- New setting `whole_dashboard_height_px` (global default `800`,
  overridable per-embed). Controls the iframe height in whole-
  dashboard mode. Default is short enough to not dominate the device
  page; the iframe scrolls internally for taller dashboards.

In whole-dashboard mode `stat_panels` and `timeseries_panels` are
ignored. The "Full dashboard" header button and the optional `footer`
behave as before. `theme_sync` still works (renders dual light + dark
iframes).

## [1.0.4] - 2026-05-18

### Changed

- `__version__` in `netbox_grafana_embed/__init__.py` is now resolved
  at import time from the installed package's metadata via
  `importlib.metadata.version('netbox-grafana-embed')`, with a
  `'0.0.0+unknown'` fallback if the package isn't installed (e.g. when
  running directly from a source checkout). `pyproject.toml`'s
  `version` field becomes the single source of truth — future
  releases only need to bump it in one place and both `/api/status/`'s
  `installed_apps[…]` and `plugins[…]` will reflect the new version
  automatically.

## [1.0.3] - 2026-05-18

### Fixed

- `__version__` in `netbox_grafana_embed/__init__.py` was still pinned
  to `'1.0.0'` while `pyproject.toml` was bumped to `1.0.2`. NetBox
  reports both `/api/status/`'s `plugins[…]` and `installed_apps[…]`
  from the plugin module's `__version__` attribute (via
  `getattr(app_module, '__version__')` for installed_apps and
  `PluginConfig.version` for plugins, both of which our class wires to
  `__version__`). Pyproject's `version` is only used for pip METADATA
  and is not surfaced by NetBox. Bumped `__version__` to `'1.0.3'` so
  the two stay in sync.

## [1.0.2] - 2026-05-18

### Fixed

- Malformed iframe URLs: every embedded Grafana iframe was loading a
  URL missing both `?` and `panelId=N`, e.g.
  `/d-solo/<uid>/<slug>&var-device=...`. Grafana responded with a 404
  whose default `X-Frame-Options: deny` made the browser show the
  iframe as `<host> refused to connect`.
  Root cause: in `_iframe_pair.html`, `"?panelId="|add:panel_id|stringformat:"s"`
  evaluated as `stringformat(add("?panelId=", 3), "s")`. Django's `add`
  filter, asked to concatenate a string with an int, falls through both
  the `int()+int()` and `str+str` branches and returns the empty string,
  which deletes the whole `?panelId=N` prefix from the query string.
  Coerce `panel_id` to a string *before* feeding it into `add` by
  hoisting it into a `{% with pid_str=panel_id|stringformat:"s" %}`
  block.

- URL-encode `device_value` and `component_value` in the iframe `src`.
  Previously only the "Full dashboard" external link encoded them, so
  Device names or component values containing characters like space
  or `&` produced broken iframe URLs.

## [1.0.1] - 2026-05-18

### Fixed

- Render error on `dcim.device` pages when `stat_panels` is configured.
  The device template tried to compute the Bootstrap column width via
  `{{ 12|divisibleby:block.stat_panels|yesno:'4,4' }}`, which raised
  `TypeError: int() argument must be a string, a bytes-like object or
  a real number, not 'list'`. Column width is now computed in Python
  (mirroring the existing InventoryItem behaviour) and the template
  reads it as `block.stat_col_md`.

## [1.0.0] - 2026-05-13

First public release.

### Added

- Embed any number of Grafana dashboards on `dcim.device` pages via
  `device_embeds` list.
- Per-role embeds on `dcim.inventoryitem` pages via
  `inventory_item_embeds` dict.
- Dual-iframe theme sync (preload light + dark, CSS toggle) for
  zero-latency theme switching with NetBox.
- Optional custom-field gates (`show_if_custom_field_set`,
  `show_if_custom_field`) for conditional rendering.
- Variable value mapping (`device_variable_value_from`,
  `component_value_from`): `name` / `id` / `cf:<field>`.
- String-replacement post-processing on derived component values
  (`component_value_replace`).
- Per-embed override of global defaults (time range, refresh, panel
  heights).
- Tested on NetBox 4.0–4.6.
