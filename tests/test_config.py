"""Tests for bellhop's Config."""

import pickle

from bellhop.config import Config


def test_config_pickle_roundtrip(tmp_path):
    """Config must stay picklable so it can cross the multiprocessing spawn boundary."""
    config = Config(data_dir=tmp_path)
    restored = pickle.loads(pickle.dumps(config))
    assert restored == config
