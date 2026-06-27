"""Language registry for the multi-language Unbound build pipeline.

Every supported target language is declared by a `languages/<code>/lang.yaml`
descriptor. This package loads and validates those descriptors so the Makefile,
the generic build driver and the test-suite all agree on a single source of
truth for "which languages exist and how each is built".
"""

from .registry import (
    LanguageConfig,
    LanguageRegistry,
    RegistryError,
    load_registry,
)

__all__ = [
    "LanguageConfig",
    "LanguageRegistry",
    "RegistryError",
    "load_registry",
]
