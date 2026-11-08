import random
import time
import unittest
from unittest.mock import patch

from pokerbot.agent import Config, DiscardBot
from pokerbot.cfr import CFR, kuhn_game
from pokerbot.river import bucket_model, public_catalog, solve_river
from tests.test_official import cards


class CFRTests(unittest.TestCase):
    def test_kuhn_value_and_best_response_convergence(self):
        game = kuhn_game()
        solver = CFR(game)
        initial = game.exploitability(solver.current())
        policy = solver.train(10000)
        self.assertAlmostEqual(game.value(policy), -1 / 18, delta=0.002)
        self.assertLess(game.exploitability(policy), 0.01)
        self.assertLess(game.exploitability(policy), initial / 20)
        for rows in policy.values():
            for row in rows:
                self.assertAlmostEqual(sum(row), 1)
                self.assertTrue(all(0 <= p <= 1 for p in row))

    def test_best_response_uses_infosets_not_hidden_opponent_card(self):
        # A showdown-only policy cannot produce a clairvoyant positive value in
        # a symmetric game. BR(uniform) is also independently known for Kuhn.
        game = kuhn_game()
        self.assertAlmostEqual(game.best_response(CFR(game).current(), 0), 0.5)
        self.assertAlmostEqual(game.best_response(CFR(game).current(), 1), 5 / 12)

    def test_public_catalog_excludes_discards_and_board_only(self):
        board, discards = cards("2h 3c 9d Th Kc"), cards("7c Qs")
        hands = public_catalog(board, discards)
        self.assertEqual(len(hands), 128)
        self.assertEqual(len(set(hands)), 128)
        self.assertFalse(any(set(h).intersection(board + discards) for h in hands))
        self.assertEqual(hands, public_catalog(board, tuple(reversed(discards))))

    def test_card_overlap_and_tied_bucket_equity(self):
        hands = [(0, 1), (1, 2), (2, 3), (4, 5)]
        scores = [10, 10, 10, 10]
        joint, equity, boundaries = bucket_model(hands, scores, [1] * 4, [1] * 4)
        self.assertEqual(sum(map(sum, joint)), 8)
        self.assertTrue(all(v == 0.5 for row in equity for v in row))
        self.assertEqual(boundaries, [10])

    def test_public_game_does_not_depend_on_actual_hero_kept_cards(self):
        board = cards("2h 3c 9d Th Kc")
        req = {"pot":20,"min_raise":2,"max_raise":190}
        games = []
        original_train = CFR.train
        def observe(solver, iterations, deadline):
            games.append((solver.game.joint, solver.game.equity))
            return original_train(solver, 4, None)
        for original in (cards("As Ad 7c"), cards("Qh Jh 7c")):
            bot = DiscardBot(config=Config(preflop_table=True))
            bot.new_hand(1, original, False)
            bot.reveal_discard(original[:2], cards("Qs")[0])
            with patch.object(CFR, "train", observe):
                reply = solve_river(bot, req, board, (), time.perf_counter() + 1)
            self.assertIn(reply["action"], ("check", "raise"))
            if reply["action"] == "raise":
                self.assertTrue(2 <= reply["amount"] <= 190)
        self.assertEqual(games[0], games[1])


if __name__ == "__main__":
    unittest.main()
