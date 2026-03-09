# Simplify GUI / Remove HTTP API Plan

## Active Work — Dashboard Graph Series Controls

### Goal

Refine the desktop dashboard graphs so they default to the most useful series, reduce clutter, and keep graph controls compact.

### Current slice
1. Default the temperature graph to the sensors referenced by active fan configs and ignore noisy alarm/limit entries.
2. Default fan RPM and target graphs to grouped hardware-level series while still allowing individual fan overlays.
3. Replace large legends with compact per-graph series menus and stack target PWM below fan RPM.
4. Update dashboard tests and run focused validation plus formatting/linting.

Status: completed.

## Notes
- The desktop GUI now uses direct local state/config/service integration throughout.
- This active plan tracks the graph filtering and visibility follow-up work on top of the completed layout refresh.
