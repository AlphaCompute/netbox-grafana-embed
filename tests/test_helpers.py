"""Pure-Python tests for the value-resolution and gate helpers.

These tests deliberately avoid importing template_content.py at module
level — that module pulls in django.conf, which isn't available without
a full NetBox install. We import the helpers via a small shim that
stubs the Django bits.
"""
import sys
import types

# Stub django.conf.settings so the module imports outside of NetBox.
django = types.ModuleType("django")
django_conf = types.ModuleType("django.conf")


class _Settings:
    PLUGINS_CONFIG = {}


django_conf.settings = _Settings()
django.conf = django_conf
sys.modules.setdefault("django", django)
sys.modules.setdefault("django.conf", django_conf)

# Stub netbox.plugins.PluginTemplateExtension too.
netbox = types.ModuleType("netbox")
netbox_plugins = types.ModuleType("netbox.plugins")


class _PluginTemplateExtension:
    def __init__(self, *a, **kw):
        pass


class _PluginConfig:
    """Stand-in for netbox.plugins.PluginConfig — captures class attrs only."""
    name = ''
    verbose_name = ''
    version = ''
    default_settings: dict = {}
    required_settings: list = []


netbox_plugins.PluginTemplateExtension = _PluginTemplateExtension
netbox_plugins.PluginConfig = _PluginConfig
netbox.plugins = netbox_plugins
sys.modules.setdefault("netbox", netbox)
sys.modules.setdefault("netbox.plugins", netbox_plugins)

from netbox_grafana_embed import template_content as tc  # noqa: E402


class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_resolve_value_name():
    obj = _Obj(name="srv-01", id=42)
    assert tc._resolve_value(obj, "name") == "srv-01"


def test_resolve_value_id():
    obj = _Obj(name="srv-01", id=42)
    assert tc._resolve_value(obj, "id") == "42"


def test_resolve_value_custom_field():
    obj = _Obj(name="srv-01", id=42, custom_field_data={"bmc_ip": "10.0.0.5"})
    assert tc._resolve_value(obj, "cf:bmc_ip") == "10.0.0.5"


def test_resolve_value_missing_custom_field():
    obj = _Obj(name="srv-01", id=42, custom_field_data={})
    assert tc._resolve_value(obj, "cf:missing") is None


def test_resolve_value_default_falls_back_to_name():
    obj = _Obj(name="srv-01", id=42)
    assert tc._resolve_value(obj, None) == "srv-01"


def test_apply_replacements_basic():
    assert tc._apply_replacements("GPU 0", [(" ", "_")]) == "GPU_0"


def test_apply_replacements_chain():
    out = tc._apply_replacements("DIMM P2-DIMMH2", [("DIMM ", ""), ("-", "_")])
    assert out == "P2_DIMMH2"


def test_apply_replacements_noop():
    assert tc._apply_replacements("plain", []) == "plain"
    assert tc._apply_replacements("plain", None) == "plain"
    assert tc._apply_replacements(None, [("a", "b")]) is None


def test_gate_passes_no_gates():
    device = _Obj(custom_field_data={"any": "thing"})
    assert tc._gate_passes(device, {}) is True


def test_gate_passes_set_truthy():
    device = _Obj(custom_field_data={"bmc_ip": "10.0.0.5"})
    assert tc._gate_passes(device, {"show_if_custom_field_set": "bmc_ip"}) is True


def test_gate_blocks_when_required_field_empty():
    device = _Obj(custom_field_data={"bmc_ip": ""})
    assert tc._gate_passes(device, {"show_if_custom_field_set": "bmc_ip"}) is False


def test_gate_blocks_when_required_field_missing():
    device = _Obj(custom_field_data={})
    assert tc._gate_passes(device, {"show_if_custom_field_set": "bmc_ip"}) is False


def test_gate_blocks_when_truthy_field_falsy():
    device = _Obj(custom_field_data={"bmc_monitored": False})
    assert tc._gate_passes(device, {"show_if_custom_field": "bmc_monitored"}) is False


def test_gate_passes_when_truthy_field_true():
    device = _Obj(custom_field_data={"bmc_monitored": True})
    assert tc._gate_passes(device, {"show_if_custom_field": "bmc_monitored"}) is True


