# ArchMotion Examples

Runnable example scripts demonstrating ArchMotion's API.

## Quick Start

```bash
# Install archmotion
pip install -e ".[dev]"

# Run any example
python examples/01_hello_world.py
python examples/02_login_flow.py
python examples/03_microservices.py
python examples/04_oauth2_flow.py
python examples/05_db_replication.py
python examples/06_ai_yaml_render.py
```

## Examples

| # | File | Description | Nodes | Complexity |
|---|---|---|---|---|
| 01 | `01_hello_world.py` | Minimal — 2 nodes, 1 connection | 2 | ⭐ |
| 02 | `02_login_flow.py` | Full login flow (PRD Golden Script) | 4 | ⭐⭐ |
| 03 | `03_microservices.py` | Microservices + Kafka event bus | 5 | ⭐⭐⭐ |
| 04 | `04_oauth2_flow.py` | OAuth2 Authorization Code Grant | 4 | ⭐⭐⭐ |
| 05 | `05_db_replication.py` | Primary → Replica DB replication | 4 | ⭐⭐⭐ |
| 06 | `06_ai_yaml_render.py` | YAML AI Interface demo | 3 | ⭐⭐ |
