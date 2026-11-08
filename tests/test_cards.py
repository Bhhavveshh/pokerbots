import random
import unittest

from pokerbot.cards import card_name, evaluate, parse_card, reference_evaluate


def cards(text):
    return tuple(parse_card(value) for value in text.split())


class EvaluatorTests(unittest.TestCase):
    def test_card_roundtrip(self):
        for card in range(52):
            self.assertEqual(parse_card(card_name(card)), card)
        for invalid in ("", "AAA", "1s", "Ax", 3):
            with self.assertRaises(ValueError):
                parse_card(invalid)

    def test_categories_and_edge_cases(self):
        examples = [
            ("As Kd 9c 6h 3s", 0), ("As Ad 9c 6h 3s", 1),
            ("As Ad 9c 9h 3s", 2), ("As Ad Ac 6h 3s", 3),
            ("As 2d 3c 4h 5s", 4), ("As Js 9s 6s 3s", 5),
            ("As Ad Ac 6h 6s", 6), ("As Ad Ac Ah 3s", 7),
            ("As 2s 3s 4s 5s", 8),
            ("As Ad Ac Kh Kd Kc 2s", 6),
            ("As Ad Kh Kd Qh Qd 2s", 2),
            ("As Ad Ac Ah Ks Kd Kc", 7),
        ]
        for text, category in examples:
            hand = cards(text)
            with self.subTest(text=text):
                self.assertEqual(evaluate(hand) >> 20, category)
                self.assertEqual(evaluate(hand), reference_evaluate(hand))

    def test_random_hands_against_independent_oracle(self):
        rng = random.Random(3451)
        for size in (5, 6, 7):
            for _ in range(750):
                hand = rng.sample(range(52), size)
                self.assertEqual(evaluate(hand), reference_evaluate(hand), hand)

    def test_board_plays_and_kickers(self):
        board = cards("As Ks Qs Js Ts")
        self.assertEqual(evaluate(board + cards("2d 3d")), evaluate(board + cards("Ah Ad")))
        self.assertGreater(evaluate(cards("Ac Ad Ks Qd Jh 4s 2c")),
                           evaluate(cards("Ah As Kd Qc Th 5s 3c")))


if __name__ == "__main__":
    unittest.main()
