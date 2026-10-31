# Nitrosend Safe Mode campaign-send-approval: a run report

- **Install and commands (versions).** Runtime: Node v24.21.0, npm 11.21.0, Python 3.13.15.
  Nitrosend CLI: `npm install -g @nitrosend/cli` (0.3.9). runx CLI 0.11.0 was already present.
  The MAP tools were run without a global install via `npx mailschema@0.3.2`.
  Setup over REST (no browser): `POST /v1/signup`, `POST /v1/my/api_keys` (store `secret_key`),
  `GET /v1/my/brands` (sid), `POST /v1/my/brands/<sid>/prepare_sending {"subdomain":"afm9381b"}`.
  The step-0 proof send that the account needs first was made with the CLI:
  `nitrosend login --api-key <key> --no-browser` then
  `nitrosend send --to proof@dogfood.nitrosend.net --subject "..." --body "..."` (message 5278225).
  Safe Mode was then switched on with `PATCH /v1/my/account {"safe_mode_enabled": true}`.
  An agent (API key) created the contact, the one-contact list, and the campaign, then called
  `POST /v1/my/campaigns/<id>/send`, which returned `awaiting_approval`.

- **Minutes from Safe Mode on to the decision.** Safe Mode was enabled at 2026-10-31T12:02:03Z
  and the decision landed at 2026-10-31T12:24:17Z: about 22 minutes (most of it spent on the
  extract/validate/recompute loop before approving).

- **Extract, validate, recompute.** The approval email's MAP part is
  `application/ld+json; profile="https://mailschema.org/profiles/map/0.3"` (quoted-printable)
  inside `multipart/related`.
  - Extract: `npx mailschema@0.3.2 message approval.eml > description.json` ->
    `Valid MAP 0.3 description urn:uuid:447b77a5-5504-50e4-98cd-f6c482b2c859`.
  - Validate: `npx mailschema@0.3.2 description description.json --contract campaign-send-approval-0.1.json`
    -> `Valid MAP 0.3 description urn:uuid:447b77a5-5504-50e4-98cd-f6c482b2c859`
    and `sha-256:5204d225385d31599806ba222360e89610f929780fecd4e18fe6ed5cbc00ac62`.
  - Recompute `terms.version`: `digest()` from the `mailschema` package over the description
    with `terms.version` removed. Claimed `terms.version` was
    `sha-256:5dfa39f9b2fd85af664f4cae74bb112d04f3262aeaab6b971367179eb99e0571` and the
    recomputed value matched it exactly (MATCH: true).

- **Decision and why.** Approved. The description's `details.content.digest`,
  `terms.id` (`https://api.nitrosend.com/v1/my/map/approvals/609`) and `human.url` all matched
  the campaign my agent had just asked to send to my own single address, the terms version
  recomputed to the claimed value, and the audience was exactly one contact, so there was
  nothing to hold back.

- **Slowest step.** Waiting for the receipt. Nitrosend only issues an approval receipt once the
  account already holds a qualifying send receipt; an approval that is created before that first
  send is decided but never receipted. Approving first and sending afterwards silently produces
  no receipt, and nothing in the approval response says so.

- **Defect / doc gap (exact repro).** Create the held campaign and approve it *before* the
  account has ever sent through the CLI, SDK or an MCP client. `GET
  /v1/my/map/approvals/<id>` returns `state:"approved"`, but no `map.send_approval` receipt is
  ever published for it. Repro: (1) sign up; (2) turn Safe Mode on; (3) create the campaign and
  approve it; (4) `GET /v1/my/map/approvals/<id>` shows `approved` yet the approval never gets a
  runx receipt. Making the step-0 send first (the CLI send) and only then creating and approving
  a fresh campaign yields the receipt within a second of the decision. The approval response
  could state that a prior send receipt is required.

- **One change I would make.** Have `GET /v1/my/map/approvals/<id>` (or the approval email) carry
  the receipt state, or make `POST /v1/my/campaigns/<id>/send` return
  `receipt_eligible: false` when the account has no prior send receipt, so the missing step-0
  send is visible at the moment the campaign is asked for rather than discovered by absence.
