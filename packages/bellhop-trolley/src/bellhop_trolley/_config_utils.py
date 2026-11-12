from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Generic, TypeVar

T = TypeVar("T")


class ContextConfig(Generic[T]):
    def __init__(self, settings_class: type[T]):
        self._var: ContextVar[T] = ContextVar(settings_class.__name__, default=settings_class())

    def config(self) -> T:
        return self._var.get()

    def set(self, settings: T) -> Token:
        return self._var.set(settings)

    def reset(self, token: Token) -> None:
        self._var.reset(token)

    def __getattr__(self, name: str):
        return getattr(self._var.get(), name)

    @contextmanager
    def configure(self, settings: T | None = None, **kwargs):
        if settings is None:
            settings = type(self._var.get())(**kwargs)
        token = self._var.set(settings)
        try:
            yield
        finally:
            self._var.reset(token)
