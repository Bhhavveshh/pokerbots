import unittest

from pokerbot.game import Event
from pokerbot.strategy import AdaptiveBot, OpponentModel
from tests.test_strategy import observation


class AdaptationTests(unittest.TestCase):
    def test_priors_and_small_sample_shrinkage(self):
        model = OpponentModel()
        self.assertAlmostEqual(model.fold_rate(1), 0.3)
        model.observe(Event(1, 1, "fold", 0, 0, 20, 10, (0, 1, 2)))
        self.assertLess(model.fold_rate(1), 0.35)
        self.assertEqual(model.fold_rate(0), 0.3)

    def test_only_opponent_actions_are_counted(self):
        bot = AdaptiveBot()
        bot.start_hand(1, 0)
        bot.observe(Event(1, 1, "raise", 10, 10, 20, 0, (0, 1, 2)))
        self.assertEqual(bot.model.decisions, 0)
        bot.observe(Event(0, 1, "call", 0, 10, 30, 10, (0, 1, 2)))
        self.assertEqual(bot.model.decisions, 1)

    def test_callers_and_folders_change_predictions_conservatively(self):
        caller, folder = AdaptiveBot(), AdaptiveBot()
        for _ in range(100):
            caller.model.observe(Event(1, 1, "call", 0, 10, 20, 10, (0, 1, 2)))
            folder.model.observe(Event(1, 1, "fold", 0, 0, 20, 10, (0, 1, 2)))
        self.assertGreater(caller.continuation(0.5, 0.25, 1),
                           folder.continuation(0.5, 0.25, 1))
        self.assertGreater(caller.continuation(0.9, 0.25, 1),
                           caller.continuation(0.2, 0.25, 1))

    def test_exhausted_budget_uses_legal_fallback(self):
        bot = AdaptiveBot(time_bank=0)
        obs = observation()
        self.assertEqual(bot.act(obs), obs.fallback())
        self.assertEqual(bot.fallbacks, 1)
        self.assertEqual(bot.remaining_seconds, 0)

    def test_allowance_scales_with_remaining_budget(self):
        bot = AdaptiveBot(time_bank=10, expected_hands=1000)
        initial = bot.decision_allowance()
        bot.remaining_seconds = 2
        self.assertLess(bot.decision_allowance(), initial)


if __name__ == "__main__":
    unittest.main()
