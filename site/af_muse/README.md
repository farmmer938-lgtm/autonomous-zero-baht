# AF_MUSE

A creative library for AF agents: 83 finished pieces in seven forms, each held to the rules
of its own craft by a script, each signed so a consumer can tell it has not been edited.

**Built:** 2026-11-21 · **Version:** 2 · **License:** CC0-1.0 · **Author:** OpenHands (AF agent)

```
aphorism   24     คำคมปรัชญา   two clauses, under 42 characters
caption    18     แคปชั่น      under 180 characters, hashtags
haiku      16     ไฮกุ          5 / 7 / 5 syllables
klon8      10     กลอนแปด      L1end~L2w3, L2end~L3end, L3end~L4w3 + tone rules
song        6     เนื้อเพลง    verse/chorus, chorus must repeat verbatim
essay       5     บทความ       thesis + 3 or more paragraphs
scene       4     บทภาพยนตร์   plan-first, every beat must appear in the text
```

## How an agent uses it

```bash
python3 tools/af_muse_query.py --list                       # forms and counts
python3 tools/af_muse_query.py --form klon8 --text          # read poems
python3 tools/af_muse_query.py --tag ความจำ                  # filter by theme
python3 tools/af_muse_query.py --random --n 5 --text        # pull a varied five
python3 tools/af_muse_query.py --get song-01 --text         # one exact piece
python3 tools/af_muse_query.py --search ตะปู --text           # find by content
python3 tools/af_muse_query.py --export /tmp/pick.json --form aphorism
```

Output is JSON by default so it pipes into `jq` or another program. `--text` prints the piece
as readable prose or verse.

From Python:

```python
import sys; sys.path.insert(0, "tools")
from af_muse_query import load_all, render

items, rejected = load_all()          # rejected lists anything that failed its checks
poems = [i for i in items if i["form"] == "klon8"]
print(render(poems[0]))
```

`load_all` re-verifies every item on the read path. A piece whose text was altered after
signing, or that no longer satisfies its form rules, comes back in `rejected` and is withheld.
An agent therefore never publishes something the library itself would not stand behind.

## What was learned before building, and how it changed the build

The instruction was to study what skilled creators do and build from that. Four findings
actually changed the code; the rest of the reading did not.

**1. Language models lose coherence over long text; the fix is to plan first.**
*Co-Writing Screenplays and Theatre Scripts with Language Models* (2023, 521 citations,
doi:10.1145/3544548.3581225) reports that models "lack long-range semantic coherence" and
solves it with hierarchical generation — structure first, dialogue second.

This is why `scene` items carry an explicit `plan` field: logline, characters with wants, and
numbered beats. The scene text is then written inside that plan, and `check_scene` fails the
piece if any beat is missing from the text or if a speaker is not in the cast. Structure is
not decoration here; it is what the text is tested against.

**2. Experts revise; novices mostly do not.**
*Cognitive Processes While Writing Poetry* (2019, 41 citations, doi:10.1080/07370008.2019.1570931)
finds revision is what separates expert from novice writing.

So building and checking are separate commands, and the check is run. The first build of this
library failed 31 of 83 pieces. Those failures are recorded below rather than quietly fixed
before anyone looked.

**3. A saying survives on brevity, rhythm and reuse.**
*What makes a good proverb?* (2022, 31 citations, doi:10.4000/lexis.6383) analyses
proverbialisation through meme fitness and selection criteria.

So the aphorism cap is 42 characters and the two-clause shape is required. This is a hard
limit, not a style note: a 55-character "aphorism" is a sentence, and a sentence is not a
proverb. Fifteen pieces were over the cap on first build and were cut, not padded.

**4. กลอนแปด has specific rules that are easy to get wrong.**
From th.wikipedia.org/wiki/กลอนสุภาพ: line 1's ending rhymes word 3 of line 2; line 2's
ending rhymes line 3's ending; line 3's ending rhymes word 3 of line 4. Line endings also
have tone constraints.

An earlier attempt at this used an invented scheme (all odd lines rhyming each other) and
reported a pass. That was wrong, and the correction is in `artifacts/creative/`.

## Verification

```bash
python3 tools/af_muse_build.py --check
```

```
checked 83 pieces
  signature: 83/83 intact
  form:      83/83 pass
```

Each item carries `signature.digest`, a SHA-256 over its own body (everything except the
signature). `signature.author` states who wrote it; the digest proves the text is unmodified.
These answer different questions and are kept separate so neither is mistaken for the other.

## What the first build got wrong

Recorded because a claim of quality without a failure list is not a claim anyone can check.

| Pieces | What failed | What was done |
|---|---|---|
| 15 aphorisms | over 42 characters (up to 56) | cut a clause from each, not words |
| 11 haiku | wrong syllable counts (4 to 8) | re-segmented at syllable level, not word level |
| 5 klon8 | rhyme not in slot 3, or a filler word on the rhyme | rewrote the failing line |

The haiku failures had a cause worth naming: I had segmented lines into *words*
(`["เวลา"]` = one segment) while the checker counts *syllables*. The checker was right and the
data was wrong. Fixing the data at syllable level (`["เว","ลา"]`) fixed 10 of the 11.

The klon8 filler flags were the opposite case — the checker was wrong. It listed `อยู่`, `ไป`,
`มา`, `เลย` as filler, which flagged four correct poems, including `ยังไม่เปลี่ยนเลย`, a
complete predicate. The filler list was narrowed instead of the poems being changed to suit it.

## Limits — what this library does not establish

- **Form correct is not good.** Every piece here passes its rules. None has been read by a
  human reader, and there is no feedback loop. Metre and rhyme are checkable; whether a poem
  moves anyone is not.
- **Tone checking is partial.** Thai tone cannot be derived from spelling without full
  orthographic analysis (consonant class, vowel length, tone mark, live/dead syllable). Tones
  are supplied from a map, and words absent from the map are simply not tone-checked. The
  klon8 poems use a shared map, so a word missing from it passes silently on tone.
- **Rhyme is approximated** by the final two characters, not by sound. Thai rhyme is judged
  on sound, and two words can look alike and not rhyme, or vice versa.
- **The scene plans are mine, not a screenwriter's.** The hierarchical method is evidence-based;
  the loglines are not.
- **83 pieces is not "a lot" in absolute terms.** It is what passed the checks in this session.

## Files

```
artifacts/af_muse/
  index.json        collection metadata, counts, craft basis, usage pointer
  klon8.json        each form's items, signed
  haiku.json
  aphorism.json
  caption.json
  song.json
  scene.json
  essay.json

tools/
  af_muse_build.py    build and verify; the checkers live here
  af_muse_content.py  the content, kept apart so the builder stays readable
  af_muse_query.py    the read interface agents use
```

---

*Written by OpenHands (AF agent) <openhands@all-hands.dev> for K. Rules sourced from the
cited papers and from Thai Wikipedia; failures and limits stated rather than omitted.*
