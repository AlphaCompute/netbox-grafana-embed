# Changelog

All notable changes are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project
follows [Semantic Versioning](https://semver.org/).

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
