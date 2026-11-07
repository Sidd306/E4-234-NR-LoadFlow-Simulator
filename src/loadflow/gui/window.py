import math

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLabel, QFileDialog, QMessageBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QDockWidget,
    QListWidget, QFormLayout, QLineEdit, QStatusBar,
    QToolBar, QHeaderView
)

from loadflow.models import Network
from loadflow.matpower_import import load_matpower_case
from loadflow.solver import solve_newton_raphson
from loadflow.gui.diagram import NetworkDiagram
from PySide6.QtGui import QDrag
from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QPushButton

# =====================================================
# RESULTS TABLE
# =====================================================

class ResultsTable(QTableWidget):

    def __init__(self):
        super().__init__()

        self.setAlternatingRowColors(True)
        self.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.horizontalHeader().setStretchLastSection(True)

    def set_data(self, headers, rows):

        self.setSortingEnabled(False)
        self.clear()

        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setRowCount(len(rows))

        for i, row in enumerate(rows):
            for j, value in enumerate(row):

                if value is None:
                    display = "—"
                elif isinstance(value, float):
                    display = f"{value:.5f}"
                else:
                    display = str(value)

                item = QTableWidgetItem(display)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                self.setItem(i, j, item)

        self.setSortingEnabled(True)

class ElementPalette(QListWidget):

    def startDrag(self, supported_actions):

        item = self.currentItem()

        if item is None or item.text() == "Select":
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(item.text())

        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)

# =====================================================
# MAIN WINDOW
# =====================================================

