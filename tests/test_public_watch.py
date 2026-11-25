import unittest

from engine.public_watch import paid_only, render_dashboard


def report(surfaces, radar=None, down=None, degraded=None):
    return {"checked_at": "2026-11-25T00:00:00+00:00",
            "healthy": not down, "down": down or [], "degraded": degraded or [],
            "surfaces": surfaces, "radar": radar or []}


def surface(url="https://example.test", ok=True, tier="critical"):
    return {"url": url, "http": 200 if ok else 404, "ok": ok, "tier": tier}


class DashboardEscapingTests(unittest.TestCase):
    def test_bounty_title_cannot_inject_markup(self):
        page = render_dashboard(report(
            {"storefront": surface(), "catalog": surface(), "research_site": surface(),
             "cashier": surface(), "opentask": surface()},
            radar=[{"rail": "ns", "title": "<script>alert(1)</script>",
                    "reward_usd": 5, "url": "https://example.test"}]))
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_unpriced_reward_is_not_rendered_as_zero(self):
        page = render_dashboard(report(
            {"storefront": surface(), "catalog": surface(), "research_site": surface(),
             "cashier": surface(), "opentask": surface()},
            radar=[{"rail": "nonsynthetic", "title": "2 RTC bounty", "reward_usd": 0,
                    "url": "https://nonsynthetic.net/"}]))
        self.assertIn("<b>unpriced</b>", page)
        self.assertNotIn("<b>$0</b>", page)

    def test_priced_reward_keeps_its_dollars(self):
        page = render_dashboard(report(
            {"storefront": surface(), "catalog": surface(), "research_site": surface(),
             "cashier": surface(), "opentask": surface()},
            radar=[{"rail": "frantic", "title": "paid", "reward_usd": 12.5,
                    "url": "https://example.test"}]))
        self.assertIn("<b>$12.5</b>", page)

    def test_javascript_url_is_dropped(self):
        page = render_dashboard(report(
            {"storefront": surface("javascript:alert(1)"), "catalog": surface(),
             "research_site": surface(), "cashier": surface(), "opentask": surface()}))
        self.assertNotIn('href="javascript:', page)
        self.assertIn('href="#"', page)

    def test_funded_titles_are_escaped(self):
        s = surface()
        s["funded_titles"] = ['<img src=x onerror=alert(1)>']
        page = render_dashboard(report({"storefront": surface(), "catalog": surface(),
                                        "research_site": surface(), "cashier": surface(),
                                        "opentask": s}))
        self.assertNotIn("<img src=x", page)
        self.assertIn("&lt;img", page)


class DashboardHeadlineTests(unittest.TestCase):
    def surfaces(self, cashier_ok=True):
        return {"storefront": surface(), "catalog": surface(), "research_site": surface(),
                "cashier": surface(ok=cashier_ok, tier="info"), "opentask": surface(tier="info")}

    def test_all_up_only_when_every_surface_answers(self):
        self.assertIn("ALL SYSTEMS UP", render_dashboard(report(self.surfaces())))

    def test_dead_cashier_is_not_reported_as_all_up(self):
        page = render_dashboard(report(self.surfaces(cashier_ok=False),
                                       degraded=["cashier"]))
        self.assertNotIn("ALL SYSTEMS UP", page)
        self.assertIn("DEGRADED", page)
        self.assertIn("cashier", page)

    def test_critical_outage_outranks_degraded(self):
        page = render_dashboard(report(self.surfaces(cashier_ok=False), down=["research_site"],
                                       degraded=["cashier"]))
        self.assertIn("DOWN: research_site", page)
        self.assertNotIn("ALL SYSTEMS UP", page)


class PaidOnlyTests(unittest.TestCase):
    def test_zero_reward_listings_are_not_called_paid(self):
        items = [{"reward_usd": 0}, {"reward_usd": "0"}, {"reward_usd": 12},
                 {"reward_usd": None}, {"reward_usd": "abc"}]
        self.assertEqual(paid_only(items), [{"reward_usd": 12}])


if __name__ == "__main__":
    unittest.main()
