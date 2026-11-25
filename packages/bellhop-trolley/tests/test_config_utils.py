"""Tests for ContextConfig.

Deliberately self-contained (no dependency on the trolley shims) so this module
can move with ContextConfig if it's extracted into its own library.
"""

import contextvars

import pytest
from pydantic import BaseModel

from bellhop_trolley._config_utils import ContextConfig


class MyConfig(BaseModel):
    name: str = "default"
    retries: int = 3


@pytest.fixture
def config_context() -> ContextConfig[MyConfig]:
    return ContextConfig(MyConfig)


def test_docstring_example(config_context):
    """The example from the _config_utils module docstring, verbatim."""

    def do_something() -> str:
        config = config_context.config()
        return f"Name: {config.name}, Retries: {config.retries}"

    config_context.set(MyConfig(name="custom", retries=5))

    assert do_something() == "Name: custom, Retries: 5"

    with config_context.override(name="temporary"):
        assert do_something() == "Name: temporary, Retries: 5"

    # changes reset outside context manager
    assert do_something() == "Name: custom, Retries: 5"


def test_lazy_default_not_built_at_construction():
    instantiated = []

    class TrackingConfig(MyConfig):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            instantiated.append(self)

    config_context = ContextConfig(TrackingConfig)
    assert instantiated == []
    config = config_context.config()
    assert len(instantiated) == 1
    # Subsequent access reuses the same instance
    assert config_context.config() is config
    assert len(instantiated) == 1


def test_config_returns_default_instance(config_context):
    assert config_context.config() == MyConfig()


def test_set_and_reset(config_context):
    token = config_context.set(MyConfig(name="override"))
    assert config_context.config().name == "override"
    config_context.reset(token)
    assert config_context.config().name == "default"


def test_override_with_kwargs_from_defaults(config_context):
    """With nothing set, override builds the settings from class defaults."""
    with config_context.override(retries=5):
        assert config_context.config().retries == 5
        assert config_context.config().name == "default"
    assert config_context.config().retries == 3


def test_override_merges_with_current_settings(config_context):
    """Fields not named in the override keep their current (non-default) values."""
    config_context.set(MyConfig(name="custom", retries=5))
    with config_context.override(name="temporary"):
        assert config_context.config().name == "temporary"
        assert config_context.config().retries == 5
    assert config_context.config() == MyConfig(name="custom", retries=5)


def test_override_with_settings_instance(config_context):
    settings = MyConfig(name="explicit")
    with config_context.override(settings):
        assert config_context.config() is settings
    assert config_context.config().name == "default"


def test_override_nesting_merges_each_level(config_context):
    with config_context.override(name="outer", retries=10):
        with config_context.override(name="inner"):
            assert config_context.config().name == "inner"
            assert config_context.config().retries == 10  # inherited from outer
        assert config_context.config().name == "outer"
    assert config_context.config() == MyConfig()


def test_override_resets_on_exception(config_context):
    with pytest.raises(RuntimeError), config_context.override(name="boom"):
        raise RuntimeError
    assert config_context.config().name == "default"


def test_context_isolation(config_context):
    """Settings applied via set() in a copied context don't leak to the caller."""
    ctx = contextvars.copy_context()
    ctx.run(config_context.set, MyConfig(name="isolated"))
    assert ctx.run(lambda: config_context.config().name) == "isolated"
    assert config_context.config().name == "default"
