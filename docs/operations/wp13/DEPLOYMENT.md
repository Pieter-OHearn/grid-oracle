# WP13 deployment and recovery design

WP13 implements application packaging and disposable acceptance tools. The
runtime stack and service catalog belong to the **DevOps agent in homelab**.
The owner clarified that this task prepares only the GridOracle side; do not
edit the homelab repository or maintain its proposal PR from this task. No host provisioning, SOPS change, DNS change, production apply or
public exposure is performed by this package. Staging fixtures are synthetic;
restart/recovery evidence is not forecast-quality evidence.

## Placement and durable storage

Choose **pi-node-1**, native ARM64, for the initial serving stack. On 2026-10-01
at 12:28 UTC, read-only SSH measured 8,454,602,752 bytes RAM,
4,836,376,576 bytes available, and 879,254,007,808 bytes available on the
application NVMe. Five interval samples had 91–96% CPU idle, 0 swap in/out and
0–2% I/O wait. These are short discovery samples, not peak-load certification.
The host already swaps about 499 MB; do not interpret reclaimable cache as
permission to consume all RAM. Recheck available RAM >= 3 GiB and CPU/PSI/disk
telemetry over a representative day before apply. Stop if sustained swap-in,
OOM, disk free <20%, or application latency breaches the measured budgets.

The N100 Proxmox alternative has only ~3.6 GiB available and ~4.0 GiB swap used;
creating a new guest is unnecessary for this initial placement. **pi-node-2**
is the 4 GiB infrastructure Pi and is excluded from ingestion and training.
Gaming PC/Mac research remains outside serving. Native AMD64 remains required
for portable recovery on an alternate host and is checked by release CI.

Primary paths (homelab catalog must own all of them):

- `/srv/appdata/gridoracle/postgres`: PostgreSQL 16, local NVMe, UID/GID 70.
- `/srv/appdata/gridoracle/artifacts`: complete content-addressed WP03 tree,
  including raw snapshots, datasets, features, models and calibrators.
- `/srv/appdata/gridoracle/bundles`: immutable bundle JSON, pinned by SHA256.
- `/srv/appdata/gridoracle/backups`: temporary coordinated recovery sets;
  **not** the durable backup destination.

Off-primary destination proposal: a dedicated directory
`/mnt/pve/media-hdd/gridoracle-backups` on **pve-node-1**'s physical `/dev/sda1`
HDD, transferred over restricted SSH to a dedicated backup principal. Read-only
measurement found 350,458,204,160 available bytes on that disk. The storage
LXC's existing `/srv/media` and `/srv/photos` exports are application-specific;
never place GridOracle backups inside either or assume their permissions.
Creating the new path, restricted SSH access, quota and service ownership is an
explicit homelab approval/provisioning dependency. No new export was created.
A same-NVMe directory, Docker volume or storage guest rootfs is not an acceptable
substitute. This protects primary-disk loss, not whole-site loss.

Initial hard budget: total recoverable DB + artifact set <=2 GiB; backup quota
40 GiB, with >=15% free on the HDD and no deletion of the last verified set.
Seven daily, four weekly and three monthly complete sets consume <=28 GiB
before overhead at that source limit; allow two scratch sets and alert at
32 GiB. Exceeding source/retention capacity blocks promotion until the owner
reviews a larger destination or deduplicating backup design. Do not silently
prune historical forecasts or shorten retention.

## Immutable release and promotion

`.github/workflows/oci-release.yml` owns tests/build/release. After integration,
run **Immutable OCI release** on `main` with an explicit shared `version`
(`vMAJOR.MINOR.PATCH`, for example `v1.2.3`). Prerelease versions, including
`wp13.x` and `rc.x`, are rejected for publication.
There is no automatic version bump: frontend, API and worker share this version.
The workflow fixes the main source SHA, runs backend/frontend checks, creates an
annotated Git tag for that tested SHA, then builds/publishes all images.
A failed release reserves its tag; fix the failure and choose a fresh version.
Tag pushes do not trigger publication. Each manual main release runs
backend/frontend checks, builds API, worker and frontend on **native**
AMD64 and ARM64 runners, then runs the image-based install/restore drill before
publishing either architecture. The release job assembles multi-platform GHCR
indexes and records exact version@digest pins, source revision, architectures
and workflow run in `release.json`. Version reuse is refused; no `latest` tag
is produced. The GitHub release includes generated changelog notes (merged
changes/contributors and comparison link; commit-list fallback for unmerged
staging ranges), a described image/package table with
all three digest pins, a source link, and the attached receipt. Optional
`notes_start_tag` sets the changelog baseline; when empty the most recent published release is used (drafts and failed tags
are excluded).
Each image has its own OCI description label, and the multi-platform index
repeats it as an annotation for GHCR package pages. Missing index descriptions
fail release verification. Existing immutable images retain their original
metadata; descriptions appear on new versions. The scheduler uses the worker
image with a different command.
Dependencies use `uv.lock` and `bun.lock`; base versions/index digests and
registry architecture evidence are in `evidence/base-images.json`.

