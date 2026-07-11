# ArchMotion Examples

Runnable example scripts demonstrating ArchMotion v2.0's API — from basic
architecture animations to cross-domain fusion demos.

## Quick Start

```bash
# Install archmotion
pip install -e ".[dev]"

# Run any example
python examples/01_hello_world.py
python examples/03_microservices.py
python examples/06_ai_yaml_render.py
python examples/v2_fusion_demo.py
```

## Architecture Examples

| # | File | Description | Nodes | Complexity |
|---|---|---|---|---|
| 01 | `01_hello_world.py` | Minimal — 2 nodes, 1 connection | 2 | ⭐ |
| 02 | `02_login_flow.py` | Full login flow (PRD Golden Script) | 4 | ⭐⭐ |
| 03 | `03_microservices.py` | Microservices + Kafka event bus | 5 | ⭐⭐⭐ |
| 04 | `04_oauth2_flow.py` | OAuth2 Authorization Code Grant | 4 | ⭐⭐⭐ |
| 05 | `05_db_replication.py` | Primary → Replica DB replication | 4 | ⭐⭐⭐ |
| 06 | `06_ai_yaml_render.py` | YAML AI Interface demo | 3 | ⭐⭐ |

## Fusion Examples (v2.0)

Cross-domain demos showing architecture, geometry, charts, math, and code
coexisting — with `Transform` morphing between domains.

| # | File | Domains | Demonstrates |
|---|---|---|---|
| — | `v2_fusion_demo.py` | arch + charts + geometry | Combined best-of showcase |
| 07 | `07_fusion_arch_metrics.py` | architecture + charts | Live `BarChart` beside a diagram |
| 08 | `08_fusion_morph.py` | arch + geometry + charts | `Node` → `Circle` → `PieChart` morph |
| 09 | `09_fusion_math_over_arch.py` | architecture + math | LaTeX equation over a diagram (needs `latex`) |
| 10 | `10_fusion_code_walkthrough.py` | architecture + code | `CodeBlock` with data-flow `Transfer` |

Architecture examples render MP4. Fusion demos export SVG + Lottie by default
(Skia/FFmpeg optional for MP4). Example 09 requires `latex` + `dvisvgm`.
