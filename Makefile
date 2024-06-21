SHELL:=bash

.PHONY: tests isort lint lint-preview lint-fix

PYTHON_PKG=dynamic_layers

tests:
	@python3 -m unittest

isort:
	@isort .

lint:
	@ruff check $(PYTHON_PKG)

lint-preview:
	@ruff check --preview $(PYTHON_PKG)

lint-fix:
	@ruff check --fix --preview $(PYTHON_PKG)
