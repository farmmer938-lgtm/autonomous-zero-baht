"""Phase E: the opportunity radar must not show one job twice, nor call credit a payment.

Measured on 2026-11-25: 200 open nonsynthetic tasks shared one URL, 61 of them were
reposts of the same job under a new id (`… [v72]`, `… [v73]`), and every one of the 200
carried `pool_funded: false` with `reward_asset: "cr"` while the page could read as "$10000".
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.public_watch import (  # noqa: E402
    canonical_url, dedupe, fingerprint, funded_only, paid_only)


def item(**kw):
    base = {"rail": "nonsynthetic", "id": "ns:1", "title": "job", "reward_usd": 0,
            "url": "https://nonsynthetic.net/", "funded": False, "claimable": True}
    base.update(kw)
    return base


class CanonicalUrlTests(unittest.TestCase):
    def test_a_site_root_identifies_no_job(self):
        self.assertIsNone(canonical_url("https://nonsynthetic.net/"))
        self.assertIsNone(canonical_url("https://nonsynthetic.net"))

    def test_a_deep_link_is_comparable(self):
        self.assertEqual(canonical_url("https://GoFrantic.com/bounties/97/"),
                         "gofrantic.com/bounties/97")

    def test_a_fragment_is_ignored(self):
        self.assertEqual(canonical_url("https://x.dev/a#b"), "x.dev/a")

    def test_empty_input_is_none(self):
        self.assertIsNone(canonical_url(""))


class FingerprintTests(unittest.TestCase):
    def test_a_version_suffix_does_not_make_a_new_job(self):
        self.assertEqual(fingerprint("[jobbi:gh] Read and list [v72]"),
                         fingerprint("[jobbi:gh] read and list [v73]"))

    def test_different_jobs_differ(self):
        self.assertNotEqual(fingerprint("job one"), fingerprint("job two"))

    def test_thai_text_is_kept(self):
        self.assertNotEqual(fingerprint("งานที่หนึ่ง"), fingerprint("งานที่สอง"))


class DedupeTests(unittest.TestCase):
    def test_the_same_id_twice_is_one_row(self):
        rows = dedupe([item(id="ns:a"), item(id="ns:a", title="other")])
        self.assertEqual(len(rows), 1)

    def test_versioned_reposts_collapse_and_count(self):
        rows = dedupe([item(id="ns:a", title="job [v72]"),
                       item(id="ns:b", title="job [v73]"),
                       item(id="ns:c", title="job [v74]")])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["duplicates"], 2)

    def test_a_shared_site_root_does_not_collapse_distinct_jobs(self):
        rows = dedupe([item(id="ns:a", title="alpha"), item(id="ns:b", title="beta")])
        self.assertEqual(len(rows), 2)

    def test_the_same_deep_link_collapses(self):
        rows = dedupe([item(id="ns:a", title="alpha", url="https://x.dev/jobs/1"),
                       item(id="ns:b", title="beta", url="https://x.dev/jobs/1/")])
        self.assertEqual(len(rows), 1)

    def test_funded_and_richer_copies_win(self):
        rows = dedupe([item(id="ns:a", title="job", reward_usd=0, funded=False),
                       item(id="ns:b", title="job", reward_usd=10, funded=True)])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["funded"])
        self.assertEqual(rows[0]["reward_usd"], 10)


class FundingTests(unittest.TestCase):
    def test_only_funded_rows_survive_funded_only(self):
        rows = [item(id="a", funded=True), item(id="b", funded=False)]
        self.assertEqual([r["id"] for r in funded_only(rows)], ["a"])

    def test_a_zero_reward_is_not_paid_work(self):
        self.assertEqual(paid_only([item(reward_usd=0), item(reward_usd=5)]),
                         [item(reward_usd=5)])

    def test_an_alert_needs_both_a_price_and_escrow(self):
        rows = [item(id="a", reward_usd=10, funded=False),
                item(id="b", reward_usd=10, funded=True)]
        self.assertEqual([r["id"] for r in funded_only(paid_only(rows))], ["b"])


if __name__ == "__main__":
    unittest.main()
