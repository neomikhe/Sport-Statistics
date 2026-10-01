import numpy as np


def expected_value(prob, odds):
    return float(prob) * float(odds) - 1.0


def ev_array(probs, odds):
    return np.asarray(probs, dtype=float) * np.asarray(odds, dtype=float) - 1.0


def implied_from_odds(odds):
    return 1.0 / float(odds)


def edge(prob_model, odds):
    return float(prob_model) - 1.0 / float(odds)
