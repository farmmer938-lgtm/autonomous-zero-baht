"""H1: a reward is only an opportunity if the money exists, it is net positive, and AF can claim it.

The board that started this said "$10 funded, 2 slots available". The detail said the $10 is a
rebate paid only after you fund $10 of someone else's work, and that 1 of 108 attempts was ever
paid. `evaluate` is what turns that into `loss` instead of a lead.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import af_opportunity_rank as rk  # noqa: E402


def opp(**kw):
    base = {"gross_usd": 10.0, "cost_to_start_usd": 0.0, "reward_kind": "escrow",
            "needs_identity": False, "claimable": True}
    base.update(kw)
    return base


class EvaluateTests(unittest.TestCase):
    def test_an_escrowed_claimable_reward_is_act_now(self):
        verdict, reasons = rk.evaluate(opp())
        self.assertEqual(verdict, "act_now", reasons)

    def test_a_rebate_that_costs_as_much_as_it_pays_is_a_loss(self):
        verdict, reasons = rk.evaluate(opp(gross_usd=10.0, cost_to_start_usd=10.0))
        self.assertEqual(verdict, "loss")
        self.assertIn("leaves 0", reasons[0])

    def test_a_reward_below_its_cost_is_a_loss(self):
        self.assertEqual(rk.evaluate(opp(gross_usd=5, cost_to_start_usd=10))[0], "loss")

    def test_a_credit_reward_is_ignored_not_ranked(self):
        verdict, reasons = rk.evaluate(opp(reward_kind="credit", gross_usd=10000))
        self.assertEqual(verdict, "ignore")
        self.assertIn("not money the rail holds", reasons[0])

    def test_an_advertised_reward_is_ignored(self):
        self.assertEqual(rk.evaluate(opp(reward_kind="advertised"))[0], "ignore")

    def test_an_identity_gate_hands_the_claim_to_the_owner(self):
        verdict, reasons = rk.evaluate(opp(needs_identity=True))
        self.assertEqual(verdict, "needs_owner")
        self.assertIn("identity", reasons[0])

    def test_a_funded_but_unclaimable_reward_is_a_watch_item(self):
        self.assertEqual(rk.evaluate(opp(claimable=False))[0], "watch")

    def test_net_is_stored_on_the_item(self):
        item = opp(gross_usd=15, cost_to_start_usd=2)
        rk.evaluate(item)
        self.assertAlmostEqual(item["net_usd"], 13.0)


class SuccessRateTests(unittest.TestCase):
    def test_one_paid_out_of_many_attempts(self):
        progress = {"paid": 1, "rejected": 9, "expired": 96, "delivered": 2}
        self.assertAlmostEqual(rk.success_rate(progress), 0.009, places=3)

    def test_no_history_is_none_not_zero(self):
        self.assertIsNone(rk.success_rate({"capacity": 5, "occupied": 3, "available": 2}))

    def test_non_dict_input_is_none(self):
        self.assertIsNone(rk.success_rate(None))

    def test_all_paid_is_one(self):
        self.assertEqual(rk.success_rate({"paid": 4}), 1.0)


class RankTests(unittest.TestCase):
    def test_act_now_comes_before_loss_and_ignore(self):
        items = [opp(reward_kind="credit"), opp(gross_usd=5, cost_to_start_usd=10),
                 opp(gross_usd=50)]
        for i in items:
            i["verdict"], i["reasons"] = rk.evaluate(i)
        order = [i["verdict"] for i in rk.rank(items)]
        self.assertEqual(order, ["act_now", "loss", "ignore"])

    def test_a_bigger_net_wins_within_a_verdict(self):
        small, big = opp(gross_usd=5), opp(gross_usd=50)
        for i in (small, big):
            i["verdict"], i["reasons"] = rk.evaluate(i)
        self.assertEqual(rk.rank([small, big])[0]["gross_usd"], 50)


if __name__ == "__main__":
    unittest.main()
