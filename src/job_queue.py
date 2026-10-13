"""Cola de un solo trabajador para la transcripcion.

POR QUE: large-v3-turbo en 2 CPUs satura la maquina; dos transcripciones a la vez tardarian
el doble cada una y el bot dejaria de responder. Con un asyncio.Lock (FIFO) solo corre una;
el resto espera y se les avisa de su puesto. El trabajo pesado va a un hilo (executor) para
no bloquear el bucle de eventos de Telegram.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable


class SingleWorkerQueue:
    def __init__(self) -> None:
        self._lock: asyncio.Lock | None = None  # perezoso: se crea ya dentro del bucle
        self._pending = 0  # en ejecucion + esperando

    @property
    def pending(self) -> int:
        return self._pending

    async def run(self, fn: Callable, *args, on_wait: Callable[[int], Awaitable[None]] | None = None):
        """Ejecuta fn(*args) en un hilo cuando le toque. `on_wait(n)` se llama si hay n
        trabajos por delante (n = su puesto en la cola)."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        ahead = self._pending
        self._pending += 1
        try:
            if ahead > 0 and on_wait is not None:
                await on_wait(ahead)
            async with self._lock:
                return await asyncio.to_thread(fn, *args)
        finally:
            self._pending -= 1
