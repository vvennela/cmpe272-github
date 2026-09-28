# Jenkins push builds

This local development installation creates a Freestyle job named **jenkinsJob**.
Push notifications cause Jenkins to check `main` for new commits. Pushes to other
branches do not build this job. The current repository has only a README, so the
build validates that README is nonempty and produces a source archive plus the
built commit ID. Replace the job's shell build step when application code exists.

## Start

Requirements: Docker with Compose and OpenSSL. The optional registration script
also uses Python 3 and GitHub CLI.

```sh
bash jenkins/setup.sh
```

Open http://localhost:8080/job/jenkinsJob/. Sign in as `admin` using the password
in `.secrets/admin-password` (`cat .secrets/admin-password` locally).
The credentials are generated once and excluded from Git. Keep `.secrets` private.
The Jenkins named volume preserves settings and build history across restarts.
This development setup runs the source-packaging build on one controller executor.
Use isolated agents before adding untrusted or production build workloads.

Click **Build Now** once to establish the initial Git checkout and confirm the build.
Each successful build archives `dist/cmpe272-github.tar.gz` and `dist/commit.txt`.

## Register the webhook

Without GitHub CLI, open the repository's **Settings → Webhooks → Add webhook**:

- Payload URL: the HTTPS URL from `docker compose logs tunnel`, followed by `/github-webhook/`.
- Content type: `application/json`.
- Secret: the contents of `.secrets/webhook-secret`.
- SSL verification: enabled.
- Events: **Just the push event**.
- Active: checked.

Click **Add webhook** and confirm the ping succeeds. Update the payload URL if
the tunnel restarts with a different address. Git itself does not manage GitHub webhooks.

Alternatively, use the optional script:

```sh
gh auth login --hostname github.com --web
python3 jenkins/register-webhook.py
```

Your GitHub account must administer `vvennela/cmpe272-github` and have permission
to manage its repository webhooks. If your token lacks the needed scope, run
`gh auth refresh --hostname github.com --scopes admin:repo_hook`.

The registration script uses the tunnel's current HTTPS URL and creates a webhook
for `push` events with JSON content and TLS verification. Jenkins validates its
signature with the matching secret stored in `.secrets/webhook-secret`.
Jenkins automatic hook management is not enabled; this script manages the hook.
It remembers its hook ID locally and updates that hook when the tunnel URL changes.

The Cloudflare Quick Tunnel is temporary: its URL can change when the tunnel
restarts. Rerun the registration script after a URL change. This Mac must be awake
and Docker running for delivery and builds. Quick Tunnels are for development;
for a permanent setup use a stable HTTPS endpoint and pass its base URL:

```sh
python3 jenkins/register-webhook.py https://your-webhook-host.example
```

The public proxy exposes only POST `/github-webhook/`; the Jenkins dashboard
remains accessible at localhost. The tunnel carries webhook payloads via Cloudflare.

## Verify

1. In GitHub Settings → Webhooks, check that the ping delivery succeeded.
2. Push a new commit to `main`.
3. Confirm a new `jenkinsJob` build succeeds and its archived `commit.txt` matches.
   Replaying a push without new commits does not create another build.

```sh
docker compose ps
docker compose logs --tail=100 jenkins
docker compose logs tunnel
docker compose stop
```

To restart, use `docker compose up -d` and update the webhook if its URL changed.
Do not delete the Jenkins volume or `.secrets` if you want to preserve this setup.

References:
- https://docs.cloudbees.com/docs/cloudbees-ci-kb/latest/client-and-managed-controllers/github-webhook-configuration
- https://docs.cloudbees.com/docs/cloudbees-ci-kb/latest/client-and-managed-controllers/github-webhook-non-multibranch-jobs
- https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/
