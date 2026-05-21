"""Render Grafana iframe blocks on NetBox Device and InventoryItem pages.

All behaviour is driven by ``PLUGINS_CONFIG['netbox_grafana_embed']`` —
see ``__init__.py`` for the full schema.
"""
import logging
from functools import lru_cache

from django.conf import settings
from netbox.plugins import PluginTemplateExtension

log = logging.getLogger(__name__)


def _cfg():
    return settings.PLUGINS_CONFIG.get('netbox_grafana_embed', {}) or {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_value(obj, expr):
    """Resolve a value spec like 'name', 'id', or 'cf:my_field' against an
    object that has ``.name``, ``.id``, and (optionally) ``.custom_field_data``.

    Returns a string, or None if the field is missing.
    """
    if not expr:
        return getattr(obj, 'name', None)
    if expr == 'name':
        return getattr(obj, 'name', None)
    if expr == 'id':
        v = getattr(obj, 'id', None)
        return str(v) if v is not None else None
    if expr.startswith('cf:'):
        field = expr[3:]
        cfs = getattr(obj, 'custom_field_data', None) or {}
        v = cfs.get(field)
        return str(v) if v is not None else None
    # Unknown expr — fall back to literal
    return expr


def _apply_replacements(value, replacements):
    """``replacements`` is a list of (find, replace) tuples / lists."""
    if not value or not replacements:
        return value
    out = value
    for pair in replacements:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        out = out.replace(pair[0], pair[1])
    return out


def _gate_passes(device, embed):
    """Evaluate optional ``show_if_*`` gates against the parent Device's
    custom fields. Returns True if the embed should render."""
    cfs = getattr(device, 'custom_field_data', None) or {}
    require_set = embed.get('show_if_custom_field_set')
    if require_set and not cfs.get(require_set):
        return False
    require_truthy = embed.get('show_if_custom_field')
    if require_truthy and not cfs.get(require_truthy):
        return False
    return True


def _shared_context(cfg, embed):
    """Defaults pulled from top-level config; per-embed values override."""
    return {
        'grafana_url':                cfg.get('grafana_url', '').rstrip('/'),
        'from_range':                 embed.get('from_range',  cfg.get('from_range',  'now-1h')),
        'to_range':                   embed.get('to_range',    cfg.get('to_range',    'now')),
        'refresh':                    embed.get('refresh',     cfg.get('refresh',     '1m')),
        'stat_panel_height_px':       embed.get('stat_panel_height_px',
                                                cfg.get('stat_panel_height_px', 120)),
        'timeseries_panel_height_px': embed.get('timeseries_panel_height_px',
                                                cfg.get('timeseries_panel_height_px', 260)),
        'whole_dashboard':            bool(embed.get('whole_dashboard',
                                                     cfg.get('whole_dashboard', False))),
        'whole_dashboard_height_px':  _resolve_whole_dashboard_height(
            embed.get('whole_dashboard_height_px',
                      cfg.get('whole_dashboard_height_px', 800)),
            cfg=cfg, dashboard_uid=embed.get('dashboard_uid', '')),
        # Pre-built leading querystring fragment for whole-dashboard mode.
        # See _kiosk_prefix() for the mapping from operator config.
        'kiosk_prefix':               _kiosk_prefix(
            embed.get('kiosk_mode', cfg.get('kiosk_mode', ''))),
        # Pre-built `&_dash.hide*=true` querystring fragment for whole-
        # dashboard mode. Empty string when nothing is hidden.
        'dash_chrome_fragment':       _dash_chrome_fragment(
            hide_variables=bool(embed.get('hide_variables',
                                          cfg.get('hide_variables', False))),
            hide_time_picker=bool(embed.get('hide_time_picker',
                                            cfg.get('hide_time_picker', False))),
            hide_links=bool(embed.get('hide_links',
                                      cfg.get('hide_links', False))),
        ),
        'theme_sync':                 embed.get('theme_sync',  cfg.get('theme_sync',  True)),
    }


def _kiosk_prefix(value):
    """Build the leading `?<kiosk_prefix>var-…` fragment for whole-dashboard
    mode. The prefix is always either empty or ends in "&" so the rest of
    the querystring concatenates cleanly.

    Operator config (``kiosk_mode``) maps as follows:

      ``None`` / ``False`` → ``""``        — omit the kiosk param; embed
                                              shows full Grafana chrome.
      ``""``               → ``"kiosk&"``  — bare ``?kiosk`` (boolean
                                              true). Hides Grafana top nav
                                              + hamburger, keeps the
                                              dashboard's own variable /
                                              timepicker subnav. Default.
      ``"tv"``             → ``"kiosk=tv&"`` — legacy alias, same effect.
      any other string     → ``"kiosk=<value>&"`` — forwarded verbatim.
    """
    if value is None or value is False:
        return ''
    if value == '':
        return 'kiosk&'
    return f'kiosk={value}&'


def _resolve_whole_dashboard_height(value, *, cfg, dashboard_uid):
    """Resolve `whole_dashboard_height_px` to an int.

    Pass-through for ints / numeric strings; for the literal ``'auto'``
    the helper fetches the dashboard JSON from Grafana, sums up the
    grid extent, multiplies by ``whole_dashboard_cell_height_px``, and
    adds ``whole_dashboard_padding_px``. Falls back to ``800`` (the
    safe default also used elsewhere) on any HTTP / parse error.
    """
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    if value != 'auto':
        # Unknown sentinel — return a sane default rather than crashing
        # the page render.
        return 800

    base = cfg.get('grafana_internal_url') or cfg.get('grafana_url', '')
    base = base.rstrip('/')
    token = cfg.get('grafana_api_token', '')
    cell_px = int(cfg.get('whole_dashboard_cell_height_px', 32))
    padding_px = int(cfg.get('whole_dashboard_padding_px', 120))
    timeout_s = float(cfg.get('whole_dashboard_fetch_timeout_s', 2.0))
    return _cached_dashboard_height(
        base, dashboard_uid, token, cell_px, padding_px, timeout_s,
    )


@lru_cache(maxsize=128)
def _cached_dashboard_height(base_url, dashboard_uid, token,
                             cell_px, padding_px, timeout_s):
    """Per-worker cache around the Grafana API call. Cleared on
    NetBox restart, which is the expected workflow when an operator
    redesigns a dashboard."""
    try:
        # Imported lazily so the test shim doesn't have to provide it.
        import requests
        url = f'{base_url}/api/dashboards/uid/{dashboard_uid}'
        headers = {'Accept': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        resp = requests.get(url, headers=headers, timeout=timeout_s)
        resp.raise_for_status()
        panels = (resp.json().get('dashboard') or {}).get('panels') or []
        max_bottom = 0
        for p in panels:
            gp = p.get('gridPos') or {}
            bottom = int(gp.get('y', 0)) + int(gp.get('h', 0))
            if bottom > max_bottom:
                max_bottom = bottom
        if max_bottom == 0:
            log.warning(
                'netbox_grafana_embed: dashboard %s has no panels with '
                'gridPos; falling back to 800px', dashboard_uid)
            return 800
        return max_bottom * cell_px + padding_px
    except Exception as exc:
        log.warning(
            'netbox_grafana_embed: auto-height fetch failed for %s '
            '(%s); falling back to 800px', dashboard_uid, exc)
        return 800


def _dash_chrome_fragment(*, hide_variables, hide_time_picker, hide_links):
    """Build the `&_dash.hide*=true` querystring suffix that toggles
    individual pieces of the dashboard subnav inside a whole-dashboard
    embed. Each input is a bool; only the True ones produce a fragment.

    Grafana 11+ Scenes-based dashboards honour these URL params:
      - ``_dash.hideVariables=true``   hides the variable dropdowns
        (typically the per-dashboard `var-*` template selectors).
      - ``_dash.hideTimePicker=true``  hides the time range picker
        and the auto-refresh dropdown.
      - ``_dash.hideLinks=true``       hides any custom dashboard
        links / external buttons configured in the dashboard model.

    The returned string is always either empty or a sequence of
    "&_dash.X=true" tokens — designed to be appended to an existing
    querystring (so it leads with "&", not "?").
    """
    parts = []
    if hide_variables:
        parts.append('&_dash.hideVariables=true')
    if hide_time_picker:
        parts.append('&_dash.hideTimePicker=true')
    if hide_links:
        parts.append('&_dash.hideLinks=true')
    return ''.join(parts)


# ---------------------------------------------------------------------------
# Plugin template extensions
# ---------------------------------------------------------------------------

class DeviceGrafanaPanels(PluginTemplateExtension):
    """Render every configured device_embed block on dcim.device pages."""
    models = ['dcim.device']

    def full_width_page(self):
        device = self.context.get('object')
        if device is None:
            return ''
        cfg = _cfg()
        embeds = cfg.get('device_embeds') or []
        if not embeds:
            return ''

        blocks = []
        for embed in embeds:
            if not embed.get('dashboard_uid'):
                continue
            if not _gate_passes(device, embed):
                continue
            value = _resolve_value(device, embed.get('device_variable_value_from', 'name'))
            if value is None:
                continue
            shared = _shared_context(cfg, embed)
            stat_panels = embed.get('stat_panels') or []
            stat_col_md = max(3, 12 // max(1, len(stat_panels)))
            blocks.append({
                'title':           embed.get('title', 'Live metrics'),
                'dashboard_uid':   embed['dashboard_uid'],
                'dashboard_slug':  embed.get('dashboard_slug', embed['dashboard_uid']),
                'device_variable': embed.get('device_variable', 'device'),
                'device_value':    value,
                'stat_panels':     stat_panels,
                'stat_col_md':     stat_col_md,
                'timeseries_panels': embed.get('timeseries_panels') or [],
                'footer':          embed.get('footer', ''),
                **shared,
            })

        if not blocks:
            return ''
        return self.render(
            'netbox_grafana_embed/device_panels.html',
            extra_context={'device': device, 'blocks': blocks},
        )


class InventoryItemGrafanaPanels(PluginTemplateExtension):
    """Render configured embed for the InventoryItem.role.slug, if any."""
    models = ['dcim.inventoryitem']

    def full_width_page(self):
        item = self.context.get('object')
        if item is None or item.role is None:
            return ''
        cfg = _cfg()
        per_role = cfg.get('inventory_item_embeds') or {}
        embed = per_role.get(item.role.slug)
        if not embed or not embed.get('dashboard_uid'):
            return ''
        device = item.device
        if device is None:
            return ''
        if not _gate_passes(device, embed):
            return ''

        device_var = embed.get('device_variable', 'device')
        device_value = _resolve_value(
            device, embed.get('device_variable_value_from', 'name'))

        comp_var = embed.get('component_variable', item.role.slug)
        raw_value = _resolve_value(item, embed.get('component_value_from', 'name'))
        comp_value = _apply_replacements(raw_value, embed.get('component_value_replace'))
        if comp_value is None:
            return ''

        stat_panels = embed.get('stat_panels') or []
        ts_panels = embed.get('timeseries_panels') or []
        # Bootstrap grid: 12 cols total → col width per stat panel
        stat_col_md = max(3, 12 // max(1, len(stat_panels)))

        shared = _shared_context(cfg, embed)
        block = {
            'title':             embed.get('title', f'{item.role.name} metrics'),
            'dashboard_uid':     embed['dashboard_uid'],
            'dashboard_slug':    embed.get('dashboard_slug', embed['dashboard_uid']),
            'device_variable':   device_var,
            'device_value':      device_value,
            'component_variable': comp_var,
            'component_value':   comp_value,
            'stat_panels':       stat_panels,
            'stat_col_md':       stat_col_md,
            'timeseries_panels': ts_panels,
            'footer':            embed.get('footer', ''),
            **shared,
        }
        return self.render(
            'netbox_grafana_embed/inventory_item_panels.html',
            extra_context={'item': item, 'device': device, 'block': block},
        )


template_extensions = [DeviceGrafanaPanels, InventoryItemGrafanaPanels]
