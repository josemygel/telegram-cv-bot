"""Telegram handlers, split by responsibility so bot.py stays thin wiring.

Each submodule exposes a make_*(deps) factory that closes over its dependencies
(pipeline, repositories, services) instead of using module globals — this keeps
the handlers injectable and unit-testable with fakes.
"""
