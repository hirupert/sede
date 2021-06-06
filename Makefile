.PHONY: all
all: lint black_check unit_test

export ROOT_DIR := $(realpath .)

.PHONY: lint
lint:
	pylint $(ROOT_DIR)/src

.PHONY: black
black:
	black $(ROOT_DIR)/src --config=./pyproject.toml

.PHONY: black_check
black_check:
	black --check $(ROOT_DIR)/src --config=./pyproject.toml

.PHONY: unit_test
unit_test:
	python -m unittest discover $(ROOT_DIR)/src/test/unit_test/
