import random
import unittest

from pokerbot.bots import BaseBot, BOT_TYPES, CallingBot, FoldingBot
from pokerbot.cards import parse_card
from pokerbot.game import Action, Engine, GameConfig
from pokerbot.benchmark import run_match


class ScriptBot(BaseBot):
    def __init__(self, actions):
        super().__init__()
        self.actions = iter(actions)
        self.observations = []

    def act(self, obs):
        self.observations.append(obs)
        item = next(self.actions, None)
        return item(obs) if callable(item) else item or Action("call" if obs.call_cost else "check")


def deck_with(prefix):
    cards = [parse_card(c) for c in prefix.split()]
    return cards + [c for c in range(52) if c not in cards]


class EngineTests(unittest.TestCase):
    def test_blinds_and_fold(self):
        a = ScriptBot([Action("fold")])
        result = Engine().play((a, CallingBot()), list(range(52)))
        self.assertEqual(result.profits, (-1, 1))
        obs = a.observations[0]
        self.assertEqual((obs.pot, obs.call_cost, obs.min_raise_to), (3, 1, 4))
        self.assertFalse(result.showdown)
        self.assertEqual(result.revealed_holes, ())
        self.assertEqual(result.board, ())

    def test_limp_preserves_big_blind_option_and_position(self):
        a, b = ScriptBot([]), ScriptBot([])
        Engine().play((a, b), list(range(52)))
        self.assertEqual(len(a.observations), 4)
        self.assertEqual(len(b.observations), 4)
        self.assertEqual(b.observations[0].legal_actions, ("check", "raise"))
        self.assertEqual(b.observations[1].history[-1].player, 1)
        self.assertEqual(a.observations[1].history[-1].player, 1)

    def test_full_raise_and_short_allin_does_not_reopen(self):
        # 10-chip stacks: raise 2->6 is a full raise; 6->10 also full.
        a = ScriptBot([Action("raise", 7)])
        b = ScriptBot([Action("raise", 10)])
        result = Engine(GameConfig(stack=10)).play((a, b), list(range(52)))
        self.assertNotIn("raise", a.observations[1].legal_actions)
        self.assertEqual(a.observations[1].call_cost, 3)
        self.assertTrue(result.showdown)
        self.assertEqual(sum(result.profits), 0)

    def test_allin_blind_refund(self):
        a, b = ScriptBot([]), ScriptBot([])
        result = Engine(GameConfig(stack=2)).play((a, b), list(range(52)))
        self.assertEqual(len(a.observations), 1)
        self.assertEqual(len(b.observations), 0)
        self.assertTrue(result.showdown)

    def test_tie_and_known_winner(self):
        tie = deck_with("2c 3d 4c 5d As Ks Qs Js Ts")
        result = Engine().play((CallingBot(), CallingBot()), tie)
        self.assertEqual(result.profits, (0, 0))
        win = deck_with("Ac Ad Kc Kd 2s 4h 7c 9d Js")
        result = Engine().play((CallingBot(), CallingBot()), win)
        self.assertEqual(result.profits, (2, -2))

    def test_duplicate_identical_deterministic_bots_cancel(self):
        for bot in ("calling", "folding", "tight", "baseline"):
            report = run_match(bot, bot, 25, 123)
            self.assertEqual(report["profit_chips"], 0)

    def test_randomized_legal_play_and_conservation(self):
        rng = random.Random(837)
        for stack in (2, 3, 7, 20, 200):
            engine = Engine(GameConfig(stack=stack))
            for _ in range(80):
                deck = list(range(52))
                rng.shuffle(deck)
                bots = [BOT_TYPES[rng.choice(list(BOT_TYPES))](rng.randrange(100000)) for _ in range(2)]
                result = engine.play(bots, deck, button=rng.randrange(2))
                self.assertEqual(sum(result.profits), 0)
                self.assertTrue(all(-stack <= p <= stack for p in result.profits))
                self.assertLess(len(result.history), 8 * stack + 8)

    def test_illegal_action_fails_clearly(self):
        bad = ScriptBot([Action("raise", 3)])
        with self.assertRaisesRegex(ValueError, "raise outside"):
            Engine().play((bad, CallingBot()), list(range(52)))


if __name__ == "__main__":
    unittest.main()
