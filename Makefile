SHELL:=bash

PYTHON_PKG=dynamic_layers

lint:
	@ruff check $(PYTHON_PKG)

lint-preview:
	@ruff check --preview $(PYTHON_PKG)

lint-fix:
	@ruff check --fix --preview $(PYTHON_PKG)