Manual invocation after this workflow is merged into the default branch:

```text
gh workflow run oci-release.yml --ref main -f version=v1.2.3
# Optional explicit changelog range:
gh workflow run oci-release.yml --ref main -f version=v1.2.3 -f notes_start_tag=v1.2.2
```

Manual execution from feature branches is rejected. Tag creation uses the
workflow token and continues within the same run; it does not depend on a
second workflow being triggered. PR validation never creates tags,
publishes images or creates releases. The dispatch UI becomes available only
after default-branch integration. No merge is performed by this task.

Promotion is a separate reviewed **homelab PR** changing literal image pins in
`services/gridoracle/docker-compose.yml`, selected bundle hash and provenance
receipt. Homelab never clones/builds GridOracle or trains/promotes models.
There is no updater service. The owner reviews the application release,
architecture reports, staging/restore hashes, capacity, ingress and SOPS slots.
Homelab's existing deploy workflow accepts only merged `main`, plans from its
last applied revision, validates, checks all targets, applies the base policy's
risk gate, verifies health after each host and verifies network exposure.
Service changes are medium; catalog/routing/firewall are high/board according
to the existing policy. Do not change policy or runner hooks for GridOracle.
Do not merge an active service proposal until production apply is authorized:
ordinary medium/high merges can trigger automatic deployment when healthy.

The DevOps agent owns the platform proposal, its branch/validation/PR lifecycle
and any later authorized activation. The GridOracle staging Compose file is a
disposable acceptance fixture, not the production stack. The earlier homelab
draft is historical context only; this task makes no further homelab changes.

### Post-deployment cleanup follow-up

The owner requested removal of rebuild planning and historical migration
information after deployment. Schedule one separately scoped cleanup after the
first stable main release is deployed, its health checks pass, and production
backup/restore and rollback are verified. This is a recorded follow-up, not a
created GitHub ticket or authorization to delete deployed artifacts now.

- Inventory `PLAN.md`, `WORKPLANS.md`, `DECISIONS.md`, `HANDOFF.md`,
  `docs/workplans/**`, historical migration/design notes and temporary staging
  evidence. Extract any still-current product, model, data and operations
  contracts into maintained documentation, then remove the obsolete planning
  and migration narrative from the active tree; Git history retains it.
- Replace the workplan entry-point instructions and README links with the
  maintained development, release and operations documentation. Check links,
  generated-document references and CI paths before removing old files. Retire
  the `wp13` naming and temporary fixtures where appropriate, updating scripts,
  imports and workflow references together.
- Inventory all staging Git tags, GitHub releases and GHCR versions, including
  failed attempts and architecture tags. DevOps must confirm the live homelab
  pins and rollback references. Remove obsolete staging artifacts only after
  checking backup receipts and recovery references; retain the deployed stable
  images and the required rollback versions and provenance.
- Preserve executable database migrations and schema history required for
  upgrade or restore, durable forecast/model lineage, and maintained release,
  migration preflight, backup, restore and rollback runbooks. Historical
  migration notes can be removed once their current requirements are captured.

GridOracle cleanup belongs in a separate reviewed application PR. Homelab
cleanup, promotion and deployment remain DevOps-owned. Validate the final
documentation links, normal CI, fresh installation, schema upgrade and recovery
after the cleanup; do not remove the current workplan coordination records while
their dependent packages still use them.

## DevOps handoff: application inputs and platform ownership

This repository delivers the application-side inputs:

