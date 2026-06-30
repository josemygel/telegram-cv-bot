.RECIPEPREFIX := >
.PHONY: install run test

install:
> pip install -r requirements.txt -r requirements-dev.txt

run:
> python -m src.bot

test:
> pytest -q
