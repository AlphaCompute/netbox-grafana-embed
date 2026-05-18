# Changelog

All notable changes are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project
follows [Semantic Versioning](https://semver.org/).

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