- `evidence/release.json`: historical staging `v0.1.0-wp13.7`, source revision
  and exact multi-platform API/worker/frontend version@digest pins. After
  integration, generate a stable release from main and use its attached receipt
  for the production proposal. DevOps copies those stable pins into its reviewed
  manifest; scheduler uses the worker pin. Do not promote the `wp13.x` images.
- `deploy/wp13/Dockerfile` and `gridoracle/ops/runtime.py`: image users and
  commands `api`, `worker`, `scheduler --season YYYY`; migration is an explicit
  `python -m scripts.wp13_migrate` one-shot, never serving startup.
- `MODEL_BUNDLE.md`: bundle identities/hash closure; runtime expects
  `GRIDORACLE_ARTIFACT_ROOT`, `GRIDORACLE_BUNDLE_FILE` and externally pinned
  `GRIDORACLE_BUNDLE_SHA256`. A real approved bundle is still required.
- `RECOVERY.md` and `scripts/wp13_{migrate,recovery}.py`: quiescence, backup
  receipt preflight, fresh-schema upgrade and new-environment restore/rollback.
- `evidence/released-{amd64,arm64}.json` and `scripts/wp13_drill.py`: reproducible
  released-image staging, offline restart, hash restoration and measured limits.

Production URL files mount read-only as `DATABASE_URL_FILE`; DevOps provisions
separate credentials and grants. Proposed SOPS slots (names only, no values):

| Slot under `hosts/pi-node-1#gridoracle` | Consumer / permission |
| --- | --- |
| `api_database_url` | API reader, SELECT/USAGE only, numeric group10001 |
| `worker_database_url` | Worker/scheduler ledger and authorized append writes, group10001 |
| `migration_database_url` | One-shot migration administrator, group10001 |
| `postgres_password` | PostgreSQL `POSTGRES_PASSWORD_FILE`, group70 |

DevOps owns the actual service manifest, production Compose, secret-slot names
and values, DB grants, durable paths/permissions, backup transfer/retention,
network/firewall/DNS/TLS policy, scrape/alerts and deployment verification.
Placement, ports and ingress below are recommendations to review against its
current catalog and live telemetry. Only frontend serves public assets/API;
its private9090 listener provides `/metrics` and `/ready`. API8000 and DB5432
have no public listener. Jobs remain disabled until their production adapter,
writer mounts and real model bundle are ready.

GridOracle review can proceed on its tested release/recovery contract. DevOps
must independently validate its configuration and obtain owner authorization
for infrastructure activation/public exposure. This task does not message the
DevOps agent, merge its PR, or modify its repository.

## Processes, caps and network boundaries

| Process | User | Memory cap | CPU cap | Responsibility |
| --- | --- | --- | --- | --- |
| frontend | 101:101 | 64 MiB | 0.25 | Static assets and `/api/v1/` GET proxy only |
| API | 10001:10001 | 256 MiB | 0.5 | Read persisted published forecasts; no model inference/training |
| PostgreSQL | 70:70 | 512 MiB | 0.5 | Durable ledger, immutable lineage and publications |
| scheduler | 10001:10001 | 256 MiB | 0.25 | Explicit season calendar reconciliation only |
| worker | 10001:10001 | 768 MiB | 0.75 | Single bounded durable job execution |
| migrate/tools | 10001:10001 | 256 MiB | 0.5 | One-shot explicit operator work |

Steady serving caps total 832 MiB. Serving + jobs total 1,856 MiB, with sequential
maintenance outside that total. The worker image retains the integrated
pipeline's Linux scientific/CUDA dependencies; no GPU device or accelerator is
mounted and no training command is exposed by the runtime entry point.
Image size is an artifact-storage concern, not the worker's measured RSS.
API dependencies exclude the pipeline/scientific/training stack.

All application roots are read-only, with bounded `/tmp` tmpfs, dropped
capabilities, no-new-privileges and PID caps. Docker socket and host filesystem
are never mounted. Artifacts/bundle are read-only to serving; ingestion needs a
separately reviewed writer mount and the same immutable store. DB state is the
only writable serving mount. Production uses separate API-reader, worker and
migration/admin credentials; staging's synthetic DB uses trust authentication on its isolated private
network and is not the production secrets design.

