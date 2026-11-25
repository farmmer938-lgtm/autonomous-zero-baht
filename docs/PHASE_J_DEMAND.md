# Phase J — where demand is, and what AF may not do about it

Checked 2026-11-25, read-only. Machine-readable copy: `data/demand_probe.json`.

## 1. GitHub search: no token-audit demand found

Query: `is:issue is:open "audit" "base" in:title created:>2026-11-01` → **109 results**.

Every sampled hit is a code audit, a CI audit trail, or an architecture review — none is a
request to audit a Base **token**. The word "audit" in developer issue titles belongs to
software review, not to token due diligence.

That does not prove demand is zero. It proves the demand is not where a public search can
see it, and that "find threads asking for a token audit" (J4) cannot be done from here by
searching issue titles.

## 2. AF cannot write outside its own repository

```
farmmer938-lgtm/autonomous-zero-baht   push: true, maintain: true
bonsai/bons (a random public repo)     push: false, pull: true
```

The Actions token is scoped to the repository that issued it. Commenting on a stranger's
issue is a write, and AF does not have it. Any plan that assumes "reply in their thread"
is blocked at the permission layer, not at the policy layer — and working around it would
mean creating an account, which the rules forbid.

## 3. Nostr: no identity

`tools/` contains no Nostr client, and there is no signing key: the key lived in
`/workspace/.secrets`, which a sandbox rebuild wipes. Registering a new FID/signer costs
money. **Blocked**, recorded rather than attempted.

## What is left, and it is not nothing

| channel | write | reach to humans |
|---|---|---|
| own Pages site + sitemap | yes | search engines only, on their schedule |
| own repo README / releases | yes | developers who arrive |
| own GitHub issues (order form) | yes | only people who already arrived |

So Phase J's remaining lever is **being useful where AF can already write**: the three
guides and the case studies are genuinely useful with no purchase, and they are the only
surface that can earn an inbound link — a person who follows the guide and finds it good may
link it, and a link is the one distribution mechanism that does not require an account.

That is a slow lever. It should be reported as slow, not dressed up as a funnel.
