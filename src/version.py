"""Single source of truth for the bot's version.

Bump this on every production deploy: /info reports it and the startup log prints
it, so the owner can verify WHICH build is actually answering (e.g. to detect a
stale container or a stray duplicate instance polling the same token).

Part of the josembot project, original work by Jose Miguel Gómez Lozano
(github.com/josemygel/telegram-cv-bot) — see AUTHORS.md and LICENSE.
"""
__version__ = "1.1.0"
