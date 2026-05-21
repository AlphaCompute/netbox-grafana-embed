"""netbox-grafana-embed: embed Grafana panels on NetBox Device and
InventoryItem detail pages.

Configuration lives entirely in ``PLUGINS_CONFIG['netbox_grafana_embed']``.
See README.md for the full schema and examples.
"""
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from netbox.plugins import PluginConfig

try:
    __version__ = _pkg_version('netbox-grafana-embed')
except PackageNotFoundError:
    __version__ = '0.0.0+unknown'


class GrafanaEmbedConfig(PluginConfig):
    name = 'netbox_grafana_embed'
    verbose_name = 'Grafana Embed'
    description = 'Embed Grafana panels on NetBox Device and InventoryItem pages.'
    version = __version__
    author = 'AlphaCompute'
    author_email = 'opensource@alphacompute.io'
    base_url = 'grafana-embed'
    min_version = '4.0.0'
    max_version = '4.99.99'

    # Operator must at least set grafana_url + one embed config.
    required_settings = ['grafana_url']

    default_settings = {
        # --- Grafana endpoint ------------------------------------------------
        # Browser-facing URL — the user's browser loads iframe src from here.
        # Must be reachable from the NetBox user's browser (not from inside
        # the NetBox container).
        'grafana_url': '',

        # --- Time range ------------------------------------------------------
        'from_range': 'now-1h',
        'to_range': 'now',

        # --- iframe sizing (px) ----------------------------------------------
        'stat_panel_height_px': 120,
        'timeseries_panel_height_px': 260,
        # Default iframe height when an embed sets `whole_dashboard: True`
        # and renders the full dashboard as a single iframe. Accepts:
        #   - int (e.g. 1500)   — explicit pixel height. Browsers can't
        #                         auto-grow cross-origin iframes, so this
        #                         is the simplest mode: pick a number that
        #                         covers your dashboard with margin.
        #   - 'auto'            — fetch the dashboard JSON from Grafana
        #                         once, compute `max(panel.y+panel.h) *
        #                         whole_dashboard_cell_height_px +
        #                         whole_dashboard_padding_px`, and use that.
        #                         Result is cached per-uid for the lifetime
        #                         of the worker process. Requires
        #                         `grafana_internal_url` to be reachable
        #                         from the NetBox container (Grafana API
        #                         is hit server-side, not through the
        #                         browser) and optionally
        #                         `grafana_api_token` for non-anonymous
        #                         Grafana setups. On any failure (HTTP
        #                         error, missing dashboard, no auth) the
        #                         embed falls back to the integer default
        #                         below.
        'whole_dashboard_height_px': 800,

        # --- Server-side Grafana API access (used only by 'auto' mode) -------
        # Browser-facing `grafana_url` above is what ends up in the
        # iframe `src` — must be reachable from the user's browser. The
        # `grafana_internal_url` below is what the NetBox process uses
        # to fetch dashboard JSON for height computation; defaults to
        # `grafana_url` (sensible for setups where Grafana is on the
        # public internet) but in docker-compose it usually needs to be
        # the in-network service name, e.g. 'http://grafana:3000'.
        'grafana_internal_url': '',
        # Bearer token for the Grafana API call. Empty disables the
        # Authorization header — fine when Grafana has anonymous viewer
        # access enabled for the relevant org/folder.
        'grafana_api_token': '',
        # Grafana renders one dashboard grid row at 30 px + an 8 px
        # inter-row margin = 38 px. Using 38 as the per-unit cost
        # treats every row as a full row plus its trailing margin,
        # which slightly over-counts but errs on the side of no
        # internal scrollbar.
        'whole_dashboard_cell_height_px': 38,
        # Fixed pixels added on top of the computed grid total.
        # Covers the dashboard subnav (variable / time-picker bar,
        # ~50 px), outer Grafana padding (~30 px), the "Powered by
        # Grafana" footer (~30 px), and a generous safety margin so
        # a tall last-row panel never gets its body clipped.
        'whole_dashboard_padding_px': 240,
        # HTTP timeout (seconds) for the dashboard JSON fetch. Page
        # render falls back to the integer default if exceeded.
        'whole_dashboard_fetch_timeout_s': 2.0,

        # --- Whole-dashboard mode chrome control -----------------------------
        # Value passed to Grafana's ?kiosk= URL param when whole_dashboard
        # is True. Effective values (Grafana 13):
        #   ''           → renders as ?kiosk (boolean true). Hides Grafana
        #                  top nav + hamburger toggle; keeps the dashboard's
        #                  own variable / timepicker subnav. Cleanest embed.
        #   'tv'         → ?kiosk=tv. Legacy alias, same effect.
        #   None / False → omit the kiosk param entirely. Embed shows full
        #                  Grafana chrome (breadcrumb, search, sign-in).
        #   other str    → forwarded verbatim, for future Grafana values.
        'kiosk_mode': '',

        # Granular dashboard-subnav toggles for whole-dashboard mode.
        # Grafana 11+ Scenes-based dashboards expose `_dash.hideX=true`
        # URL params; each flag here is a thin boolean wrapper around
        # one of those. All three default False (subnav stays visible).
        # Useful when the embed already has equivalent context from
        # NetBox (e.g. the parent device page name already tells the
        # user which server they're looking at, so `hide_variables`
        # removes the redundant Grafana variable dropdowns).
        'hide_variables':   False,
        'hide_time_picker': False,
        'hide_links':       False,

        # --- Theme sync ------------------------------------------------------
        # When True, the plugin renders BOTH light and dark theme iframes
        # and toggles their CSS visibility based on NetBox's data-bs-theme
        # attribute — gives instant theme switch with no iframe reload.
        # Cost: 2× iframe loads on page open.
        # Set False to render a single iframe (theme=light by default).
        'theme_sync': True,

        # --- Refresh hint passed to Grafana (the iframe src ?refresh= param)
        'refresh': '1m',

        # --- Device embeds ---------------------------------------------------
        # List of embed blocks rendered on dcim.device detail pages. Each
        # block becomes one card with title, "Full dashboard" link, and the
        # configured stat/timeseries panels.
        #
        # Example:
        #   'device_embeds': [
        #     {
        #       'title': 'Live metrics',
        #       'dashboard_uid': 'my-server',
        #       'dashboard_slug': 'my-server-detail',  # optional, URL prettier
        #       'device_variable': 'device',
        #       'device_variable_value_from': 'name',  # 'name' | 'id' |
        #                                              # 'cf:<custom_field_name>'
        #       'stat_panels': [3, 4, 6],
        #       'timeseries_panels': [10, 11],
        #       # Optional gate — show only if Device.custom_field_data has
        #       # a non-empty value for this field.
        #       'show_if_custom_field_set': 'bmc_ip',
        #       # Optional gate — show only if this CF is truthy.
        #       'show_if_custom_field': 'bmc_monitored',
        #       # Optional footer text shown under the panels.
        #       'footer': 'Out-of-band BMC telemetry.',
        #     },
        #   ]
        #
        # Alternative — embed the whole dashboard as a single iframe
        # instead of per-panel `d-solo` iframes. One Grafana boot
        # instead of 2 × len(stat_panels + timeseries_panels), and
        # Grafana lays the panels out itself:
        #   'device_embeds': [
        #     {
        #       'title': 'Live metrics',
        #       'dashboard_uid': 'my-server',
        #       'dashboard_slug': 'my-server-detail',
        #       'device_variable': 'device',
        #       'whole_dashboard': True,
        #       'whole_dashboard_height_px': 1400,  # override 800 default
        #     },
        #   ]
        # In whole-dashboard mode `stat_panels` and `timeseries_panels`
        # are ignored — Grafana renders the dashboard's own layout
        # inside the iframe (with `?kiosk=tv` to hide Grafana chrome).
        'device_embeds': [],

        # --- InventoryItem embeds --------------------------------------------
        # Mapping {InventoryItemRole.slug → embed config}. Rendered on the
        # dcim.inventoryitem detail page when item.role.slug matches.
        #
        # Example:
        #   'inventory_item_embeds': {
        #     'gpu': {
        #       'title': 'GPU live metrics',
        #       'dashboard_uid': 'my-gpu',
        #       'dashboard_slug': 'my-gpu-detail',
        #       'device_variable': 'device',
        #       'component_variable': 'gpu',
        #       # How to derive the component variable value from the
        #       # InventoryItem: 'name' (default), 'id', 'cf:<field>'.
        #       'component_value_from': 'name',
        #       # Optional list of (find, replace) string pairs applied to
        #       # the derived value (e.g. [(' ', '_')] to turn "GPU 0" into
        #       # "GPU_0" for a Prometheus label).
        #       'component_value_replace': [],
        #       'stat_panels': [1, 2, 3, 4],
        #       'timeseries_panels': [10, 11],
        #       # Same gates as device_embeds (evaluated against the parent
        #       # Device's custom fields).
        #       'show_if_custom_field_set': None,
        #       'show_if_custom_field': None,
        #     },
        #   }
        'inventory_item_embeds': {},
    }


config = GrafanaEmbedConfig
