# Simplify GUI / Remove HTTP API Plan

## Active Work — Dashboard Layout Refresh

### Goal

Refine the desktop dashboard layout so it stays compact, scrollable, and palette-aware in both light and dark themes.

### Current slice
1. Replace the tall dashboard summary blocks with a compact status strip plus left-panel fan summaries.
2. Move history controls into the graph area and restyle plots for palette compatibility.
3. Rename the `Curves` surface to `Config` and keep config details off the dashboard.
4. Update GUI tests and run focused validation.

Status: in progress.

## Notes
- The desktop GUI now uses direct local state/config/service integration throughout.
- This active plan tracks the current dashboard/layout follow-up work only.
