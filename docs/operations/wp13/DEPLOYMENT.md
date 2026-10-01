# WP13 deployment and recovery design

WP13 implements application packaging and disposable acceptance tools. The
runtime stack and service catalog belong to **homelab**, with a separate
proposal PR. No host provisioning, SOPS change, DNS change, production apply or
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

`.github/workflows/oci-release.yml` owns tests/build/release. Each version tag
runs backend/frontend checks, builds API, worker and frontend on **native**
AMD64 and ARM64 runners, then runs the image-based install/restore drill before
publishing either architecture. The release job assembles multi-platform GHCR
indexes and records exact version@digest pins, source revision, architectures
and workflow run in `release.json`. Version reuse is refused; no `latest` tag
is produced. The scheduler uses the worker image with a different command.
Dependencies use `uv.lock` and `bun.lock`; base versions/index digests and
registry architecture evidence are in `evidence/base-images.json`.

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

The proposal is kept under `homelab/docs/proposals/gridoracle/` until those
activation conditions hold. It is concrete source for a later service PR,
not a generated wiki file or an already provisioned runtime stack.

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

SOPS slots are named in the homelab proposal. Only the owner/deployer holds age
keys. Secret URL/password files are declared in `compose.files`, readable only
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
