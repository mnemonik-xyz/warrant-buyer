# warrant-buyer

Packaging for the `warrant-buyer` Python package: the buyer guardrail for Warrant. An AI agent
buys compute with USDC on Arc. The agent holds no key that can pay. The local guardrail holds
the wallet key and the spending cap, funds the escrow and signs the acceptance.

```sh
uvx warrant-buyer init      # makes a new wallet and prints the MCP client configuration
uvx warrant-buyer status    # shows the wallet address and its USDC balance
```

User documentation is in [`packaging/warrant-buyer/README.md`](packaging/warrant-buyer/README.md).
That file is the PyPI description.

## What is in a wheel

A wheel for one platform holds two things:

| Part | Where it comes from | Pinned by |
|---|---|---|
| The Python buyer code (`showcases/ionet_arc`: guardrail, `init`, escrow client, config) | [`mnemonik-xyz/warrant-showcases`](https://github.com/mnemonik-xyz/warrant-showcases) | [`source.lock`](source.lock): repository and commit |
| `warrant-policy` and `warrant-evidence` | A release of [`mnemonik-xyz/policy-execution`](https://github.com/mnemonik-xyz/policy-execution) | [`core.lock`](core.lock): tag and SHA-256 of each file |

This repository compiles nothing. The buyer code is shared with the seller, so it stays in
`warrant-showcases`. There are no submodules.

```sh
python scripts/fetch_source.py fetch              # check out the pinned commit into .src/
python scripts/fetch_core.py fetch --tools-only   # download the helper binaries into .core/bin
scripts/build-buyer-wheel.sh <version> .core/bin <platform-tag> dist
```

- `fetch_source.py fetch` confirms that the checkout is the pinned commit.
- `fetch_core.py fetch` stops when a download differs from `core.lock`.
- To upgrade, run `fetch_source.py pin main` or `fetch_core.py lock <core tag>` and review the diff.
  Both trust the remote once.

## Release

1. Update the pins if needed and merge by pull request.
2. Push a tag `buyer-vX.Y.Z` on `main`.
3. The workflow builds a wheel for linux x86_64, linux arm64 and macOS arm64, installs each in a
   clean environment, runs `warrant-buyer init`, computes a policy hash, starts the guardrail over
   stdio, and then publishes to PyPI.

A pull request or a manual run builds and tests the wheels and never publishes.

### Settings that a pull request cannot change

- PyPI: the trusted publisher of the `warrant-buyer` project must name this repository
  (`mnemonik-xyz/warrant-buyer`), the workflow file `release.yml` and the environment `pypi`.
- GitHub: create the environment `pypi` with required reviewers. Add a tag ruleset for `buyer-v*`.

## Tests

```sh
python -m unittest discover tests
ruff check scripts tests
```

## License

See [LICENSE](LICENSE).
