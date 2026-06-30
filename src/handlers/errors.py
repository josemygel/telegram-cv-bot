"""Global error handler: log the failure so a crashing handler never leaves the
user hanging. Logging only — user-facing messages are sent by each handler."""
from __future__ import annotations

import logging

log = logging.getLogger("josembot")


def make_error_handler(deps):
    async def on_error(update, context):
        # Never log tokens/headers — only the error itself.
        log.error("Unhandled handler error: %s", context.error, exc_info=context.error)

    return on_error
