"""Local CLI chat — test the grounded assistant without Telegram.

Uses your .env / LLM_BACKEND config (LM Studio by default). Same grounding as the
bot (profile + structured projects), so what you see here is what Telegram gets.
Run:  python chat_cli.py
"""
from __future__ import annotations

from src.config import ASSISTANT_NAME, LLM_BACKEND, PROFILE_PATH
from src.grounding import build_grounded_prompt
from src.llm import BackendError
from src.pipeline import Pipeline
from src.projects import ProjectsRepository
from src.runtime import get_llm


def main() -> None:
    system_prompt = build_grounded_prompt(ASSISTANT_NAME, PROFILE_PATH, ProjectsRepository().list_projects())
    bot = Pipeline(llm=get_llm(LLM_BACKEND), system_prompt=system_prompt)
    print(f"{ASSISTANT_NAME}'s assistant [{LLM_BACKEND}]. Type 'exit' to quit.\n")
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if text.lower() in {"exit", "quit"}:
            break
        if not text:
            continue
        try:
            reply = bot.process_text(0, text)["reply"]
        except BackendError as exc:
            print("bot> [backend no disponible]", exc, "\n")
            continue
        print("bot>", reply or "[respuesta vacía — reformula la pregunta]", "\n")


if __name__ == "__main__":
    main()
