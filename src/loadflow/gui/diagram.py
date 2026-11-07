import math

from PySide6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
)

from PySide6.QtGui import QPen, QBrush, QColor, QPainter
from PySide6.QtCore import Qt, QPointF, Signal

from loadflow.models import (
    Bus, Line, Transformer, Generator, Load, Shunt
)


class NetworkDiagram(QGraphicsView):

    element_selected = Signal(object)
    network_modified = Signal()

    COLORS = {
        "Slack": "#e6a23c",
        "PV": "#409eff",
        "PQ": "#36a269",
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.network = None
        self.mode = "select"
        self.first_bus = None

        self.bus_items = {}
        self.bus_positions = {}

        self._results = None
        self.status_message = ""

        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setBackgroundBrush(QColor("#171b22"))
        self.setMinimumSize(500, 400)

        self.scene.selectionChanged.connect(
            self.on_selection_changed
        )

    # =========================================================
    # MODE
    # =========================================================

    def set_mode(self, mode):

        self.mode = mode
        self.first_bus = None

        if mode == "select":
            self.setDragMode(
                QGraphicsView.DragMode.RubberBandDrag
            )
        else:
            self.setDragMode(
                QGraphicsView.DragMode.NoDrag
            )

    # =========================================================
    # NETWORK DRAWING
    # =========================================================

    def draw_network(self, network, results=None):

        # Preserve positions when redrawing the same network.
        # Reset positions when loading a different network.
        if network is not self.network:
            self.bus_positions = {}

        self.network = network
        self._results = results
        self.first_bus = None

        if network is None:
            self.bus_positions.clear()
            self.bus_items.clear()
            self.scene.clear()
            return

        # Remove positions belonging to deleted buses.
        valid_ids = {
            bus.bus_id for bus in network.buses
        }

        self.bus_positions = {
            bus_id: position
            for bus_id, position in self.bus_positions.items()
            if bus_id in valid_ids
        }

        # Grid layout for buses without an existing position.
        count = len(network.buses)
        columns = max(
            1,
            math.ceil(math.sqrt(max(count, 1)))
        )

        for i, bus in enumerate(network.buses):

            if bus.bus_id not in self.bus_positions:

                self.bus_positions[bus.bus_id] = QPointF(
                    (i % columns) * 190,
                    (i // columns) * 145
                )

        self.refresh(results)
        self.fit_diagram()

    # =========================================================
    # DRAW BUSES
    # =========================================================

    def draw_buses(self, results=None):

        self.bus_items = {}

        for index, bus in enumerate(self.network.buses):

            pos = self.bus_positions[bus.bus_id]

            # Horizontal busbar representation.
            item = QGraphicsLineItem(
                -22, 0, 22, 0
            )

            item.setPos(pos)

            color = QColor(
                self.COLORS.get(
                    bus.bus_type,
                    "#ffffff"
                )
            )

            item.setPen(QPen(color, 5))

            item.setFlag(
                QGraphicsLineItem.GraphicsItemFlag.ItemIsSelectable,
                True
            )

            item.setFlag(
                QGraphicsLineItem.GraphicsItemFlag.ItemIsMovable,
                True
            )

            item.setData(0, "Bus")
            item.setData(1, bus.bus_id)
            item.setZValue(5)

            self.scene.addItem(item)

            self.bus_items[bus.bus_id] = item

            # Bus label.
            label = QGraphicsTextItem(
                f"Bus {bus.bus_id} [{bus.bus_type}]"
            )

            label.setDefaultTextColor(
                Qt.GlobalColor.white
            )

            label.setPos(
                pos.x() + 30,
                pos.y() - 13
            )

            label.setZValue(7)
            self.scene.addItem(label)

            # Voltage label after successful load flow.
            if results and results.get("converged"):

                voltage_values = results.get("voltage_mag")

                if (
                    voltage_values is not None
                    and index < len(voltage_values)
                ):

                    voltage = voltage_values[index]

                    voltage_label = QGraphicsTextItem(
                        f"{voltage:.3f} pu"
                    )

                    voltage_label.setDefaultTextColor(
                        QColor("#7dd3fc")
                    )

                    voltage_label.setPos(
                        pos.x() - 20,
                        pos.y() + 12
                    )

                    voltage_label.setZValue(7)
                    self.scene.addItem(voltage_label)

    # =========================================================
    # DRAW BRANCHES
    # =========================================================

    def draw_branches(self):

        for index, line in enumerate(self.network.lines):

            if getattr(line, "status", True):

                self.draw_branch(
                    line.from_bus,
                    line.to_bus,
                    "Line",
                    index
                )

        for index, transformer in enumerate(self.network.transformers):

            if getattr(transformer, "status", True):

                self.draw_branch(
                    transformer.from_bus,
                    transformer.to_bus,
                    "Transformer",
                    index
                )


    def draw_branch(self, from_bus, to_bus, element_type, index):

        if (
            from_bus not in self.bus_positions
            or to_bus not in self.bus_positions
        ):
            return

        p1 = self.bus_positions[from_bus]
        p2 = self.bus_positions[to_bus]

        color = QColor(
            "#b58cff"
            if element_type == "Transformer"
            else "#9aa4b2"
        )

        branch = QGraphicsLineItem(
            p1.x(), p1.y(),
            p2.x(), p2.y()
        )

        branch.setPen(QPen(color, 3))
        branch.setZValue(0)

        branch.setFlag(
            QGraphicsLineItem.GraphicsItemFlag.ItemIsSelectable,
            True
        )

        branch.setData(0, element_type)
        branch.setData(1, index)

        self.scene.addItem(branch)

        # Transformer symbol
        if element_type == "Transformer":

            mx = (p1.x() + p2.x()) / 2
            my = (p1.y() + p2.y()) / 2

            for offset in (-6, 6):

                circle = QGraphicsEllipseItem(
                    mx - 5 + offset,
                    my - 5,
                    10,
                    10
                )

                circle.setBrush(
                    QBrush(QColor("#171b22"))
                )

                circle.setPen(
                    QPen(color, 2)
                )

                circle.setZValue(2)
                self.scene.addItem(circle)
    # =========================================================
    # DRAW GENERATORS, LOADS AND SHUNTS
    # =========================================================

    def draw_attached_elements(self):

        if self.network is None:
            return

        for bus_id, pos in self.bus_positions.items():

            generators = [
                g for g in self.network.generators
                if g.bus_id == bus_id
                and getattr(g, "status", True)
            ]

            loads = [
                load for load in self.network.loads
                if load.bus_id == bus_id
                and getattr(load, "status", True)
            ]

            shunts = [
                shunt for shunt in self.network.shunts
                if shunt.bus_id == bus_id
                and getattr(shunt, "status", True)
            ]

            # ---------------- GENERATORS ----------------

            for i, generator in enumerate(generators):

                x = pos.x() - 65
                y = pos.y() - 42 - i * 34

                self.draw_lead(
                    pos.x() - 22,
                    pos.y(),
                    x + 13,
                    y
                )

                symbol = QGraphicsEllipseItem(
                    x - 13,
                    y - 13,
                    26,
                    26
                )

                symbol.setBrush(
                    QBrush(QColor("#171b22"))
                )

                symbol.setPen(
                    QPen(QColor("#55c2a3"), 2)
                )

                symbol.setFlag(
                    QGraphicsEllipseItem.GraphicsItemFlag.ItemIsSelectable,
                    True
                )

                generator_index = next(
                    j for j, g in enumerate(self.network.generators)
                    if g is generator
                )

                symbol.setData(0, "Generator")
                symbol.setData(1, generator_index)

                symbol.setZValue(3)
                self.scene.addItem(symbol)

                self.add_symbol_text(
                    "G",
                    x - 5,
                    y - 10,
                    "#55c2a3"
                )

            # ---------------- LOADS ----------------

            for i, load in enumerate(loads):

                x = pos.x() + 65
                y = pos.y() - 42 - i * 34

                self.draw_lead(
                    pos.x() + 22,
                    pos.y(),
                    x - 20,
                    y
                )

                symbol = QGraphicsRectItem(
                    x - 20,
                    y - 12,
                    40,
                    24
                )

                symbol.setBrush(
                    QBrush(QColor("#171b22"))
                )

                symbol.setPen(
                    QPen(QColor("#f0a35e"), 2)
                )

                symbol.setFlag(
                    QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable,
                    True
                )

                load_index = next(
                    j for j, item in enumerate(self.network.loads)
                    if item is load
                )

                symbol.setData(0, "Load")
                symbol.setData(1, load_index)

                symbol.setZValue(3)
                self.scene.addItem(symbol)

                self.add_symbol_text(
                    "LOAD",
                    x - 17,
                    y - 9,
                    "#f0a35e"
                )

            # ---------------- SHUNTS ----------------

            for i, shunt in enumerate(shunts):

                x = pos.x()
                y = pos.y() + 48 + i * 30

                self.draw_lead(
                    x,
                    pos.y(),
                    x,
                    y - 12
                )

                # Selectable shunt symbol
                symbol = QGraphicsRectItem(
                    x - 10,
                    y - 8,
                    20,
                    16
                )

                symbol.setBrush(
                    QBrush(QColor("#171b22"))
                )

                symbol.setPen(
                    QPen(QColor("#d6c46a"), 2)
                )

                symbol.setFlag(
                    QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable,
                    True
                )

                shunt_index = next(
                    j for j, item in enumerate(self.network.shunts)
                    if item is shunt
                )

                symbol.setData(0, "Shunt")
                symbol.setData(1, shunt_index)

                symbol.setZValue(3)
                self.scene.addItem(symbol)

                self.add_symbol_text(
                    "SH",
                    x + 13,
                    y - 10,
                    "#d6c46a"
                )

            # ---------------- EXTERNAL GRID ----------------

            bus = next(
                (
                    b for b in self.network.buses
                    if b.bus_id == bus_id
                ),
                None
            )

            if bus and bus.bus_type == "Slack":

                self.add_symbol_text(
                    "GRID",
                    pos.x() - 18,
                    pos.y() - 42,
                    "#e6a23c"
                )

    def draw_lead(
        self,
        x1,
        y1,
        x2,
        y2,
        color="#9aa4b2",
        width=1.5
    ):

        lead = QGraphicsLineItem(
            x1, y1, x2, y2
        )

        lead.setPen(
            QPen(QColor(color), width)
        )

        lead.setZValue(1)
        self.scene.addItem(lead)

    def add_symbol_text(self, text, x, y, color):

        label = QGraphicsTextItem(text)

        label.setDefaultTextColor(
            QColor(color)
        )

        label.setPos(x, y)
        label.setZValue(4)

        self.scene.addItem(label)

    # =========================================================
    # DRAG AND DROP
    # =========================================================

    def dragEnterEvent(self, event):

        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):

        if event.mimeData().hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):

        if self.network is None:
            event.ignore()
            return

        element_type = event.mimeData().text().strip()

        position = self.mapToScene(
            event.position().toPoint()
        )

        try:

            if element_type == "Bus":

                self.add_bus(position)

            elif element_type in (
                "Generator",
                "Load",
                "Shunt",
                "External Grid"
            ):

                bus_id = self.find_bus_near(position)

                if bus_id is None:

                    self.element_selected.emit({
                        "error": "Drop this element directly onto a bus."
                    })

                    event.ignore()
                    return

                self.attach_element(
                    element_type,
                    bus_id
                )

            elif element_type in (
                "Transmission Line",
                "Transformer"
            ):

                self.set_mode(
                    "line"
                    if element_type == "Transmission Line"
                    else "transformer"
                )

                self.status_message = (
                    "Select the first bus, then the second bus."
                )

            else:

                event.ignore()
                return

            event.acceptProposedAction()

        except (ValueError, TypeError) as error:

            self.element_selected.emit({
                "error": str(error)
            })

            event.ignore()

    def find_bus_near(self, position, radius=30):

        closest_id = None
        closest_distance = radius

        for bus_id, bus_position in self.bus_positions.items():

            distance = math.hypot(
                position.x() - bus_position.x(),
                position.y() - bus_position.y()
            )

            if distance <= closest_distance:

                closest_distance = distance
                closest_id = bus_id

        return closest_id

    # =========================================================
    # MOUSE INTERACTION
    # =========================================================

    def mousePressEvent(self, event):

        position = self.mapToScene(
            event.position().toPoint()
        )

        if event.button() == Qt.MouseButton.LeftButton:

            if self.network is not None and self.mode == "bus":

                self.add_bus(position)
                return

            if self.mode in ("line", "transformer"):

                self.select_branch_endpoint(position)
                return

            if self.mode in (
                "Generator",
                "Load",
                "Shunt",
                "External Grid"
            ):

                bus_id = self.find_bus_near(position)

                if bus_id is not None:

                    self.attach_element(
                        self.mode,
                        bus_id
                    )

                else:

                    self.status_message = (
                        "Select a bus to attach this element."
                    )

                return

        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):

        super().mouseReleaseEvent(event)

        if self.mode == "select" and self.network is not None:

            moved = False

            for bus_id, item in self.bus_items.items():

                new_position = item.scenePos()
                old_position = self.bus_positions.get(bus_id)

                if (
                    old_position is None
                    or (
                        new_position - old_position
                    ).manhattanLength() > 0.01
                ):

                    self.bus_positions[bus_id] = QPointF(
                        new_position
                    )

                    moved = True

            if moved:

                self.refresh(self._results)
                self.network_modified.emit()

    # =========================================================
    # ADD BUS
    # =========================================================

    def add_bus(self, position):

        if self.network is None:
            return

        new_id = max(
            (bus.bus_id for bus in self.network.buses),
            default=0
        ) + 1

        bus_type = (
            "Slack"
            if not any(
                bus.bus_type == "Slack"
                for bus in self.network.buses
            )
            else "PQ"
        )

        self.network.add_bus(
            Bus(
                bus_id=new_id,
                bus_type=bus_type,
                name=f"Bus {new_id}"
            )
        )

        self.bus_positions[new_id] = QPointF(position)

        self.refresh()
        self.network_modified.emit()

    # =========================================================
    # ATTACH ELEMENTS
    # =========================================================

    def attach_element(self, element_type, bus_id):

        if self.network is None:
            return

        target = next(
            (
                bus for bus in self.network.buses
                if bus.bus_id == bus_id
            ),
            None
        )

        if target is None:
            return

        if element_type == "External Grid":

            for bus in self.network.buses:

                if bus.bus_type == "Slack":
                    bus.bus_type = "PQ"

            target.bus_type = "Slack"

        elif element_type == "Generator":

            generator = Generator(bus_id=bus_id)

            self.network.add_generator(generator)

            # Convert PQ bus to PV
            if target.bus_type == "PQ":
                target.bus_type = "PV"
                target.voltage_mag_pu = generator.voltage_setpoint_pu
                
        elif element_type == "Load":

            self.network.add_load(
                Load(bus_id=bus_id)
            )

        elif element_type == "Shunt":

            self.network.add_shunt(
                Shunt(bus_id=bus_id)
            )

        else:
            return

        self.refresh()
        self.network_modified.emit()

    # =========================================================
    # BRANCH CONNECTION
    # =========================================================

    def select_branch_endpoint(self, position):

        if self.network is None:
            return

        bus_id = self.find_bus_near(position)

        if bus_id is None:
            return

        if self.first_bus is None:

            self.first_bus = bus_id

            self.status_message = (
                f"Bus {bus_id} selected. Select the second bus."
            )

            return

        first = self.first_bus
        second = bus_id

        self.first_bus = None

        if first == second:

            self.status_message = (
                "Choose a different bus for the second endpoint."
            )

            return

        if self.mode == "line":

            self.network.add_line(
                Line(
                    from_bus=first,
                    to_bus=second,
                    r_pu=0.01,
                    x_pu=0.1
                )
            )

        elif self.mode == "transformer":

            self.network.add_transformer(
                Transformer(
                    from_bus=first,
                    to_bus=second,
                    r_pu=0.01,
                    x_pu=0.1
                )
            )

        self.status_message = (
            f"{self.mode.title()} connected: {first} to {second}."
        )

        self.refresh()
        self.network_modified.emit()

        # Keep the branch tool active for additional connections.

    # =========================================================
    # SELECTION
    # =========================================================

    def on_selection_changed(self):

        if self.network is None:
            self.element_selected.emit(None)
            return

        selected = self.scene.selectedItems()

        if not selected:
            self.element_selected.emit(None)
            return

        item = selected[0]

        element_type = item.data(0)
        index = item.data(1)

        # Bus selection uses bus_id, not list index.
        if element_type == "Bus":

            bus = next(
                (
                    b for b in self.network.buses
                    if b.bus_id == index
                ),
                None
            )

            self.element_selected.emit(bus)
            return

        collections = {
            "Generator": self.network.generators,
            "Load": self.network.loads,
            "Shunt": self.network.shunts,
            "Line": self.network.lines,
            "Transformer": self.network.transformers,
        }

        if element_type not in collections or index is None:
            self.element_selected.emit(None)
            return

        elements = collections[element_type]

        if 0 <= index < len(elements):
            self.element_selected.emit(elements[index])
        else:
            self.element_selected.emit(None)

    # =========================================================
    # DELETE SELECTED BUS
    # =========================================================

    def delete_selected(self):

        if self.network is None:
            return

        selected = self.scene.selectedItems()

        if not selected:
            return

        item = selected[0]

        if item.data(0) != "Bus":
            return

        bus_id = item.data(1)

        self.network.buses = [
            bus for bus in self.network.buses
            if bus.bus_id != bus_id
        ]

        self.network.generators = [
            generator for generator in self.network.generators
            if generator.bus_id != bus_id
        ]

        self.network.loads = [
            load for load in self.network.loads
            if load.bus_id != bus_id
        ]

        self.network.shunts = [
            shunt for shunt in self.network.shunts
            if shunt.bus_id != bus_id
        ]

        self.network.lines = [
            line for line in self.network.lines
            if line.from_bus != bus_id
            and line.to_bus != bus_id
        ]

        self.network.transformers = [
            transformer for transformer in self.network.transformers
            if transformer.from_bus != bus_id
            and transformer.to_bus != bus_id
        ]

        self.bus_positions.pop(bus_id, None)

        self.refresh()
        self.network_modified.emit()

    # =========================================================
    # REFRESH
    # =========================================================

    def refresh(self, results=None):

        if self.network is None:

            self.scene.clear()
            self.bus_items = {}
            return

        self._results = results

        self.scene.clear()
        self.bus_items = {}

        self.draw_branches()
        self.draw_buses(self._results)
        self.draw_attached_elements()

        bounds = self.scene.itemsBoundingRect()

        if bounds.isNull():
            bounds = self.scene.sceneRect()

        self.scene.setSceneRect(
            bounds.adjusted(-100, -100, 100, 100)
        )

    # =========================================================
    # VIEW CONTROLS
    # =========================================================

    def wheelEvent(self, event):

        factor = (
            1.15
            if event.angleDelta().y() > 0
            else 0.87
        )

        self.scale(factor, factor)

    def fit_diagram(self):

        if self.scene.items():

            self.fitInView(
                self.scene.sceneRect(),
                Qt.AspectRatioMode.KeepAspectRatio
            )