def test_shared_context_uses_embed_overrides():
    cfg = {"from_range": "now-1h", "stat_panel_height_px": 100}
    embed = {"from_range": "now-7d", "timeseries_panel_height_px": 320}
    ctx = tc._shared_context(cfg, embed)
    assert ctx["from_range"] == "now-7d"
    assert ctx["to_range"] == "now"          # from cfg default
    assert ctx["stat_panel_height_px"] == 100
    assert ctx["timeseries_panel_height_px"] == 320
    assert ctx["theme_sync"] is True


def test_shared_context_whole_dashboard_defaults_off():
    ctx = tc._shared_context({}, {})
    assert ctx["whole_dashboard"] is False
    assert ctx["whole_dashboard_height_px"] == 800


def test_shared_context_whole_dashboard_per_embed_override():
    cfg = {"whole_dashboard": False, "whole_dashboard_height_px": 800}
    embed = {"whole_dashboard": True, "whole_dashboard_height_px": 1400}
    ctx = tc._shared_context(cfg, embed)
    assert ctx["whole_dashboard"] is True
    assert ctx["whole_dashboard_height_px"] == 1400


def test_shared_context_whole_dashboard_global_default():
    cfg = {"whole_dashboard": True}
    ctx = tc._shared_context(cfg, {})
    assert ctx["whole_dashboard"] is True
    assert ctx["whole_dashboard_height_px"] == 800


def test_kiosk_prefix_default_empty_string():
    # Default operator config — bare ?kiosk (cleanest embed).
    assert tc._kiosk_prefix("") == "kiosk&"


def test_kiosk_prefix_legacy_tv_value():
    assert tc._kiosk_prefix("tv") == "kiosk=tv&"


def test_kiosk_prefix_arbitrary_value_forwarded():
    # Future Grafana kiosk values pass through verbatim.
    assert tc._kiosk_prefix("anything") == "kiosk=anything&"


def test_kiosk_prefix_none_omits_param():
    assert tc._kiosk_prefix(None) == ""


def test_kiosk_prefix_false_omits_param():
    assert tc._kiosk_prefix(False) == ""


def test_shared_context_kiosk_prefix_default():
    ctx = tc._shared_context({}, {})
    # Default '' → bare ?kiosk.
    assert ctx["kiosk_prefix"] == "kiosk&"


def test_shared_context_kiosk_prefix_per_embed_override():
    cfg = {"kiosk_mode": ""}
    embed = {"kiosk_mode": None}
    ctx = tc._shared_context(cfg, embed)
    assert ctx["kiosk_prefix"] == ""


def test_dash_chrome_fragment_all_off():
    assert tc._dash_chrome_fragment(
        hide_variables=False, hide_time_picker=False, hide_links=False
    ) == ""


def test_dash_chrome_fragment_only_variables():
    assert tc._dash_chrome_fragment(
        hide_variables=True, hide_time_picker=False, hide_links=False
    ) == "&_dash.hideVariables=true"


def test_dash_chrome_fragment_only_time_picker():
    assert tc._dash_chrome_fragment(
        hide_variables=False, hide_time_picker=True, hide_links=False
    ) == "&_dash.hideTimePicker=true"


def test_dash_chrome_fragment_only_links():
    assert tc._dash_chrome_fragment(
        hide_variables=False, hide_time_picker=False, hide_links=True
    ) == "&_dash.hideLinks=true"


def test_dash_chrome_fragment_all_on_order_stable():
    # Order is variables, time picker, links — stable so URLs are diffable.
    assert tc._dash_chrome_fragment(
        hide_variables=True, hide_time_picker=True, hide_links=True
    ) == "&_dash.hideVariables=true&_dash.hideTimePicker=true&_dash.hideLinks=true"


def test_shared_context_dash_chrome_default_empty():
    ctx = tc._shared_context({}, {})
    assert ctx["dash_chrome_fragment"] == ""


def test_shared_context_dash_chrome_per_embed_override():
    cfg = {"hide_variables": False, "hide_links": False}
    embed = {"hide_variables": True, "hide_links": True}
    ctx = tc._shared_context(cfg, embed)
    assert ctx["dash_chrome_fragment"] == "&_dash.hideVariables=true&_dash.hideLinks=true"
