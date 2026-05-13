# Changelog

All notable changes are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project
follows [Semantic Versioning](https://semver.org/).

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
