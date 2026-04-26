"""v0.1 backwards-compatibility aliases.

In v0.1.0, `from pebbles import Storage` returned the JSON-file concrete
class. In v0.2.0, `Storage` becomes the Protocol type — the headline name
for v0.2-native code, where users will type-hint against the interface
more often than they construct the JSON impl.

For v0.1.0 code that depended on `Storage` being the concrete class,
this module preserves that meaning:

    # Old (v0.1.0):
    from pebbles import Storage
    s = Storage("./pebbles.db")  # works in v0.1.0, but Storage is now a Protocol

    # New (v0.2.0+):
    from pebbles.compat import Storage
    s = Storage("./pebbles.db")  # works — alias to JsonStorage

    # OR (preferred for new code):
    from pebbles import JsonStorage
    s = JsonStorage("./pebbles.db")

This module exists so v0.1 → v0.2 upgrade is one import-path change away,
not a code rewrite.
"""

from pebbles.storage import JsonStorage as Storage

__all__ = ["Storage"]
