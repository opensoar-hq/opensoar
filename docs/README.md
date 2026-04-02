## OpenSOAR Docs

Documentation for OpenSOAR, intended to be deployed at `docs.opensoar.app`.

### Local Development

```bash
uv sync
uv run zensical serve
```

By default, the local preview is available at `http://127.0.0.1:8000`.

### Build

```bash
uv run zensical build
```

The generated static site is written to `site/`.

### Scope

This docs app includes:

- installation and upgrades
- playbook authoring and deployment
- integrations
- API usage
- troubleshooting and migration guides
- engineering and architecture references for contributors

Business, launch, and positioning material should not live here.
