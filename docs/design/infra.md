# Infra

## Object storage

Audio files are stored in an S3-compatible object store rather than on local
disk or in memory. For local development and this take-home, that store is
[MinIO](https://min.io/), run as a container alongside the API via Docker
Compose. Because MinIO implements the S3 API, the same client code
(`boto3` or the `minio` SDK) will work unmodified against real AWS S3 later —
switching environments is a matter of changing endpoint/credentials, not
application code.

Current scope:

- One bucket holds all uploaded WAV files.
- The API server is the only client of the bucket.
- Storage runs locally via Compose; no multi-region or replication concerns
  yet.

Future scope (cloud S3):

- Swap the MinIO endpoint for an AWS S3 endpoint (or drop the endpoint
  override entirely and rely on the SDK's default AWS resolution).
- Bucket lifecycle policies, versioning, and encryption-at-rest become
  relevant and should be defined in infra-as-code (Terraform/CloudFormation),
  not application code.

## Bucket creation: lifespan vs. init container

Decision: create the bucket (if it does not already exist) from the FastAPI
app's `lifespan` startup hook, using an idempotent "create if missing" call.

Considered alternative: a one-shot init container/service in Compose (e.g.
`mc mb ...`) that provisions the bucket before the API starts, using
`depends_on: condition: service_completed_successfully`.

Rationale:

- At this scale (single API instance, single bucket, local MinIO), the
  init-container pattern adds a second Compose service and an extra
  dependency chain for something that is a two-line idempotent check in
  `lifespan`.
- The lifespan approach keeps environment setup to a single `docker compose
  up` with no separate provisioning step to reason about.

Tradeoff to revisit before production:

- Giving the app's runtime credentials `CreateBucket` permission is
  acceptable against local MinIO, but is generally undesirable against real
  AWS S3. Bucket provisioning there is normally an infra-as-code concern,
  done once and out-of-band from app deploys, with the app's IAM role scoped
  down to just `GetObject`/`PutObject`/`ListBucket` on a specific
  pre-existing bucket.
- When moving to cloud S3, bucket creation should move out of `lifespan` and
  into Terraform/CloudFormation, and the app's startup check can be relaxed
  to a read-only existence check (or removed, trusting the bucket exists).

## Concurrency and scale (not yet addressed)

Not yet designed; revisit if/when this grows beyond a single API instance.
Candidates to consider later: multiple API replicas behind a load balancer,
streaming uploads directly to S3 instead of buffering in the request handler,
and moving duration/metadata extraction to an async worker if it becomes a
bottleneck.

## Data integrity (not yet addressed)

Not yet designed. Candidates to consider later: validating uploaded bytes are
a real WAV (RIFF header check) before accepting/storing, computing a checksum
on upload for later integrity verification, and deriving metadata (duration,
sample rate, etc.) from the decoded audio rather than trusting client-supplied
values.
