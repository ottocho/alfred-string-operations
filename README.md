# String Operations

Format clipboard JSON and change text case in Alfred. Uses `uv` and Python’s standard library; no packages or virtual environments.

## Install

Requires macOS, Alfred Powerpack, [uv](https://docs.astral.sh/uv/getting-started/installation/), and Python 3.10+. If needed: `uv python install 3.12`.

From this repository:

```sh
make install
```

Confirm the Alfred import. Disable the old String Operations workflow to avoid duplicate keywords.

## Use

Copy text, run a keyword in Alfred, then paste.

| Keyword | Action |
| --- | --- |
| `json.pretty` | Format JSON with four-space indentation and sorted keys |
| `camelCase` | Convert to camelCase |
| `snake_case` | Convert to snake_case |
| `underscore_case` | Alias of snake_case |
| `kebab-case` | Convert to kebab-case |
| `lowercase` | Convert to lowercase |
| `uppercase` | Convert to UPPERCASE |

Invalid JSON leaves the clipboard unchanged. Check Alfred’s workflow debugger for errors.

## Development

```sh
make test    # Run tests without touching the clipboard
make build   # Create dist/String-Operations.alfredworkflow
```

Edit `workflow/`, then run `make install` to apply changes. For releases, update the version in `workflow/info.plist`, test, build, and attach the package to a GitHub release.
