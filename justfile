[windows]
set shell := ["cmd.exe", "/C"]

sync:
	uv sync

config_schema:
	uv run bellhop config-schema ./schema/bellhop_config_schema.json

api_spec:
	uv run bellhop openapi-spec ./schema/bellhop_api_spec.yaml

schemas: config_schema api_spec

generate-client:
	uv run python scripts/generate_client.py
	uvx ruff check --fix packages/bellhop-client/src/bellhop_client/
	uvx ruff format packages/bellhop-client/src/bellhop_client/

api:
	uv run bellhop

ui:
	cd packages/bellhop-ui && uv run reflex run

format:
	uvx ruff check --fix .
	uvx ruff format .

test:
	uv run pytest

test_all_versions:
	uv run --isolated --python 3.11 pytest
	uv run --isolated --python 3.12 pytest
	uv run --isolated --python 3.13 pytest
	uv run --isolated --python 3.14 pytest
	uv run --isolated --python 3.15 pytest

build:
	uv run pyinstaller src/bellhop/cli.py -n bellhop --noconsole --collect-all bellhop --add-data "src/bellhop/resources;src/bellhop/resources"

test_build:
	./dist/bellhop/bellhop.exe -v