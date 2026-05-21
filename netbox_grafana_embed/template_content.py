"""Render Grafana iframe blocks on NetBox Device and InventoryItem pages.

All behaviour is driven by ``PLUGINS_CONFIG['netbox_grafana_embed']`` —
see ``__init__.py`` for the full schema.
"""
from django.conf import settings
from netbox.plugins import PluginTemplateExtension


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
        'whole_dashboard_height_px':  embed.get('whole_dashboard_height_px',
                                                cfg.get('whole_dashboard_height_px', 800)),
        # Pre-built leading querystring fragment for whole-dashboard mode.
        # See _kiosk_prefix() for the mapping from operator config.
        'kiosk_prefix':               _kiosk_prefix(
            embed.get('kiosk_mode', cfg.get('kiosk_mode', ''))),
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
