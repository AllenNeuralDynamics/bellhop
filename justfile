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

run *args: export_ui
	uv run bellhop {{args}}

# runs UI in dev mode
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
#	uv run --isolated --python 3.15 pytest

clear_ui_cache:
	cd packages/bellhop-ui && rm -rf .web

export_ui: clear_ui_cache
	cd packages/bellhop-ui && set "REFLEX_SSR=false" && set "BELLHOP_UI_API_URL=http://localhost:8311" && uv run reflex export --frontend-only --no-zip

build: export_ui
	uv run pyinstaller src/bellhop/cli.py -n bellhop \
	--hide-console hide-early \
	--collect-all bellhop \
	--collect-all bellhop_ui \
	--collect-all reflex \
	--collect-all reflex_base \
	--collect-all reflex_cli \
	--collect-all reflex_build_sdk \
	--collect-all reflex_components_code \
	--collect-all reflex_components_core \
	--collect-all reflex_components_dataeditor \
	--collect-all reflex_components_gridjs \
	--collect-all reflex_components_lucide \
	--collect-all reflex_components_markdown \
	--collect-all reflex_components_moment \
	--collect-all reflex_components_plotly \
	--collect-all reflex_components_radix \
	--collect-all reflex_components_react_player \
	--collect-all reflex_components_recharts \
	--collect-all reflex_components_sonner \
	--collect-all reflex_monaco \
	--collect-all reflex_resizable_panels \
	--collect-all reflex_otel \
	--hidden-import bellhop_ui.bellhop_ui \
	--copy-metadata bellhop \
	--copy-metadata bellhop-client \
	--copy-metadata bellhop-models \
	--copy-metadata bellhop-trolley \
	--copy-metadata bellhop-ui \
	--copy-metadata reflex \
	--add-data "src/bellhop/resources;src/bellhop/resources" \
	--add-data "packages/bellhop-ui/.web/build/client;.web/build/client" \
	--add-data "packages/bellhop-ui/.web/routes.json;.web" \
	--add-data "packages/bellhop-ui/rxconfig.py;." --noconfirm

test_exe:
	dist\bellhop\bellhop.exe --version

run_exe:
	dist\bellhop\bellhop.exe
