# NitroMTA 0.2.1 dogfood run — real delivery to proof@nitromta.com

- **Install and exact version.** Downloaded the release archive
  `nitromta-0.2.1-x86_64-linux.tar.gz` from the GitHub release page for
  `nitrosend/nitromta` v0.2.1, extracted it, and ran the binary directly (no
  root): `nitromta --version` → `nitromta 0.2.1`. I did not use brew or the
  container, since neither is available in this Linux container.
- **OS and architecture.** Linux `6.8.0-1055-gke` (Ubuntu-based container),
  `x86_64`, one CPU, unprivileged user. No public IP, no domain, no DNS of my
  own — the same constraints the brief allows.
- **Exact commands and config changes.** In an empty directory:
  `nitromta setup --config config.toml --capture` (wrote `config.toml`, `tls.crt`,
  `tls.key`, `keys`, and a `capture/` directory). I then edited `config.toml`:
  deleted the whole `[capture]` section (including its comment and
  `directory = "./capture"`), and under `[delivery]` uncommented and set
  `port = 2525` and `dane = false`. Started it as my own user:
  `nitromta run --config config.toml`. Generated the DKIM key:
  `openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out dkim.pem`.
  Provisioned the account, the signing identity and an SMTP login over the admin
  socket (`nitromta admin`): `put_account` account 1, `put_identity` account 1
  name `example.test` selector `s1` with the PEM passed as the `private_key`
  field (JSON-encoded with `json.dumps`), then `create_login` user `app`. Also
  ran `nitromta access-key create --account 1` for the SES path. Finally I sent
  one message to `proof@nitromta.com` over SMTP at `127.0.0.1:2587` with
  STARTTLS and that login, `Reply-To` set to my own mailbox, subject
  `nitromta.send`.
- **Minutes from install to receipt.** About one minute end to end: the archive
  finished downloading at 14:39:20 UTC and the proof mailbox emailed the receipt
  at 14:40:03 UTC. Most of that was the 10 MB download; setup, the config edit,
  the DKIM key, provisioning and the send together took under a minute. The
  message shows `nitromta_attempts_total{result="delivered"} 1` on the metrics
  endpoint.
- **Step that slowed me most.** Building the `put_identity` line. The admin
  socket is a raw line-oriented JSON API with no schema in `--help`, and the
  brief says "put_identity (with selector and private_key)" without showing the
  exact field names. I had to read `docs/install.md` to learn that the fields are
  `selector` and `private_key` and that `private_key` takes the whole PEM as a
  JSON string (`key=$(jq -Rs . dkim.pem)`). `nitromta admin` silently accepts
  `put_identity` without a key (`revision` bumps, the identity is created), so a
  typo in a field name is not rejected at that point — I only noticed the
  difference when `nitromta list identities` showed `SIGNS true` and printed the
  DKIM record to publish.
- **One defect or doc gap, with an exact repro.** `docs/capture.md` says the
  operator endpoint serves "health, metrics and the capture inspector on
  `http://127.0.0.1:9090`", but the health path is never named and the obvious
  guess is wrong. Repro on 0.2.1 after `nitromta run`:
  `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9090/health` → `404`,
  while `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9090/metrics`
  → `200`. I could not locate the health endpoint by guessing (`/health`,
  `/healthz`, `/ready`, `/live` all returned 404). Naming the exact health path
  in the docs, or making `/health` the documented path, would fix it.
- **One change I would make.** Add a `nitromta status --config config.toml`
  subcommand that prints, in one place, whether the engine is up, the queue
  depth, the last delivery outcome, and the identities' `SIGNS` state. Today that
  information is split across the `:9090/metrics` text, `nitromta queue` and
  `nitromta list identities`, and during this run I had to call all three to
  confirm the message was signed and delivered.
