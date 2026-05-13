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
