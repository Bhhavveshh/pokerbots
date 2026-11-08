"""Vanilla CFR for a finite, two-player, zero-sum one-bet river abstraction.

Both players see only their own strength bucket. Chance is a joint distribution,
so card removal and correlated ranges are supported. This solves the restricted
game only: actual no-limit raises and within-bucket distinctions are omitted.
"""

import time


class OneBetGame:
    def __init__(self, joint, equity, pot=2.0, bet=1.0, opponent_after_check=True):
        self.size = len(joint)
        if not self.size or any(len(row) != self.size for row in joint + equity):
            raise ValueError("square chance/equity matrices required")
        mass = sum(map(sum, joint))
        if mass <= 0 or pot <= 0 or bet <= 0:
            raise ValueError("positive chance mass, pot and bet required")
        self.joint = [[v / mass for v in row] for row in joint]
        self.equity, self.pot, self.bet = equity, pot, bet
        self.nodes = {"": (0, ("k", "b")), "b": (1, ("f", "c"))}
        if opponent_after_check:
            self.nodes.update({"k": (1, ("k", "b")), "kb": (0, ("f", "c"))})

    def utility(self, history, i, j):
        if history.endswith("f"):
            return self.pot / 2 if history == "bf" else -self.pot / 2
        extra = self.bet if history.endswith("c") else 0
        return (2 * self.equity[i][j] - 1) * (self.pot / 2 + extra)

    def value(self, policy):
        n = self.size
        def visit(history):
            if history not in self.nodes:
                return [[self.utility(history, i, j) for j in range(n)] for i in range(n)]
            actor, actions = self.nodes[history]
            children = [visit(history + action) for action in actions]
            return [[sum(policy[history][i if actor == 0 else j][a] * children[a][i][j]
                         for a in range(2)) for j in range(n)] for i in range(n)]
        values = visit("")
        return sum(self.joint[i][j] * values[i][j] for i in range(n) for j in range(n))

    def best_response(self, policy, player):
        """Maximize per information set, AFTER averaging unknown opponent types."""
        n = self.size
        def visit(history, other_reach):
            if history not in self.nodes:
                if player == 0:
                    return [sum(self.joint[i][j] * other_reach[j] * self.utility(history, i, j)
                                for j in range(n)) for i in range(n)]
                return [sum(self.joint[i][j] * other_reach[i] * -self.utility(history, i, j)
                            for i in range(n)) for j in range(n)]
            actor, actions = self.nodes[history]
            if actor == player:
                children = [visit(history + a, other_reach) for a in actions]
                return [max(child[b] for child in children) for b in range(n)]
            children = [visit(history + action,
                              [other_reach[b] * policy[history][b][a] for b in range(n)])
                        for a, action in enumerate(actions)]
            return [sum(child[b] for child in children) for b in range(n)]
        return sum(visit("", [1.0] * n))

    def exploitability(self, policy):
        return (self.best_response(policy, 0) + self.best_response(policy, 1)) / 2


class CFR:
    def __init__(self, game):
        self.game = game
        self.regrets = {h: [[0.0, 0.0] for _ in range(game.size)] for h in game.nodes}
        self.sums = {h: [[0.0, 0.0] for _ in range(game.size)] for h in game.nodes}
        self.iterations = 0

    def current(self):
        result = {}
        for history, regrets in self.regrets.items():
            result[history] = []
            for row in regrets:
                positive = [max(0, v) for v in row]
                total = sum(positive)
                result[history].append([v / total for v in positive] if total else [0.5, 0.5])
        return result

    def average(self):
        return {h: [[v / sum(row) for v in row] if sum(row) else [0.5, 0.5]
                    for row in rows] for h, rows in self.sums.items()}

    def train(self, iterations=200, deadline=None):
        game, n = self.game, self.game.size
        def visit(history, reaches, policy):
            if history not in game.nodes:
                return [[game.utility(history, i, j) for j in range(n)] for i in range(n)]
            actor, actions = game.nodes[history]
            strategy = policy[history]
            children = []
            for a, action in enumerate(actions):
                next_reaches = list(reaches)
                next_reaches[actor] = [reaches[actor][b] * strategy[b][a] for b in range(n)]
                children.append(visit(history + action, next_reaches, policy))
            values = [[sum(strategy[i if actor == 0 else j][a] * children[a][i][j]
                           for a in range(2)) for j in range(n)] for i in range(n)]
            for b in range(n):
                for a in range(2):
                    if actor == 0:
                        regret = sum(game.joint[b][j] * reaches[1][j] *
                                     (children[a][b][j] - values[b][j]) for j in range(n))
                    else:
                        regret = sum(game.joint[i][b] * reaches[0][i] *
                                     (values[i][b] - children[a][i][b]) for i in range(n))
                    self.regrets[history][b][a] += regret
                    self.sums[history][b][a] += reaches[actor][b] * strategy[b][a]
            return values
        for _ in range(iterations):
            if deadline is not None and self.iterations >= 2 and time.perf_counter() >= deadline:
                break
            visit("", [[1.0] * n, [1.0] * n], self.current())
            self.iterations += 1
        return self.average()


def kuhn_game():
    joint = [[0 if i == j else 1 / 6 for j in range(3)] for i in range(3)]
    equity = [[1 if i > j else 0.5 if i == j else 0 for j in range(3)] for i in range(3)]
    return OneBetGame(joint, equity)
