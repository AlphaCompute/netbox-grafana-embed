# netbox-grafana-embed

NetBox plugin that embeds Grafana panels on **Device** and **InventoryItem**
detail pages. Theme-synced (NetBox dark ↔ Grafana dark), instant-switch via
dual-iframe technique, fully configurable, vendor-neutral.

[![PyPI](https://img.shields.io/pypi/v/netbox-grafana-embed.svg)](https://pypi.org/project/netbox-grafana-embed/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![NetBox 4.x](https://img.shields.io/badge/NetBox-4.x-success)](https://github.com/netbox-community/netbox)

---

## What it does

Drop one block of YAML/Python into `PLUGINS_CONFIG` and every Device page in
NetBox gains a live Grafana card — same time range across all panels, dark
or light follows NetBox theme, click "Full dashboard" to deep-link with the
variable already scoped to that Device.

The same mechanism works on InventoryItem pages: each role (e.g. `gpu`,
`psu`, `drive`) can point at its own dashboard, scoped by both the parent
Device variable and a component variable.

![Device page with embedded Grafana panels](docs/images/device-page.png)

## Features

- **Generic** — no hard-coded dashboard UIDs, role slugs, or vendor names.
  Works with any Grafana dashboard that has a templating variable scoped
  to a Device.
- **Theme sync** — preloads light + dark iframe variants, toggles by CSS.
  Switching NetBox theme is instant, no iframe reload, no flicker.
- **Multiple embed blocks per Device** — show several dashboards on one
  page (e.g. environmental + network + security).
- **Per-role dashboards** for InventoryItems — gpu, cpu, drive, fan, etc.
  Each role gets its own dashboard config.
- **Optional gates** — only render the embed when a custom field is set
  (e.g. only show the BMC dashboard if `bmc_ip` is filled).
- **Variable mapping** — choose what value to pass to the Grafana
  variable: device name, ID, or any custom field.
- **String replacements** — turn `"GPU 0"` into `"GPU_0"` (or anything
  else) when the dashboard's label format doesn't match NetBox's naming.

## Requirements

- NetBox `>= 4.0` (tested on 4.0–4.6)
- Python `>= 3.10`
- A Grafana that allows iframe embedding (`GF_SECURITY_ALLOW_EMBEDDING=true`
  on self-hosted; "Allow embedding" toggle on AWS Managed Grafana; etc.)

## Install

```bash
pip install netbox-grafana-embed
```

Then in your NetBox `configuration.py`:

```python
PLUGINS = [
    'netbox_grafana_embed',
]

PLUGINS_CONFIG = {
    'netbox_grafana_embed': {
        # REQUIRED: browser-facing Grafana base URL (the user's browser
        # loads iframe src from here; not the NetBox container).
        'grafana_url': 'https://grafana.example.com',

        # Optional global defaults (apply to every embed unless overridden)
        'from_range': 'now-1h',
        'to_range': 'now',
        'refresh': '1m',
        'theme_sync': True,
        'stat_panel_height_px': 120,
        'timeseries_panel_height_px': 260,

        # See "Configuration" below
        'device_embeds': [...],
        'inventory_item_embeds': {...},
    },
}
```

Restart NetBox + the rq-worker. The plugin loads automatically.

## Configuration

### Device embeds

`device_embeds` is a list of embed configurations rendered on every
`dcim.device` detail page. Most fields are optional — only `dashboard_uid`
is required per block.

```python
'device_embeds': [
    {
        # Required
        'dashboard_uid':    'my-server-dashboard',

        # Optional (recommended for prettier URLs)
        'dashboard_slug':   'my-server',

        # What heading appears on the card
        'title':            'Live metrics',

        # The Grafana template variable that scopes the dashboard to a
        # single Device. Default: 'device'.
        'device_variable':           'device',
        # Where to pull the variable's value from:
        #   'name'       → device.name (default)
        #   'id'         → device.id
        #   'cf:<field>' → device.custom_field_data[<field>]
        'device_variable_value_from': 'name',

        # Which panels in the dashboard to embed. Stat panels are
        # rendered as a horizontal row at the top; timeseries panels
        # are rendered stacked below, one per row.
        'stat_panels':       [3, 4, 6],
        'timeseries_panels': [10, 11],

        # Optional: only render this card when these custom-field gates
        # pass. Useful when not every Device has the relevant data.
        'show_if_custom_field_set': 'bmc_ip',     # CF must be non-empty
        'show_if_custom_field':     'bmc_monitored',  # CF must be truthy

        # Optional footer text under the panels.
        'footer': 'Out-of-band BMC telemetry.',
    },
],
```

### InventoryItem embeds

Per-role dashboards. Key is the `InventoryItemRole.slug`; only items whose
role matches will render the embed.

```python
'inventory_item_embeds': {
    'gpu': {
        'dashboard_uid':      'my-gpu-detail',
        'dashboard_slug':     'gpu-detail',
        'title':              'GPU live metrics',
        'device_variable':    'device',
        'component_variable': 'gpu',

        # How to derive the component variable's value from the
        # InventoryItem: same syntax as device_variable_value_from.
        'component_value_from': 'name',

        # Optional: transform the derived value before passing to Grafana.
        # List of (find, replace) pairs applied in order.
        # Example: NetBox item.name is "GPU 0", but the Prometheus label
        # is "GPU_0" — turn space into underscore.
        'component_value_replace': [(' ', '_')],

        'stat_panels':       [1, 2, 3, 4],
        'timeseries_panels': [10, 11],
    },
    'psu': {
        'dashboard_uid':      'my-psu-detail',
        'component_variable': 'psu',
        'stat_panels':        [1, 2],
        'timeseries_panels':  [10],
    },
    # ... one entry per role you want embedded
},
```

### Global defaults

| Key | Default | Purpose |
| --- | --- | --- |
| `grafana_url` | _(required)_ | Browser-facing Grafana base URL. No trailing slash. |
| `from_range` | `now-1h` | Default time-range start for embedded panels |
| `to_range` | `now` | Default time-range end |
| `refresh` | `1m` | Grafana `?refresh=` query param |
| `theme_sync` | `True` | Render dual light+dark iframes for instant theme toggle |
| `stat_panel_height_px` | `120` | iframe height for stat panels |
| `timeseries_panel_height_px` | `260` | iframe height for timeseries panels |

Any of these can be overridden per-embed by setting the same key inside
a `device_embeds` entry or an `inventory_item_embeds` value.

## How the iframes are constructed

For each panel listed in `stat_panels` / `timeseries_panels`, the plugin
emits a Grafana **panel-solo** URL:

```
{grafana_url}/d-solo/{dashboard_uid}/{dashboard_slug}
  ?panelId={pid}
  &var-{device_variable}={device_value}
  [&var-{component_variable}={component_value}]
  &from={from_range}&to={to_range}
  &refresh={refresh}
  &theme=light|dark
```

When `theme_sync=True`, two iframes are emitted per panel (light + dark)
and a small CSS rule toggles their visibility based on NetBox's
`html[data-bs-theme]` attribute. Cost: two iframe loads on page open;
benefit: zero-latency theme switch with no stream interruption.

## Grafana side

The plugin doesn't talk to Grafana — it just renders iframes the user's
browser will load. Make sure:

1. **Iframe embedding is allowed.**
   - Self-hosted Grafana: `GF_SECURITY_ALLOW_EMBEDDING=true`.
   - AWS Managed Grafana: enable embedding in workspace settings.
   - Grafana Cloud: contact support / use embed tokens.
2. **The user is authenticated to Grafana**, or anonymous viewer is
   enabled. The plugin doesn't pass auth on the user's behalf.
3. **The dashboard exists** with the configured `dashboard_uid` and has
   a templating variable matching `device_variable` (and
   `component_variable`, for InventoryItem embeds).

## Versioning + compatibility

| Plugin | NetBox |
| --- | --- |
| 1.x | 4.x |

Following [Semantic Versioning](https://semver.org/). Breaking changes
to the plugin config schema would bump the major version.

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache 2.0](LICENSE).
