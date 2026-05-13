# Contributing

Thanks for considering a contribution.

## Reporting issues

- Search [existing issues](https://github.com/AlphaCompute/netbox-grafana-embed/issues)
  first.
- For bugs, include: NetBox version, plugin version, Grafana version, the
  relevant chunk of your `PLUGINS_CONFIG['netbox_grafana_embed']`, and
  the rendered HTML / browser-side error (if any).

## Development

```bash
git clone https://github.com/AlphaCompute/netbox-grafana-embed.git
cd netbox-grafana-embed
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest
```

To try it against a live NetBox, install it into the NetBox venv:

```bash
/opt/netbox/venv/bin/pip install -e /path/to/your/clone
```

Then add `'netbox_grafana_embed'` to `PLUGINS` in your NetBox
configuration and restart NetBox + the rq-worker.

## Pull requests

1. Branch from `main`.
2. Keep changes focused — one feature / fix per PR.
3. Update `CHANGELOG.md` under an `## [Unreleased]` heading.
4. Run `ruff check .` and `pytest` locally.
5. PRs that change behaviour should add or update tests.

## Schema-breaking changes

The plugin config schema (`PLUGINS_CONFIG['netbox_grafana_embed']`) is
part of the public contract. Breaking changes require a major version
bump and a clear deprecation path.

## License

By contributing you agree your contributions are licensed under
[Apache 2.0](LICENSE).