`gridoracle.ops.runtime scheduler --season YYYY` does not claim jobs;
`worker` does not reconcile a calendar. PostgreSQL session advisory locks allow
one process per role. There is no legacy scheduler command, automatic fit,
startup schema mutation or latest-model selector. The integrated WP04 handlers
still visibly block feature/predict/publish without their provenance adapter.
Jobs remain opt-in until that limitation is resolved and tested by integration;
serving/restoring saved publications works independently.

Production networks are `serving` (internal: frontend/API), `database` (internal:
API/DB/tools/worker/scheduler), and a bounded worker egress network only when
jobs are authorized. The frontend edge network is routable; API/DB serving networks have no
outbound route. API has no
published port; PostgreSQL has none. Only frontend backend port 8090 on
pi-node-1 is catalogued for Traefik/health checks and a separate frontend private-operations listener on port 18090
only for Prometheus (host firewall, IPv4/IPv6 and gateway ACL checks required).
The proposal must allocate these in the authoritative catalog before apply;
never rely on Docker port binding alone as access control.

## Ingress, TLS and secrets review

Initial proposed route is **private** `gridoracle.pieterohearn.com`, file-provider,
`auth: sso`, backend 8090; owner confirmation of domain remains required.
Traefik on pi-node-2 terminates TLS through its existing Cloudflare DNS-01
resolver. The current config has `websecure` and `agents`; Quro's old singular
`entrypoint: apps` is not copied. Staging has loopback listeners only and no
Traefik, DNS or wildcard-certificate change. A certificate never authorizes
public traffic. Future fan-facing GET route requires a separate explicit owner
choice of public domain, ingress/tunnel/port forwarding, auth-none reason,
rate-limit policy, IPv6 and external probe evidence. No admin, DB, metrics,
OpenAPI or worker ingress can accompany that route.

Proposed secret slots for DevOps are listed below. Only the owner/deployer
holds age keys. Secret URL/password files are declared in `compose.files`, readable only
by the consuming numeric group (0440, group 10001; DB password group 70), with
private parent directories. Compose's local `uid/gid/mode` fields do not change
bind-source ownership. Mount secrets read-only; do not print them, put them in
image layers, pass passwords as CLI arguments or use shared `.env` files.
API reader gets SELECT/USAGE only; worker gets append/ledger writes; migration
owns DDL; backup principal reads dumps only. Schema/bootstrap and role creation
are maintenance actions reviewed separately from serving startup.

## Public-ingress proposal for owner review (O03)

The existing homelab uses private Pi-hole/Tailscale names and has no public
records or WAN forward for these services. Recommended future public name:
`forecasts.pieterohearn.com`, distinct from the private SSO preview. Proposed
transport is one owner-applied WAN TCP443 forward to pi-node-2 **port8444**,
a new isolated Traefik `gridoracle-public` TLS entry point. Port8443 already
belongs to the agents entry point and must not be reused. Port8444 is not in
the inspected catalog; live conflict and external firewall checks remain
activation gates. Do not forward the shared private `websecure` entry point.

Only the GridOracle Host router attaches to this new entry point, with the
existing DNS-01 certificate resolver, frontend8090 as sole backend, no SSO
for the approved public saved-forecast GETs, and a dedicated rate limit of
20 requests/second with burst40 plus an initial simultaneous-request cap32.
Nginx still proxies only `/api/v1/` reads; admin/DB/metrics/readiness never get
a public backend. Unknown Host/SNI must have no router. No HTTP80 forward is
needed for DNS-01 issuance. Owner must approve the DNS A/forward, forwarding
feasibility (including ISP/CGNAT), unauthenticated-read reason and abuse budget;
if forwarding is unavailable, return for a separately reviewed tunnel design.
Do not add a public AAAA until equivalent IPv6 firewall and external denial
probes pass. Do not change existing private-service DNS or routers.

The activation PR must include the new entry point/Compose listener,
GridOracle-only router, rate-limit/concurrency rules, authoritative catalog
and owner-applied gateway policy. Probe from outside the LAN: the intended
hostname serves saved forecasts over valid TLS; arbitrary private-service
Host/SNI, DB5432, API8000, private ops18090, readiness/admin/metrics and any
unapproved IPv6 path do not expose those services. Verify the private SSO
preview separately. This is a concrete recommendation awaiting owner review,
not public-routing authorization or a tested WAN configuration.

## Package-local answers to open platform questions

