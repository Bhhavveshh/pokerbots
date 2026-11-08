import random
import unittest

from pokerbot.cards import parse_card
from pokerbot.game import Action, Engine, Observation
from pokerbot.bots import CallingBot
from pokerbot.strategy import ParticleRange, RangeBot, StrategyConfig, made_strength


def cards(text):
    return tuple(parse_card(c) for c in text.split())


def observation(hole="As Ah", board="2c 3d 7s 9h Jc", call=10, maximum=100):
    return Observation(1, 0, 0, cards(hole), cards(board), (100, 100), 30,
                       {0: 0, 3: 1, 4: 2, 5: 3}[len(cards(board))],
                       (0, call), call, 2 * call if call else 2,
                       maximum, 2)


class StrategyTests(unittest.TestCase):
    def test_range_excludes_known_cards(self):
        obs = observation()
        particles = ParticleRange(obs.hole, obs.board, 160, random.Random(5))
        particles.update(obs)
        blocked = set(obs.hole + obs.board)
        for hand in particles.sample(random.Random(1), 100):
            self.assertEqual(len(set(hand)), 2)
            self.assertFalse(blocked.intersection(hand))

    def test_river_nuts_always_have_full_equity(self):
        bot = RangeBot(seed=7)
        obs = observation("As Ks", "Qs Js Ts 2c 3d")
        bot.start_hand(0, 1)
        action = bot.act(obs)
        self.assertEqual(bot.last_equity, 1.0)
        self.assertEqual(action.kind, "raise")
        obs.validate(action)

    def test_board_nuts_always_split(self):
        bot = RangeBot(seed=7)
        obs = observation("2c 3d", "As Ks Qs Js Ts", call=10)
        bot.start_hand(0, 1)
        action = bot.act(obs)
        self.assertEqual(bot.last_equity, 0.5)
        self.assertNotEqual(action.kind, "fold")

    def test_paired_board_is_not_our_strong_pair(self):
        board = cards("Kh Kd 8c 4s 2d")
        self.assertGreater(made_strength(cards("As Kc"), board),
                           made_strength(cards("As Qc"), board))

    def test_budget_still_returns_samples_and_legal_action(self):
        bot = RangeBot(seed=4, config=StrategyConfig(samples=2000, decision_seconds=0))
        obs = observation(board="2c 3d 7s")
        action = bot.act(obs)
        self.assertEqual(bot.last_samples, 16)
        obs.validate(action)

    def test_range_recovers_if_all_particles_are_blocked(self):
        bot = RangeBot(seed=4)
        obs = observation()
        bot.range = ParticleRange(obs.hole, obs.board, 16, bot.rng)
        bot.range.hands = [obs.hole] * 16
        bot.range.weights = [1.0] * 16
        action = bot.act(obs)
        obs.validate(action)
        self.assertGreater(sum(bot.range.weights), 0)

    def test_invalid_sampling_configuration(self):
        for kwargs in ({"samples": 0}, {"particles": 0}, {"decision_seconds": float("nan")}):
            with self.assertRaises(ValueError):
                StrategyConfig(**kwargs)

    def test_wheel_draw_feature_is_included(self):
        # A-2-3-4 is a real wheel draw. The unused high suits do not make a flush draw.
        drawn = made_strength(cards("As 2c"), cards("3d 4h 9s"))
        undrawn = made_strength(cards("As 2c"), cards("3d 8h 9s"))
        self.assertGreater(drawn, undrawn)

    def test_legal_full_matches_multiple_stack_depths(self):
        from pokerbot.game import GameConfig
        rng = random.Random(893)
        for stack in (2, 7, 40, 200):
            bot = RangeBot(seed=2)
            for hand_id in range(12):
                deck = list(range(52))
                rng.shuffle(deck)
                result = Engine(GameConfig(stack=stack)).play((bot, CallingBot()), deck, hand_id=hand_id)
                self.assertEqual(sum(result.profits), 0)


if __name__ == "__main__":
    unittest.main()
