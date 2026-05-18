"""netbox-grafana-embed: embed Grafana panels on NetBox Device and
InventoryItem detail pages.

Configuration lives entirely in ``PLUGINS_CONFIG['netbox_grafana_embed']``.
See README.md for the full schema and examples.
"""
from netbox.plugins import PluginConfig

__version__ = '1.0.3'


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
