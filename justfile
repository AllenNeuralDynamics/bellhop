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