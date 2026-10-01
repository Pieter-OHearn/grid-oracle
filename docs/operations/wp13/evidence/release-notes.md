## GridOracle runtime images

Version: `v0.1.0-wp13.7` · [Source commit](https://github.com/Pieter-OHearn/grid-oracle/commit/1942bb859a13e532c7ade24de203a38186705500)

All images support **linux/amd64** and **linux/arm64**.

| Component | Description | Immutable image |
| --- | --- | --- |
| [api](https://github.com/Pieter-OHearn/grid-oracle/pkgs/container/gridoracle-api) | GridOracle backend API serving published Formula 1 forecasts and provenance. | `ghcr.io/pieter-ohearn/gridoracle-api:v0.1.0-wp13.7@sha256:e0a5ecdb40245a7a470cb8e787ce79b3f56000e073c36229d985882e644d6af1` |
| [worker](https://github.com/Pieter-OHearn/grid-oracle/pkgs/container/gridoracle-worker) | GridOracle background worker and scheduler for bounded forecast jobs. | `ghcr.io/pieter-ohearn/gridoracle-worker:v0.1.0-wp13.7@sha256:5607fc616ff0726d7800e37b73d2c683bb58779fb108c241f17d0e22cb92f1f6` |
| [frontend](https://github.com/Pieter-OHearn/grid-oracle/pkgs/container/gridoracle-frontend) | GridOracle web dashboard for Formula 1 forecasts, results and provenance. | `ghcr.io/pieter-ohearn/gridoracle-frontend:v0.1.0-wp13.7@sha256:9ea4e980ad0082187d75362df7037d2e74cb369fb4450c10ac670267d9d1ccbd` |

The attached `release.json` records exact image digests, source revision,
architectures and workflow run. Promote its version@digest pins through a
reviewed homelab PR. This release performs no deployment.

## Changelog

- fix(ops): preserve OCI package descriptions and release baseline (WP13) ([1942bb8](https://github.com/Pieter-OHearn/grid-oracle/commit/1942bb859a13e532c7ade24de203a38186705500))
- fix(ops): include unmerged staging commits in release changelog (WP13) ([9649dca](https://github.com/Pieter-OHearn/grid-oracle/commit/9649dca9a669eb5028411e1df94d27799f1d89aa))
- feat(ops): add tagged release workflow changelog and image descriptions (WP13) ([b60a67a](https://github.com/Pieter-OHearn/grid-oracle/commit/b60a67a8d7197f57a5e4f40eb70fef5376c3dd5d))
- docs(ops): record corrected WP13 review candidate ([1cac5f2](https://github.com/Pieter-OHearn/grid-oracle/commit/1cac5f2afd8cb5aecf5520d04fbc02d799579828))
- docs(ops): record corrected WP13 release and recovery evidence ([1e15bb2](https://github.com/Pieter-OHearn/grid-oracle/commit/1e15bb2ff7c13fbd07d7de1f1a538a2c4ecef08e))

**Full Changelog**: https://github.com/Pieter-OHearn/grid-oracle/compare/v0.1.0-wp13.4...v0.1.0-wp13.7