| Question | Proposed resolution | Remaining activation gate |
| --- | --- | --- |
| O02 placement/storage | Measured pi-node-1 ARM NVMe; 832 MiB serving /1,856 MiB with jobs caps | Owner placement approval and representative loaded-host headroom |
| O03 public ingress/access | Private SSO preview; future `forecasts.pieterohearn.com` on isolated TLS8444 entry point | Owner public-domain/forward policy and external IPv4/IPv6 probes |
| O04 off-primary retention/owner | Proxmox physical HDD dedicated path, 7 daily/4 weekly/3 monthly, Pieter as restore owner | Restricted principal/quota provisioning and actual off-disk transfer/restore |

These recommendations resolve WP13's design choices without changing shared
DECISIONS or claiming owner adoption. Production release remains gated on the
listed conditions; synthetic staging evidence cannot discharge them.

## Existing observability

Vector already ships Docker/journald logs to VictoriaLogs (90 days /50 GiB).
The production API logs bounded route template, status, service, level and
request duration as JSON; it omits raw URL, query, payload, headers and secrets.
Traefik's JSON log supplies router and trace_id. Traefik already exports request
traces to pi-node-1's collector (errors/slow traces +20% sampling), then
VictoriaTraces (14 days /20 GiB). Nginx passes traceparent to the API; application
DB spans are not yet instrumented, so this design claims **edge traces only**.
Do not assume that setting OTEL environment variables instruments Python.

Private `/metrics` emits bounded route/status counters, duration histograms and
five fixed ledger-state gauges. No season/race/driver/run/model/URL/job IDs or
exception strings become labels. Add Prometheus scrape + service-owner alerts
through the catalog; retain existing 30-day /25 GB storage. Alert on unhealthy
container, API/DB unavailable, blocked/pending work, backup age >26 h, failed
hash verification, free-disk/quota threshold and OOM. Node/cAdvisor metrics and
Traefik route p95/5xx rules supply host and ingress load. Backups/receipts are
retained separately; existing general log retention is not backup coverage.

Operational targets are validation budgets: initial p95 GET <500 ms at 1
concurrent client, no OOM under the declared cap; one worker, one event backfill
at a time, provider rate budget and retry bound from WP04. Never put historical
backfill or training on the HTTP request path. Native CI/local drill reports
identify actual memory/latency and dataset size; tiny synthetic results do not
establish real-data backfill throughput or a loaded-host SLO.

## Sources inspected

Homelab base `a8d2ec2ce67dae968bb896c2dd7fbf9c91683b95`: AGENTS, README,
`.github/workflows/deploy.yml`, risk policy, compose_stack migration task,
physical/guest manifests, Traefik config, Quro service/Compose and env template.
Quro `.github/workflows/release.yml` supplies the release→GHCR pattern; its
MinIO/banking/parser/updater components and mutable tags are excluded.
GridOracle delivery contract PR #106 is merged as `a79766c`; WP11 PR #105 is
merged as `1994c6e`. Registry semantics:
[Docker manifest inspection](https://docs.docker.com/reference/cli/docker/buildx/imagetools/inspect/)
and [GHCR digest pulls](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

## Application review corrections

The owner-requested review and five fixes are recorded in [REVIEW.md](REVIEW.md).
EVALUATE jobs are blocked until the evaluation adapter accepts the declared
bundle; the serving worker never invokes the legacy latest-model selector.
Recovery compares actual live mounts, supports pre-ledger rollback targets and
rejects removed migration ledgers. New v2 lineage inventories stream within
the tools memory budget; v1 reading retains historical hash semantics.
All `wp13.x` releases are historical staging evidence and must not be promoted
to production. The final staging release `v0.1.0-wp13.7`, source
`1942bb859a13e532c7ade24de203a38186705500`,
passed twelve candidate and twelve released-digest checks on both architectures
in [run 36906440683](https://github.com/Pieter-OHearn/grid-oracle/actions/runs/36906440683).
The current receipt/reports are in `evidence/`; prior `.3` and `.4` reports are archived.

Release entry-point/token semantics and presentation were verified against
[GitHub workflow dispatch documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow),
[GitHub CLI generated release notes](https://cli.github.com/manual/gh_release_create)
and [Docker index annotations](https://docs.docker.com/reference/cli/docker/buildx/imagetools/create/).
