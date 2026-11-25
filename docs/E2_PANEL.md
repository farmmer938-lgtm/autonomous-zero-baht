# E2 — ten audits of traded tokens, published with no outreach

Approved by K, 2026-11-25. Window: **30 days from 2026-11-25**, cap **10 tokens**, stop rule below.

## Advisory review — single-agent, labelled

No advisory team exists (Phase N §0). This analysis was written by one agent under six headings;
it is **not** a multi-model council and must never be reported as one.

| role | the one thing it said |
|---|---|
| Strategy | E2 is the only experiment AF can run alone; it has a clock and a cap |
| Market | attention ≠ demand; volume is a proxy, stated on every page |
| Technical | the engine already produces block + reads + sha256; nothing new to build |
| Sales | none — no message is sent to anyone, so no channel is needed |
| Finance | cost 0.00; the output is a citation surface, not revenue |
| Red Team | see "what is wrong with this panel" |

## Selection, exactly as run

`GeckoTerminal /networks/base/trending_pools` → one row per base token (deepest pool) → top 10 by
24h pool volume → dedupe by address → audited with `tools/af_token_review.py` → pages written by
`tools/af_e2_panel.py`.

Panel of 2026-11-25 16:01Z (blocks 62,160,4xx–62,160,5xx): NVDAc · PROS · SOL · SPCXc · ANTc ·
ELSA · AERO (0x3f5bf3ed) · VVV · TTWOc · AERO (0x940181a9).

Ledger with every block, read, flag, sha256 and quoted free-scanner value: `data/e2_panel.json`.
Pages: `site/audit/e2/` (+ index), listed in `site/sitemap.xml` → 24 URLs, all local, all 200-checked
by `tools/af_discoverability.py`.

## What each page states, and what it refuses to state

States: the block, every field read, the bytecode flags, the free scanner's values **quoted not
interpreted**, the sha256 of the report, and a list of what was deliberately not established.

Refuses: "safe", "honeypot-tested", "certified", any price prediction, any rating. A test fails the
build on those claim forms. Every page carries: *"It says nothing about whether you can sell this
token. No swap was simulated and no honeypot test was performed."*

## What is wrong with this panel (Red Team, before K reads the numbers)

1. **9 of 10 verdicts read "no owner() surface found".** That is the truth for these contracts, but
   it makes the pages look alike. The difference is in the flags — mint present vs absent, and one
   contract owner (VVV) — and in supply, holders and taxes. If K finds them indistinct, the panel is
   the problem, not the reader.
2. **Two tokens share the symbol AERO** with different contracts (0x3f5bf3ed vs 0x940181a9). Kept
   apart by address and recorded in the ledger; one of them is almost certainly not the AERO anyone
   means. This is exactly the trap a "10 pages" target creates.
3. **Tokenised equities (NVDAc, SPCXc, ANTc, TTWOc) are issuer-controlled.** A "no owner() surface"
   verdict reads reassuring and is nearly meaningless for them; the control is at the issuer.
   Real limitation, stated here rather than fixed by wording.
4. **Volume-based selection is not discussion-based selection.** My first attempt tried Farcaster
   cashtags and DexScreener search and returned zero candidates; the honest record of that failure is
   in this run's history, not hidden.
5. **Ten pages may produce zero attention.** If `discovered` stays null at day 30, adding an
   eleventh page is the wrong response.

## Stop rule (fixed now, not decided later)

| day 30 check | action |
|---|---|
| ≥1 human enquiry (not a bot, not self-test) | evaluate selling; keep the panel |
| 0 enquiries, `reach`/`discovered` still null | **stop producing pages**; propose market change or shutdown |
| 0 enquiries but discovery evidence exists | keep 10 pages, test copy/price once (E3), then decide |

No page will be added before day 30. That is the promise that makes this an experiment rather than
content farming.

## KPI (same six, no substitutes)

| # | KPI | value |
|---|---|---|
| 1 | humans reached | **null** — no analytics |
| 2 | real enquiries | **0** |
| 3 | real orders | **0** |
| 4 | cash received | **0.00 USDC** |
| 5 | cost | **0.00** |
| 6 | net | **0.00 USDC** |
