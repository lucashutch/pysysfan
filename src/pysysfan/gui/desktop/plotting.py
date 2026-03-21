"""Reusable plot helpers for the PySide6 desktop GUI."""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QWheelEvent

try:  # pragma: no cover - optional GUI dependency
    import pyqtgraph as pg
except ImportError:  # pragma: no cover - optional GUI dependency
    pg = None


class ElapsedSecondsAxis(pg.AxisItem if pg is not None else object):
    """Bottom-axis helper that renders elapsed seconds as positive values."""

    def tickStrings(self, values, scale, spacing):  # noqa: N802
        if pg is None:  # pragma: no cover - protected by callers
            return []

        precision = 0
        if spacing < 1:
            precision = 1
        if spacing < 0.1:
            precision = 2

        rendered: list[str] = []
        for value in values:
            seconds = abs(value)
            if precision == 0:
                rendered.append(str(int(round(seconds))))
                continue
            rendered.append(f"{seconds:.{precision}f}".rstrip("0").rstrip("."))
        return rendered


class DashboardPlotWidget(pg.PlotWidget if pg is not None else object):
    """Plot widget with interaction disabled for dashboard-style charts."""

    hoverChanged = Signal(object)

    def __init__(self, *args, **kwargs) -> None:
        if pg is None:  # pragma: no cover - protected by callers
            raise RuntimeError("pyqtgraph is required for DashboardPlotWidget")
        super().__init__(*args, **kwargs)
        self.setMenuEnabled(False)
        self.hideButtons()
        self.setMouseEnabled(x=False, y=False)
        self.getPlotItem().vb.setMouseEnabled(x=False, y=False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self._series_items: dict[str, pg.PlotDataItem] = {}
        self._vertical_crosshair = pg.InfiniteLine(angle=90, movable=False)
        self._horizontal_crosshair = pg.InfiniteLine(angle=0, movable=False)
        self.addItem(self._vertical_crosshair, ignoreBounds=True)
        self.addItem(self._horizontal_crosshair, ignoreBounds=True)
        self._set_crosshair_visible(False)

        self.scene().sigMouseMoved.connect(self._handle_scene_mouse_moved)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """Ignore wheel events so charts do not zoom unexpectedly."""
        event.ignore()

    def update_series(self, series_id: str, xs: list, ys: list, pen) -> None:
        """Update an existing series or create a new one."""
        if series_id in self._series_items:
            self._series_items[series_id].setData(xs, ys)
            self._series_items[series_id].setPen(pen)
        else:
            item = pg.PlotDataItem(xs, ys, pen=pen, antialias=True)
            self._series_items[series_id] = item
            self.addItem(item)

    def remove_series(self, series_id: str) -> None:
        """Remove a series by ID."""
        item = self._series_items.pop(series_id, None)
        if item is not None:
            self.removeItem(item)

    def remove_stale_series(self, active_ids: set[str]) -> None:
        """Remove all series not in the active set."""
        stale = [sid for sid in self._series_items if sid not in active_ids]
        for sid in stale:
            self.remove_series(sid)

    def clear_all_series(self) -> None:
        """Remove all tracked series items."""
        for item in self._series_items.values():
            self.removeItem(item)
        self._series_items.clear()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if pg is None:  # pragma: no cover - protected by callers
            return super().mouseMoveEvent(event)

        scene_pos = self.mapToScene(event.position().toPoint())
        data_pos = self._scene_to_data(scene_pos)
        if data_pos is None:
            self._set_crosshair_visible(False)
            self.hoverChanged.emit(None)
            return super().mouseMoveEvent(event)

        self._update_hover(data_pos.x(), data_pos.y())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._set_crosshair_visible(False)
        self.hoverChanged.emit(None)
        super().leaveEvent(event)

    def _handle_scene_mouse_moved(self, scene_pos) -> None:
        data_pos = self._scene_to_data(scene_pos)
        if data_pos is None:
            self._set_crosshair_visible(False)
            self.hoverChanged.emit(None)
            return

        self._update_hover(data_pos.x(), data_pos.y())

    def _scene_to_data(self, scene_pos) -> QPointF | None:
        view_box = self.getPlotItem().vb
        if not view_box.sceneBoundingRect().contains(scene_pos):
            return None
        return view_box.mapSceneToView(scene_pos)

    def _update_hover(self, x_value: float, y_value: float) -> None:
        self._vertical_crosshair.setPos(x_value)
        self._horizontal_crosshair.setPos(y_value)
        self._set_crosshair_visible(True)
        self.hoverChanged.emit((float(x_value), float(y_value)))

    def _set_crosshair_visible(self, visible: bool) -> None:
        self._vertical_crosshair.setVisible(visible)
        self._horizontal_crosshair.setVisible(visible)


class CurveEditorPlotWidget(pg.PlotWidget if pg is not None else object):
    """Interactive plot widget for curve editing with hover and drag support."""

    pointsChanged = Signal(object)
    hoverChanged = Signal(object)

    def __init__(self, *args, **kwargs) -> None:
        if pg is None:  # pragma: no cover - protected by callers
            raise RuntimeError("pyqtgraph is required for CurveEditorPlotWidget")
        super().__init__(*args, **kwargs)
        self.setMenuEnabled(False)
        self.hideButtons()
        self.setMouseEnabled(x=False, y=False)
        self.getPlotItem().vb.setMouseEnabled(x=False, y=False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

        self._points: list[tuple[float, float]] = []
        self._preview_series: list[tuple[float, float]] = []
        self._drag_index: int | None = None
        self._x_bounds = (20.0, 100.0)
        self._y_bounds = (0.0, 100.0)

        self._preview_item = pg.PlotDataItem()
        self._curve_item = pg.PlotDataItem()
        self._points_item = pg.ScatterPlotItem()
        self.addItem(self._preview_item)
        self.addItem(self._curve_item)
        self.addItem(self._points_item)

        self._vertical_crosshair = pg.InfiniteLine(angle=90, movable=False)
        self._horizontal_crosshair = pg.InfiniteLine(angle=0, movable=False)
        self.addItem(self._vertical_crosshair, ignoreBounds=True)
        self.addItem(self._horizontal_crosshair, ignoreBounds=True)
        self._set_crosshair_visible(False)

        self.scene().sigMouseMoved.connect(self._handle_scene_mouse_moved)

    def set_theme(self, colors: dict[str, str | list[str]]) -> None:
        """Apply palette-aware colors to the curve editor plot."""
        if pg is None:  # pragma: no cover - protected by callers
            return

        series = colors.get("series", ["#4E79A7"])
        line_color = series[0] if isinstance(series, list) and series else "#4E79A7"
        point_color = (
            series[3] if isinstance(series, list) and len(series) > 3 else "#E15759"
        )
        muted = str(colors.get("muted", "#6b7280"))
        foreground = str(colors.get("foreground", "#111827"))
        background = str(colors.get("background", "#ffffff"))

        self.setBackground(background)
        plot_item = self.getPlotItem()
        plot_item.getAxis("left").setTextPen(foreground)
        plot_item.getAxis("bottom").setTextPen(foreground)
        plot_item.getAxis("left").setPen(muted)
        plot_item.getAxis("bottom").setPen(muted)
        plot_item.getAxis("top").setPen(muted)
        plot_item.getAxis("right").setPen(muted)

        self._preview_item.setPen(pg.mkPen(color=line_color, width=2.5))
        self._curve_item.setPen(pg.mkPen(color=foreground, width=1.2))
        self._points_item.setBrush(pg.mkBrush(point_color))
        self._points_item.setPen(pg.mkPen(color=foreground, width=1.2))
        crosshair_pen = pg.mkPen(color=muted, width=1, style=Qt.PenStyle.DashLine)
        self._vertical_crosshair.setPen(crosshair_pen)
        self._horizontal_crosshair.setPen(crosshair_pen)

    def set_preview_series(self, preview_series: list[tuple[float, float]]) -> None:
        """Replace the rendered preview curve while keeping editable points intact."""
        self._preview_series = [
            (float(temperature), float(speed)) for temperature, speed in preview_series
        ]
        self._refresh_items()

    def set_points(self, points: list[tuple[float, float]]) -> None:
        """Replace the current control points and redraw the chart."""
        self._points = [
            (float(temperature), float(speed))
            for temperature, speed in sorted(points, key=lambda point: point[0])
        ]
        self._refresh_items()

    def points(self) -> list[tuple[float, float]]:
        """Return a copy of the current control points."""
        return list(self._points)

    def move_control_point(self, index: int, temperature: float, speed: float) -> None:
        """Move a control point, snapping to integer coordinates and preserving order."""
        if index < 0 or index >= len(self._points):
            return

        constrained = self._constrain_point(index, temperature, speed)
        if constrained == self._points[index]:
            self._update_hover(*constrained)
            return

        self._points[index] = constrained
        self._refresh_items()
        self._update_hover(*constrained)
        self.pointsChanged.emit(self.points())

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        """Ignore wheel events so the editor does not zoom unexpectedly."""
        event.ignore()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if pg is None:  # pragma: no cover - protected by callers
            return super().mousePressEvent(event)

        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())
            point_index = self._nearest_point_index(scene_pos)
            if point_index is not None:
                self._drag_index = point_index
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if pg is None:  # pragma: no cover - protected by callers
            return super().mouseMoveEvent(event)

        scene_pos = self.mapToScene(event.position().toPoint())
        data_pos = self._scene_to_data(scene_pos)
        if data_pos is None:
            self._set_crosshair_visible(False)
            self.hoverChanged.emit(None)
            return super().mouseMoveEvent(event)

        if self._drag_index is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move_control_point(self._drag_index, data_pos.x(), data_pos.y())
            event.accept()
            return

        self._update_hover(data_pos.x(), data_pos.y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._drag_index = None
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._drag_index = None
        self._set_crosshair_visible(False)
        self.hoverChanged.emit(None)
        super().leaveEvent(event)

    def _handle_scene_mouse_moved(self, scene_pos) -> None:
        if self._drag_index is not None:
            return

        data_pos = self._scene_to_data(scene_pos)
        if data_pos is None:
            self._set_crosshair_visible(False)
            self.hoverChanged.emit(None)
            return

        self._update_hover(data_pos.x(), data_pos.y())

    def _refresh_items(self) -> None:
        preview_xs = [point[0] for point in self._preview_series]
        preview_ys = [point[1] for point in self._preview_series]
        xs = [point[0] for point in self._points]
        ys = [point[1] for point in self._points]
        self._preview_item.setData(preview_xs, preview_ys)
        self._curve_item.setData(xs, ys)
        self._points_item.setData(xs, ys, size=11)
        self.setXRange(self._x_bounds[0], self._x_bounds[1], padding=0.02)
        self.setYRange(self._y_bounds[0], self._y_bounds[1], padding=0.05)

    def _scene_to_data(self, scene_pos) -> QPointF | None:
        view_box = self.getPlotItem().vb
        if not view_box.sceneBoundingRect().contains(scene_pos):
            return None
        return view_box.mapSceneToView(scene_pos)

    def _nearest_point_index(self, scene_pos) -> int | None:
        if not self._points:
            return None

        view_box = self.getPlotItem().vb
        best_index: int | None = None
        best_distance: float | None = None
        for index, (temperature, speed) in enumerate(self._points):
            point_scene = view_box.mapViewToScene(QPointF(temperature, speed))
            distance = (
                (point_scene.x() - scene_pos.x()) ** 2
                + (point_scene.y() - scene_pos.y()) ** 2
            ) ** 0.5
            if distance > 14:
                continue
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_index = index
        return best_index

    def _constrain_point(
        self,
        index: int,
        temperature: float,
        speed: float,
    ) -> tuple[float, float]:
        rounded_temperature = float(round(temperature))
        rounded_speed = float(round(speed))

        min_temperature = self._x_bounds[0]
        max_temperature = self._x_bounds[1]
        if index > 0:
            min_temperature = self._points[index - 1][0] + 1.0
        if index < len(self._points) - 1:
            max_temperature = self._points[index + 1][0] - 1.0

        constrained_temperature = min(
            max(rounded_temperature, min_temperature), max_temperature
        )
        constrained_speed = min(
            max(rounded_speed, self._y_bounds[0]), self._y_bounds[1]
        )
        return (float(constrained_temperature), float(constrained_speed))

    def _update_hover(self, temperature: float, speed: float) -> None:
        snapped_temperature = min(
            max(int(round(temperature)), int(self._x_bounds[0])), int(self._x_bounds[1])
        )
        snapped_speed = min(
            max(int(round(speed)), int(self._y_bounds[0])), int(self._y_bounds[1])
        )
        self._vertical_crosshair.setPos(snapped_temperature)
        self._horizontal_crosshair.setPos(snapped_speed)
        self._set_crosshair_visible(True)
        self.hoverChanged.emit((snapped_temperature, snapped_speed))

    def _set_crosshair_visible(self, visible: bool) -> None:
        self._vertical_crosshair.setVisible(visible)
        self._horizontal_crosshair.setVisible(visible)
