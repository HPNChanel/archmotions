# ARCHMOTION — PUBLIC ROADMAP

> Tầm nhìn phát triển sản phẩm. Cập nhật mỗi khi chốt milestone.

---

## Tổng quan Version Strategy

```
v0.1.0 (MVP)          v0.2.0 (Polish)        v1.0.0 (Production)
   |                      |                       |
   | Core Pipeline        | Extended API           | Web Export
   | Basic Primitives     | YAML AI Interface      | SaaS Platform
   | Single Theme         | Multi-Theme            | Plugin System
   | CLI Only             | Error DX               | Community Ecosystem
   |                      |                       |
   v                      v                       v
```

---

## v0.1.0 — MVP (Current)
**Mục tiêu:** Render được video MP4 từ Python code. Chứng minh concept hoạt động end-to-end.

| Feature | Status | Ghi chú |
|---|---|---|
| Node + Database primitives | ✅ Done | Fluent API (.right_of, .below) |
| Connection (Manhattan routing) | ✅ Done | L/I-shape, waypoints override |
| FadeIn / FadeOut / Transfer / Pulse | ✅ Done | Validation + frozen dataclass |
| 7 Easing functions | ✅ Done | Linear -> Bounce |
| Scene (Virtual Clock + concurrent) | ✅ Done | Context manager pattern |
| Exception hierarchy (12 types) | ✅ Done | Per-Phase error tree |
| ThemeConfig (dark_terminal) | ✅ Done | Frozen dataclass |
| FFmpeg binary resolution | ✅ Done | 3-tier fallback |
| POC: skia + multiprocessing + ffmpeg | Done | 54.5fps, NVENC, 2.2s |
| Layout Resolver (DAG -> pixels) | Done | Kahn + centering, 22 tests |
| Timeline Compiler (animate -> actions) | Done | 4 decomposers, 26 tests |
| Skia Renderer (frame painting) | Done | canvas + 4 painters, 35 tests |
| Multiprocessing Exporter (Zero-Disk) | Done | FFmpegPipe + Pool, 13 tests |
| Scene.render() full integration | Done | 4-phase pipeline, 11 tests |

**Tiêu chí hoàn thành v0.1.0:**
- `examples/01_hello_world.py` xuất được file MP4 chạy được
- `pytest tests/` pass 100%
- Peak RAM < 512MB cho video 10 giây
- Render time < 30 giây trên i7-11800H

---

## v0.2.0 — Polish & Extend
**Mục tiêu:** API phong phú hơn, YAML AI Interface, DX cao cấp.

| Feature | Status | Ghi chú |
|---|---|---|
| Extended Primitives (Cloud, Queue, Cache, User) | ✅ Done | 4 subclasses, 4 painters, 32 tests |
| Extended Animations (Highlight, ColorShift, Scale) | ✅ Done | 4 classes, 3 decomposers, 38 tests |
| YAML AI Interface (LLM -> YAML -> Video) | ✅ Done | Pydantic schema + builder + 46 tests |
| Rich error messages + progress bar | ✅ Done | DX package, 30 tests |
| Multiple themes (neon, blueprint, light) | ✅ Done | PLAN-012 — 3 new themes |
| Rounded corner routing | ✅ Done | PLAN-012 — `conn_corner_radius` 12px default |
| A* Pathfinding (obstacle-aware routing) | ✅ Done | PLAN-013 — Visibility graph A* router |
| SharedMemory optimization (IPC) | ✅ Done | PLAN-014 — Ring buffer + zero-copy IPC |
| MkDocs documentation site | ✅ Done | PLAN-011 — MkDocs Material + 4 pages |
| 5+ runnable examples | ✅ Done | PLAN-011 — 6 examples total |

**Tiêu chí hoàn thành v0.2.0:**
- Tất cả tính năng v0.1.0 stable
- YAML file render thành công end-to-end
- 80%+ test coverage trên core modules
- Documentation site live trên GitHub Pages

---

## v1.0.0 — Production Ready
**Mục tiêu:** Sẵn sàng cho cộng đồng open-source sử dụng rộng rãi.

| Feature | Status | Ghi chú |
|---|---|---|
| WebGL / Lottie export | ✅ Done | PLAN-015 — Lottie JSON + minify |
| Premium Icon Packs (AWS, GCP, K8s) | ⏳ Future | Open-Core Tier 1 |
| Plugin system (custom primitives) | ⏳ Future | — |
| Interactive HTML player | ✅ Done | PLAN-015 — lottie-web + controls |
| Animated SVG export | ✅ Done | PLAN-015 — CSS @keyframes |
| SaaS platform (ArchMotion Studio) | ⏳ Future | Open-Core Tier 3 |

**Tiêu chí hoàn thành v1.0.0:**
- Tất cả v0.2.0 stable
- PyPI downloads > 1,000/month
- GitHub Stars > 500
- Community contributions (PRs from external devs)

---

## Dependency Graph

```
PLAN-001 (POC)
    |
    +---> PLAN-004 (Skia Renderer)
    |         |
    |         +---> PLAN-005 (MP Exporter)
    |
    +---> PLAN-002 (Layout Resolver)
              |
              +---> PLAN-003 (Timeline Compiler)
                        |
                        +---> PLAN-006 (render() Integration)
                                  |
                                  +---> v0.1.0 RELEASE
                                            |
                                   +---------+---------+
                                   |         |         |
                             PLAN-007   PLAN-008   PLAN-009
                             (Prims)    (Anims)    (YAML AI)
                                   |         |         |
                                   +---------+---------+
                                             |
                                   +---------+---------+
                                   |         |         |
                             PLAN-010   PLAN-011   PLAN-012
                             (DX)      (Docs)     (Themes)
                                   |         |         |
                                   +---------+---------+
                                             |
                                      v0.2.0 RELEASE
                                             |
                                       PLAN-015
                                      (Web Export)
                                             |
                                      v1.0.0 RELEASE
```

---

*Cập nhật lần cuối: 2026-06-13*
