# Silvertongue MCP run: one draft in a famous voice

- **The app, its version and the model.** App: the **OpenHands agent harness** (build tag
  `refs/tags/v1.60.1`, commit `e99e5c71ffe4`). MCP client: a small HTTP JSON-RPC client I wrote
  for this run (protocol `2024-11-05`, `Accept: application/json, text/event-stream`). The model:
  the OpenHands-managed LLM served through `https://llm-proxy.app.all-hands.dev`; the harness does
  not expose the model id inside the sandbox, so I do not name one. The server I connected to is
  `silvertongue 0.1.5` at the exact address
  `https://mcp.silvertongue.dev/mcp?ref=frantic-mcp-1&receipt=1`.

- **The voice and what was asked.** Voice: **gordon-ramsay** (`gordon-ramsay@sha256:75d1f9dd…`),
  release `sha256:5649bd8f…`. I asked Silvertongue for a short reply packet and told my model to
  write my reply as Gordon Ramsay. The thing I actually want to send: a reply to a friend saying I
  cannot make Friday. The ask, verbatim: "Use Silvertongue to write my reply as Gordon Ramsay:
  I can't make it Friday."

- **The draft, exactly as written.**
  > Friday? I've cooked soufflés with more structure than that excuse. Give me a proper date, plan
  > it like you mean it, and come with something worth the table. Otherwise, don't bother booking.

- **Score: 8/10.** The lens is right: it finds the standard being missed (a vague "can't make it")
  and hands back the fix (name a real date, plan it), which is the move the packet asks for. It
  loses two points because the food image ("soufflés with more structure") is a fair Ramsay
  register but not one of the studied moves, so it reads slightly invented rather than observed.

- **One finding.** The packet instructions end with a line that must be shown verbatim:
  `Receipt: https://runx.ai/r/<64 hex>`. That receipt is **not stable per server** — it is minted
  **per call**. Two identical `get_voice_packet` calls returned two different 64-hex receipts
  (`c1e8316c…` then `0459c885…`), and each resolves on runx.ai with `venue: silvertongue` and
  `subject: mcp.voice_packet`. So a caller who fetches the packet twice (for example once to read
  it and once to re-read it) will hold two receipts, and only the one they actually cite is the
  proof. Nothing to fix, but worth knowing before you paste the wrong one. I tried: three separate
  `get_voice_packet` calls, compared the hex, and fetched both receipts.

- **One change.** Add a one-line note to the packet's receipt footer — "this receipt is minted per
  call; cite the one from the packet you wrote from" — so an agent that retries a call does not
  cite a receipt that maps to a packet it discarded.
