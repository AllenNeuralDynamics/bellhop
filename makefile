sync:
	uv sync

config_schema:
	uv run bellhop config-schema ./schema/bellhop_config_schema.json

api_spec:
	uv run bellhop openapi-spec ./schema/bellhop_api_spec.yaml

schemas: config_schema api_spec

api:
	uv run bellhop

ui:
	cd packages/bellhop-ui && uv run reflex run

format:
	uvx ruff check --fix .
	uvx ruff format .