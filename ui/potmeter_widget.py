from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, pyqtSignal, QPointF
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor
import math

class Potmeter(QWidget):
    valueChanged = pyqtSignal(int)  # Signal emitted when the value changes

    def __init__(self, min_value=0, max_value=100, initial_value=50, parent=None):
        super().__init__(parent)
        self.min_value = min_value
        self.max_value = max_value
        self.value = initial_value
        self.setMinimumSize(50, 50)  # Minimum size of the potmeter

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw the outer circle
        radius = min(self.width(), self.height()) // 2 - 5
        center = self.rect().center()
        painter.setBrush(QBrush(QColor(200, 200, 200)))
        painter.setPen(QPen(Qt.NoPen))
        painter.drawEllipse(center, radius, radius)

        # Draw the indicator line
        angle = self.value_to_angle(self.value)
        line_length = radius - 10
        x = center.x() + line_length * math.cos(math.radians(angle))
        y = center.y() - line_length * math.sin(math.radians(angle))
        painter.setPen(QPen(QColor(50, 50, 50), 3))
        painter.drawLine(center, QPointF(x, y))

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.update_value_from_position(event.pos())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.update_value_from_position(event.pos())

    def update_value_from_position(self, pos):
        center = self.rect().center()
        dx = pos.x() - center.x()
        dy = center.y() - pos.y()
        angle = math.degrees(math.atan2(dy, dx))
        if angle < 0:
            angle += 360

        # Map the angle to the value range
        new_value = self.angle_to_value(angle)
        if new_value != self.value:
            self.value = new_value
            self.valueChanged.emit(self.value)
            self.update()

    def value_to_angle(self, value):
        """Convert a value to an angle (0-360 degrees)."""
        return 135 + (value - self.min_value) / (self.max_value - self.min_value) * 270

    def angle_to_value(self, angle):
        """Convert an angle (0-360 degrees) to a value."""
        if angle < 135 or angle > 405:
            return self.value  # Ignore angles outside the valid range
        normalized_angle = (angle - 135) % 360
        return int(self.min_value + normalized_angle / 270 * (self.max_value - self.min_value))
