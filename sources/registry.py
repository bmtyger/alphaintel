from __future__ import annotations

import logging
from typing import Dict, List, Type

from .base import BaseSource

logger = logging.getLogger(__name__)


class SourceRegistry:
    def __init__(self) -> None:
        self._sources: Dict[str, BaseSource] = {}

    def register(self, source_cls: Type[BaseSource]) -> None:
        name = source_cls.name
        self._sources[name] = source_cls()
        logger.debug("Registered source: %s (%s)", name, source_cls.category)

    def get(self, name: str) -> BaseSource:
        if name not in self._sources:
            raise KeyError(f"Unknown source: {name}")
        return self._sources[name]

    def all(self) -> List[BaseSource]:
        return list(self._sources.values())

    def by_category(self, category: str) -> List[BaseSource]:
        return [s for s in self._sources.values() if s.category == category]


registry = SourceRegistry()


def autodiscover(module_names: List[str]) -> None:
    import importlib
    for mod_name in module_names:
        try:
            mod = importlib.import_module(mod_name)
            for attr in dir(mod):
                obj = getattr(mod, attr)
                if isinstance(obj, type) and issubclass(obj, BaseSource) and obj is not BaseSource:
                    registry.register(obj)
        except Exception as exc:
            logger.warning("Failed to import source module %s: %s", mod_name, exc)