class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("E4234 | Power System Analysis")
        self.resize(1550, 950)

        self.network = None
        self.results = None
        self.case_path = None

        self.tolerance = 1e-8
        self.max_iterations = 20

        # Create canvas first because actions use it.
        self.create_central_canvas()

        self.create_actions()
        self.create_palette_dock()
        self.create_properties_dock()
        self.create_results_dock()

        self.create_menus()
        self.create_toolbar()
        self.create_status_bar()

        self.apply_style()

    def activate_tool(self, tool):
        if self.network is None:
            QMessageBox.warning(
                self, "No Network",
                "Create a new network or import a MATPOWER case first."
            )
            return

        modes = {
            "Select": "select",
            "Bus": "bus",
            "Transmission Line": "line",
            "Transformer": "transformer",
            "Generator": "Generator",
            "Load": "Load",
            "Shunt": "Shunt",
            "External Grid": "External Grid"
        }

        self.diagram.set_mode(modes[tool])

        instructions = {
            "Select": "Select and move network elements.",
            "Bus": "Click the canvas to place a bus.",
            "Transmission Line": "Click the first bus, then the second bus.",
            "Transformer": "Click the first bus, then the second bus.",
            "Generator": "Click the bus where the generator should be connected.",
            "Load": "Click the bus where the load should be connected.",
            "Shunt": "Click the bus where the shunt should be connected.",
            "External Grid": "Click the bus to configure it as the Slack bus."
        }

        self.status.showMessage(instructions[tool])
    # =================================================
    # ACTIONS
    # =================================================

    def create_actions(self):

        self.open_action = QAction("Import MATPOWER", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(self.load_case)

        self.new_action = QAction("New Network", self)
        self.new_action.setShortcut("Ctrl+N")
        self.new_action.triggered.connect(self.new_network)

        self.save_action = QAction("Save Project", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_project)

        self.exit_action = QAction("Exit", self)
        self.exit_action.triggered.connect(self.close)

        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.setEnabled(False)

        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut("Ctrl+Y")
        self.redo_action.setEnabled(False)

        self.check_action = QAction("Check Network", self)
        self.check_action.setShortcut("Ctrl+K")
        self.check_action.triggered.connect(self.check_network)

        self.run_action = QAction("Run Newton-Raphson", self)
        self.run_action.setShortcut("F5")
        self.run_action.setEnabled(False)
        self.run_action.triggered.connect(self.run_solver)

        self.fit_action = QAction("Zoom to Fit", self)
        self.fit_action.setShortcut("F")
        self.fit_action.triggered.connect(
            self.diagram.fit_diagram
        )

        self.show_results_action = QAction("Show Results", self)
        self.show_results_action.triggered.connect(
            lambda: self.results_dock.show()
        )

        self.about_action = QAction("About", self)
        self.about_action.triggered.connect(self.show_about)

        self.delete_action = QAction("Delete Element", self)
        self.delete_action.setShortcut("Delete")
        self.delete_action.triggered.connect(self.delete_element)
    def delete_element(self):
        if self.network is None:
            return

        self.diagram.delete_selected()
        self.invalidate_results()
        
    def invalidate_results(self):
        self.results = None
        self.clear_results()

        if self.network is not None:
            self.run_action.setEnabled(True)
            self.status.showMessage("Network modified | Results invalidated")
    # =================================================
    # CENTRAL CANVAS
    # =================================================

    def create_central_canvas(self):

        self.diagram = NetworkDiagram()

        self.diagram.setMinimumSize(500, 400)

        self.diagram.element_selected.connect(
            self.show_element_properties
        )

        self.diagram.network_modified.connect(
            self.invalidate_results
        )

        self.setCentralWidget(self.diagram)

    # =================================================
    # ELEMENT PALETTE
    # =================================================

    def create_palette_dock(self):

        dock = QDockWidget("Element Palette", self)
        dock.setObjectName("ElementPalette")

        dock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea |
            Qt.DockWidgetArea.RightDockWidgetArea
        )

        widget = QWidget()
        layout = QVBoxLayout(widget)

        description = QLabel("Network Elements")
        description.setStyleSheet("font-weight: bold;")

        # Create the palette first
        self.element_palette = ElementPalette()

        self.element_palette.addItems([
            "Select",
            "Bus",
            "Transmission Line",
            "Transformer",
            "Generator",
            "Load",
            "Shunt",
            "External Grid"
        ])

        # Enable dragging
        self.element_palette.setDragEnabled(True)

        self.element_palette.currentTextChanged.connect(
            self.activate_tool
        )

        layout.addWidget(description)
        layout.addWidget(self.element_palette)

        dock.setWidget(widget)

        self.addDockWidget(
            Qt.DockWidgetArea.LeftDockWidgetArea,
            dock
        )

        self.palette_dock = dock
    # =================================================
    # PROPERTIES PANEL
    # =================================================

    def create_properties_dock(self):

        dock = QDockWidget("Properties", self)
        dock.setObjectName("PropertiesDock")

        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.property_title = QLabel("No element selected")
        self.property_title.setStyleSheet(
            "font-weight: bold; font-size: 14px;"
        )

        self.property_form = QFormLayout()

        self.property_name = QLineEdit()
        self.property_id = QLineEdit()
        self.property_type = QLineEdit()

        for field in (
            self.property_name,
            self.property_id,
            self.property_type
        ):
            field.setReadOnly(True)

        self.property_form.addRow("Name:", self.property_name)
        self.property_form.addRow("ID:", self.property_id)
        self.property_form.addRow("Type:", self.property_type)

        # Editable specifications
        self.property_edit_form = QFormLayout()
        self.property_inputs = {}
        self.selected_element = None

        self.property_message = QLabel(
            "Select an element to view its properties."
        )
        self.property_message.setWordWrap(True)

        self.apply_properties_button = QPushButton("Apply Changes")
        self.apply_properties_button.clicked.connect(
            self.apply_element_properties
        )
        self.apply_properties_button.setEnabled(False)

        layout.addWidget(self.property_title)
        layout.addLayout(self.property_form)
        layout.addLayout(self.property_edit_form)
        layout.addWidget(self.property_message)
        layout.addWidget(self.apply_properties_button)
        layout.addStretch()

        dock.setWidget(widget)

        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea,
            dock
        )

        self.properties_dock = dock
        
    def show_element_properties(self, element):

        if isinstance(element, dict) and "error" in element:
            QMessageBox.warning(self, "Editor", element["error"])
            return

        self.selected_element = element
        self.property_inputs = {}

        while self.property_edit_form.rowCount():
            self.property_edit_form.removeRow(0)

        if element is None:

            self.property_title.setText("No element selected")
            self.property_name.clear()
            self.property_id.clear()
            self.property_type.clear()

            self.property_message.setText(
                "Select an element to view its properties."
            )

            self.apply_properties_button.setEnabled(False)
            return

        element_type = type(element).__name__

        def add_field(label, key, value):
            field = QLineEdit(str(value))
            self.property_inputs[key] = field
            self.property_edit_form.addRow(label, field)

        self.property_title.setText(f"{element_type} Properties")
        self.apply_properties_button.setEnabled(True)

        self.property_message.setText(
            "Edit the specifications and click Apply Changes."
        )

        # ---------------- BUS ----------------

        if element_type == "Bus":

            self.property_name.setText(
                element.name or f"Bus {element.bus_id}"
            )
            self.property_id.setText(str(element.bus_id))
            self.property_type.setText(element.bus_type)

            add_field("Bus Type", "bus_type", element.bus_type)
            add_field("Voltage Magnitude (pu)", "voltage_mag_pu",
                    element.voltage_mag_pu)
            add_field("Voltage Angle (rad)", "voltage_angle_rad",
                    element.voltage_angle_rad)

        # ---------------- GENERATOR ----------------

        elif element_type == "Generator":

            self.property_name.setText(
                f"Generator at Bus {element.bus_id}"
            )
            self.property_id.setText(str(element.bus_id))
            self.property_type.setText("Generator")

            add_field("Active Power (MW)", "p_mw", element.p_mw)
            add_field("Reactive Power (MVAr)", "q_mvar", element.q_mvar)
            add_field("Minimum Q (MVAr)", "q_min_mvar", element.q_min_mvar)
            add_field("Maximum Q (MVAr)", "q_max_mvar", element.q_max_mvar)
            add_field("Voltage Setpoint (pu)", "voltage_setpoint_pu",
                    element.voltage_setpoint_pu)

        # ---------------- LOAD ----------------

        elif element_type == "Load":

            self.property_name.setText(f"Load at Bus {element.bus_id}")
            self.property_id.setText(str(element.bus_id))
            self.property_type.setText("Load")

            add_field("Active Power (MW)", "p_mw", element.p_mw)
            add_field("Reactive Power (MVAr)", "q_mvar", element.q_mvar)

        # ---------------- LINE ----------------

        elif element_type == "Line":

            self.property_name.setText(
                f"Line: Bus {element.from_bus} - Bus {element.to_bus}"
            )
            self.property_id.setText(
                f"{element.from_bus} - {element.to_bus}"
            )
            self.property_type.setText("Transmission Line")

            add_field("Resistance (pu)", "r_pu", element.r_pu)
            add_field("Reactance (pu)", "x_pu", element.x_pu)
            add_field("Shunt Susceptance (pu)", "b_pu", element.b_pu)
            add_field("Rating (MVA)", "rate_mva", element.rate_mva)

        # ---------------- TRANSFORMER ----------------

        elif element_type == "Transformer":

            self.property_name.setText(
                f"Transformer: Bus {element.from_bus} - Bus {element.to_bus}"
            )
            self.property_id.setText(
                f"{element.from_bus} - {element.to_bus}"
            )
            self.property_type.setText("Transformer")

            add_field("Resistance (pu)", "r_pu", element.r_pu)
            add_field("Reactance (pu)", "x_pu", element.x_pu)
            add_field("Shunt Susceptance (pu)", "b_pu", element.b_pu)
            add_field("Tap Ratio", "tap_ratio", element.tap_ratio)
            add_field("Phase Shift (deg)", "phase_shift_deg",
                    element.phase_shift_deg)
            add_field("Rating (MVA)", "rate_mva", element.rate_mva)

        # ---------------- SHUNT ----------------

        elif element_type == "Shunt":

            self.property_name.setText(f"Shunt at Bus {element.bus_id}")
            self.property_id.setText(str(element.bus_id))
            self.property_type.setText("Shunt")

            add_field("Conductance (pu)", "g_pu", element.g_pu)
            add_field("Susceptance (pu)", "b_pu", element.b_pu)

        else:

            self.property_name.setText(element_type)
            self.property_id.clear()
            self.property_type.setText(element_type)

            self.property_message.setText(
                "No editor is available for this element."
            )

            self.apply_properties_button.setEnabled(False)
            
    def apply_element_properties(self):

        element = self.selected_element

        if element is None:
            return

        element_type = type(element).__name__

        try:

            values = {
                key: field.text().strip()
                for key, field in self.property_inputs.items()
            }

            # Convert all editable values to numbers,
            # except Bus Type.
            numeric_values = {}

            for key, value in values.items():

                if key == "bus_type":
                    continue

                numeric_values[key] = float(value)

            if not all(math.isfinite(v) for v in numeric_values.values()):
                raise ValueError("All numeric properties must be finite")

            # ---------------- BUS ----------------

            if element_type == "Bus":

                bus_type = values["bus_type"].upper()

                if bus_type not in ("PQ", "PV", "SLACK"):
                    raise ValueError(
                        "Bus type must be PQ, PV or Slack."
                    )

                if bus_type == "SLACK":
                    bus_type = "Slack"
                elif bus_type == "PV":
                    bus_type = "PV"
                else:
                    bus_type = "PQ"

                voltage = numeric_values["voltage_mag_pu"]
                angle = numeric_values["voltage_angle_rad"]

                if voltage <= 0:
                    raise ValueError("Voltage must be positive.")

                element.bus_type = bus_type
                element.voltage_mag_pu = voltage
                element.voltage_angle_rad = angle

            # ---------------- GENERATOR ----------------

            elif element_type == "Generator":

                p = numeric_values["p_mw"]
                q = numeric_values["q_mvar"]
                q_min = numeric_values["q_min_mvar"]
                q_max = numeric_values["q_max_mvar"]
                voltage = numeric_values["voltage_setpoint_pu"]

                if q_min > q_max:
                    raise ValueError(
                        "Minimum Q cannot exceed maximum Q."
                    )

                if voltage <= 0:
                    raise ValueError(
                        "Voltage setpoint must be positive."
                    )

                element.p_mw = p
                element.q_mvar = q
                element.q_min_mvar = q_min
                element.q_max_mvar = q_max
                element.voltage_setpoint_pu = voltage

                # Update corresponding PV bus voltage.
                for bus in self.network.buses:

                    if (
                        bus.bus_id == element.bus_id
                        and bus.bus_type in ("PV", "Slack")
                    ):
                        bus.voltage_mag_pu = voltage

            # ---------------- LOAD ----------------

            elif element_type == "Load":

                element.p_mw = numeric_values["p_mw"]
                element.q_mvar = numeric_values["q_mvar"]

            # ---------------- LINE ----------------

            elif element_type == "Line":

                if numeric_values["r_pu"] == 0 and numeric_values["x_pu"] == 0:
                    raise ValueError("Line impedance R+jX cannot be zero")
                if numeric_values["rate_mva"] < 0:
                    raise ValueError("Line rating cannot be negative")
                element.r_pu = numeric_values["r_pu"]
                element.x_pu = numeric_values["x_pu"]
                element.b_pu = numeric_values["b_pu"]
                element.rate_mva = numeric_values["rate_mva"]

            # ---------------- TRANSFORMER ----------------

            elif element_type == "Transformer":

                tap_ratio = numeric_values["tap_ratio"]

                if tap_ratio <= 0:
                    raise ValueError(
                        "Transformer tap ratio must be positive."
                    )

                if numeric_values["r_pu"] == 0 and numeric_values["x_pu"] == 0:
                    raise ValueError("Transformer impedance R+jX cannot be zero")
                if numeric_values["rate_mva"] < 0:
                    raise ValueError("Transformer rating cannot be negative")
                element.r_pu = numeric_values["r_pu"]
                element.x_pu = numeric_values["x_pu"]
                element.b_pu = numeric_values["b_pu"]
                element.tap_ratio = tap_ratio
                element.phase_shift_deg = numeric_values["phase_shift_deg"]
                element.rate_mva = numeric_values["rate_mva"]

            # ---------------- SHUNT ----------------

            elif element_type == "Shunt":

                element.g_pu = numeric_values["g_pu"]
                element.b_pu = numeric_values["b_pu"]

            # Invalidate previous results.
            self.invalidate_results()

            # Refresh diagram and properties.
            self.diagram.refresh()
            self.show_element_properties(element)

            self.status.showMessage(
                "Component specifications updated.",
                4000
            )

        except ValueError as error:

            QMessageBox.warning(
                self,
                "Invalid Specifications",
                str(error)
            )
    # =================================================
    # RESULTS DOCK
    # =================================================

    def create_results_dock(self):

        self.results_dock = QDockWidget("Study Results", self)
        self.results_dock.setObjectName("ResultsDock")

        self.results_tabs = QTabWidget()

        self.bus_table = ResultsTable()
        self.branch_table = ResultsTable()
        self.generator_table = ResultsTable()
        self.summary_table = ResultsTable()
        self.history_table = ResultsTable()
        self.violations_table = ResultsTable()

        self.results_tabs.addTab(
            self.bus_table, "Bus Results"
        )

        self.results_tabs.addTab(
            self.branch_table, "Branch Results"
        )

        self.results_tabs.addTab(
            self.generator_table, "Generators"
        )

        self.results_tabs.addTab(
            self.violations_table, "Violations"
        )

        self.results_tabs.addTab(
            self.history_table, "Iteration Log"
        )

        self.results_tabs.addTab(
            self.summary_table, "System Summary"
        )

        self.results_dock.setWidget(self.results_tabs)

        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea,
            self.results_dock
        )

        self.results_dock.setMinimumHeight(190)

    # =================================================
    # MENUS
    # =================================================

    def create_menus(self):

        menu = self.menuBar()

        file_menu = menu.addMenu("File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.save_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        edit_menu = menu.addMenu("Edit")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addAction(self.delete_action)

        view_menu = menu.addMenu("View")
        view_menu.addAction(self.fit_action)
        view_menu.addAction(self.show_results_action)

        view_menu.addAction(
            self.palette_dock.toggleViewAction()
        )

        view_menu.addAction(
            self.properties_dock.toggleViewAction()
        )

        view_menu.addAction(
            self.results_dock.toggleViewAction()
        )

        network_menu = menu.addMenu("Network")
        network_menu.addAction(self.check_action)

        study_menu = menu.addMenu("Study")
        study_menu.addAction(self.run_action)

        results_menu = menu.addMenu("Results")
        results_menu.addAction(self.show_results_action)

        help_menu = menu.addMenu("Help")
        help_menu.addAction(self.about_action)

    # =================================================
    # TOOLBAR
    # =================================================

    def create_toolbar(self):

        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)

        self.addToolBar(toolbar)

        actions = [
            self.new_action,
            self.open_action,
            self.undo_action,
            self.redo_action,
            self.check_action,
            self.run_action,
            self.fit_action,
            self.show_results_action
        ]

        for action in actions:
            toolbar.addAction(action)

    # =================================================
    # STATUS BAR
    # =================================================

    def create_status_bar(self):

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.status.showMessage(
            "Ready | No network loaded | System base: -- MVA"
        )

    # =================================================
    # NETWORK OPERATIONS
    # =================================================

    def load_case(self):

        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Import MATPOWER Case",
            "",
            "MATPOWER Files (*.m)"
        )

        if not filepath:
            return

        try:

            network = load_matpower_case(filepath)
            network.validate()

            self.network = network
            self.results = None
            self.case_path = filepath

            self.diagram.draw_network(network)

            self.clear_results()

            self.run_action.setEnabled(True)

            self.status.showMessage(
                f"Loaded {Path(filepath).name} | "
                f"{len(network.buses)} buses | "
                f"Base: {network.base_mva} MVA"
            )

            self.results_dock.show()

        except Exception as error:

            QMessageBox.critical(
                self, "Import Error", str(error)
            )

    def new_network(self):

        reply = QMessageBox.question(
            self,
            "New Network",
            "Start a new network? Current unsaved work will be lost.",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.network = Network()
        self.results = None
        self.case_path = None

        self.diagram.draw_network(self.network)

        self.clear_results()

        self.run_action.setEnabled(True)

        self.status.showMessage(
            "New network | Add buses using the element palette"
        )

    def save_project(self):

        QMessageBox.information(
            self,
            "Save Project",
            "Native project saving will be implemented in the project-file stage."
        )

    # =================================================
    # NETWORK VALIDATION
    # =================================================

    def check_network(self):

        if self.network is None:

            QMessageBox.warning(
                self, "Network Check", "No network loaded."
            )

            return

        try:

            self.network.validate()

            QMessageBox.information(
                self,
                "Network Check",
                "Network validation passed."
            )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Network Check Failed",
                str(error)
            )

    # =================================================
    # NEWTON-RAPHSON SOLVER
    # =================================================

    def run_solver(self):

        if self.network is None:
            return

        try:
            self.network.validate()

        except Exception as error:

            QMessageBox.warning(
                self, "Invalid Network", str(error)
            )

            return

        self.run_action.setEnabled(False)

        self.status.showMessage(
            "Newton-Raphson calculation running..."
        )

        QApplication.processEvents()

        try:

            self.results = solve_newton_raphson(
                self.network,
                tolerance=self.tolerance,
                max_iterations=self.max_iterations
            )

            self.display_results()

        except Exception as error:

            QMessageBox.critical(
                self, "Solver Error", str(error)
            )

        finally:

            self.run_action.setEnabled(True)

    # =================================================
    # DISPLAY RESULTS
    # =================================================

    def display_results(self):

        r = self.results

        if not r:
            return

        self.diagram.draw_network(self.network, r)

        if not r.get("converged", False):

            self.status.showMessage(
                f"NOT CONVERGED | Iterations: {r.get('iterations', 0)}"
            )

            self.display_history()

            QMessageBox.warning(
                self,
                "Load Flow",
                "Newton-Raphson did not converge. Check the iteration log."
            )

            return

        self.display_bus_results()
        self.display_branch_results()
        self.display_generator_results()
        self.display_history()
        self.display_summary()

        self.status.showMessage(
            f"CONVERGED | Iterations: {r['iterations']} | "
            f"Base: {self.network.base_mva} MVA"
        )

        self.results_dock.show()

    # =================================================
    # BUS RESULTS
    # =================================================

    def display_bus_results(self):

        rows = []
        r = self.results

        for i, bus in enumerate(self.network.buses):

            rows.append([
                bus.bus_id,
                r.get("effective_bus_types", {}).get(bus.bus_id, bus.bus_type),
                r["voltage_mag"][i],
                r["voltage_angle"][i] * 180 / 3.141592653589793,
                r["P_calc"][i] * self.network.base_mva,
                r["Q_calc"][i] * self.network.base_mva
            ])

        self.bus_table.set_data(
            [
                "Bus",
                "Type",
                "V (pu)",
                "Angle (deg)",
                "P Injection (MW)",
                "Q Injection (MVAr)"
            ],
            rows
        )

    # =================================================
    # BRANCH RESULTS
    # =================================================

    def display_branch_results(self):

        rows = []

        for branch in self.results.get("branch_flows", []):

            rows.append([
                branch["element_type"],
                branch["from_bus"],
                branch["to_bus"],
                branch["P_from_mw"],
                branch["Q_from_mvar"],
                branch["P_to_mw"],
                branch["Q_to_mvar"],
                branch["P_loss_mw"],
                branch["Q_loss_mvar"],
                branch["loading_percent"]
            ])

        self.branch_table.set_data(
            [
                "Type",
                "From",
                "To",
                "P From",
                "Q From",
                "P To",
                "Q To",
                "P Loss",
                "Q Loss",
                "Loading %"
            ],
            rows
        )

    # =================================================
    # GENERATOR RESULTS
    # =================================================

    def display_generator_results(self):

        rows = []

        for generator in self.results.get(
            "generator_outputs", []
        ):

            rows.append([
                generator["bus_id"],
                generator.get("source_type", "Generator"),
                generator["generator_count"],
                generator["P_generation_mw"],
                generator["Q_generation_mvar"]
            ])

        self.generator_table.set_data(
            [
                "Bus",
                "Source",
                "Count",
                "P Generation (MW)",
                "Q Generation (MVAr)"
            ],
            rows
        )

    # =================================================
    # ITERATION HISTORY
    # =================================================

    def display_history(self):

        rows = []

        for item in self.results.get("history", []):

            if isinstance(item, dict):

                rows.append([
                    item.get("stage", ""),
                    item.get("stage_iteration", ""),
                    item.get("total_iterations", ""),
                    item.get("max_mismatch", "")
                ])

            else:
                rows.append([str(item)])

        self.history_table.set_data(
            [
                "Stage",
                "Stage Iteration",
                "Total Iterations",
                "Maximum Mismatch"
            ],
            rows
        )

    # =================================================
    # SYSTEM SUMMARY
    # =================================================

    def display_summary(self):

        summary = self.results.get(
            "system_summary", {}
        )

        rows = [
            ["Generation (MW)", summary.get("P_generation_mw")],
            ["Generation (MVAr)", summary.get("Q_generation_mvar")],
            ["Load (MW)", summary.get("P_load_mw")],
            ["Load (MVAr)", summary.get("Q_load_mvar")],
            ["Branch Active Loss (MW)", summary.get("P_branch_loss_mw")],
            ["Branch Reactive Loss (MVAr)", summary.get("Q_branch_loss_mvar")],
            ["Total Active Loss (MW)", summary.get("P_loss_mw")],
            ["Total Reactive Loss (MVAr)", summary.get("Q_loss_mvar")],
            ["Power Balance Check", summary.get("power_balance_ok")]
        ]

        self.summary_table.set_data(
            ["Parameter", "Value"],
            rows
        )

    # =================================================
    # CLEAR RESULTS
    # =================================================

    def clear_results(self):

        tables = [
            self.bus_table,
            self.branch_table,
            self.generator_table,
            self.summary_table,
            self.history_table,
            self.violations_table
        ]

        for table in tables:
            table.set_data([], [])

    # =================================================
    # KEYBOARD SHORTCUTS
    # =================================================

    def keyPressEvent(self, event):

        if event.key() == Qt.Key.Key_Delete:
            self.delete_element()
            return

        if event.key() == Qt.Key.Key_Escape:
            self.diagram.set_mode("select")
            self.palette.clearSelection()
            return

        super().keyPressEvent(event)

    # =================================================
    # ABOUT
    # =================================================

    def show_about(self):

        QMessageBox.about(
            self,
            "About",
            "E4234 Power System Analysis\n"
            "Newton-Raphson Load Flow Simulator\n"
            "Built using Python and PySide6"
        )

    # =================================================
    # STYLE
    # =================================================

    def apply_style(self):

        self.setStyleSheet("""
            QMainWindow {
                background: #20242b;
            }

            QDockWidget {
                color: #ffffff;
                font-weight: bold;
            }

            QDockWidget::title {
                background: #303641;
                padding: 7px;
            }

            QWidget {
                color: #e5e7eb;
            }

            QTableWidget {
                background: #252a33;
                alternate-background-color: #2d333d;
                gridline-color: #424955;
            }

            QHeaderView::section {
                background: #343b47;
                padding: 5px;
                border: 1px solid #424955;
            }

            QListWidget {
                background: #252a33;
                border: none;
            }

            QToolBar {
                background: #303641;
                spacing: 6px;
                padding: 5px;
            }

            QStatusBar {
                background: #303641;
            }
        """)


# =====================================================
# APPLICATION ENTRY POINT
# =====================================================

def main():

    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
