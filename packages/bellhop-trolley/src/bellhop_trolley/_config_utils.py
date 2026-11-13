"""Context wrapper util for managing library config

Example usage:

## Define configuration class and create context wrapper
```python
# my_lib/config.py

class MyConfig(BaseSettings):
    name: str = "default"
    retries: int = 3

config_context = ContextConfig(MyConfig)
```

## Library functions access config from context
```python
# my_lib/do_something.py
from my_lib.config import config_context

def do_something():
    config = config_context.config()
    print(f"Name: {config.name}, Retries: {config.retries}")
```

# User code can set and override the configuration for the library using the context wrapper
```python
# Usage
from my_lib import MyConfig, config_context, do_something

config_context.set(MyConfig(name="custom", retries=5))

do_something() # prints Name: custom, Retries: 5

# Temporarily override configuration within a context block
with config_context.override(name="temporary"):
    do_something() # prints Name: temporary, Retries: 5

# changes reset outside the with statement.
do_something() # prints Name: custom, Retries: 5
```
"""

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ContextConfig(Generic[T]):
    def __init__(self, settings_class: type[T]):
        self._settings_class = settings_class
        # Don't build settings class until it's first accessed to avoid side effects.
        self._var: ContextVar[T | None] = ContextVar(settings_class.__name__, default=None)

    def config(self) -> T:
        value = self._var.get()
        if value is None:
            value = self._settings_class()
            self._var.set(value)
        return value

    def set(self, settings: T) -> Token:
        return self._var.set(settings)

    def reset(self, token: Token) -> None:
        self._var.reset(token)

    @contextmanager
    def override(self, settings: T | None = None, **kwargs):
        """Temporarily override the current configuration."""
        if settings is None:
            current = self._var.get()
            if current is not None:
                settings = self._settings_class(**(current.model_dump() | kwargs))
            else:
                settings = self._settings_class(**kwargs)
        token = self._var.set(settings)
        try:
            yield
        finally:
            self._var.reset(token)


# TODO: Add generic `configure` func/contextmanager so users can
#   set and override library config without having to access the ContextConfig instance directly.
#   Also maybe the config_context should be a private library variable.
