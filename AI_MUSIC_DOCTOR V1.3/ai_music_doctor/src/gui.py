
"""
AI Music Doctor - Professional Hardware-Style GUI
Version: 4.1.0

Features:
- Orange/copper hardware aesthetic (T-RackS One style)
- All mastering knobs: Air, Body, Focus, Push, Width, Volume, Transients, Analog, Bass Punch
- REVERB with 4 types: Plate, Hall, Room, Chamber (max 60% wet)
- DENOISER with 6 glowing orbit buttons (Boomy, Boxy, Muddy, Honky, Harsh, Sizzle)
- Artifact-free EQ with ±2.4dB max
- Neve-style processing throughout (soft-knee saturation, even harmonics)
- Proper bypass functionality
- Spectrum analyzer
"""

import sys
import os
import math
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QComboBox, QSlider,
                             QFileDialog, QProgressBar, QGroupBox, QGridLayout,
                             QMessageBox, QDialog, QFrame, QSplitter,
                             QScrollArea, QSizePolicy, QSpacerItem)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QRectF, QPointF
from PyQt5.QtGui import (QFont, QPalette, QColor, QPainter, QBrush, QPen, 
                         QLinearGradient, QRadialGradient, QConicalGradient,
                         QPainterPath, QFontMetrics)
import numpy as np
from pathlib import Path

from audio_processor import AudioProcessor, StreamingExporter
from presets import PresetManager

try:
    from audio_analyzer import AudioAnalyzer, AnalysisResult, IssueLevel
    ANALYZER_AVAILABLE = True
except ImportError:
    ANALYZER_AVAILABLE = False

try:
    from realtime_engine import RealTimeAudioEngine, ProcessingParameters, SOUNDDEVICE_AVAILABLE
    REALTIME_AVAILABLE = SOUNDDEVICE_AVAILABLE
except ImportError:
    REALTIME_AVAILABLE = False
    print("Warning: Real-time engine not available")


# Color palette
COLORS = {
    'background': '#1a1a1a',
    'panel': '#2d2d2d',
    'copper': '#b87333',
    'copper_light': '#d4955c',
    'copper_dark': '#8c5a2a',
    'brass': '#c9a227',
    'knob': '#1a1a1a',
    'knob_ring': '#333333',
    'marker': '#ffffff',
    'text': '#e0e0e0',
    'text_dim': '#888888',
    'meter_green': '#00ff00',
    'meter_yellow': '#ffff00',
    'meter_red': '#ff0000',
    'spectrum_green': '#44ff44',
    'spectrum_yellow': '#ffff44',
    'eq_line': '#00ffff',
    'eq_point': '#ff6600',
    'orbit_glow': '#ff8800',
    'orbit_inactive': '#333333',
    'orbit_active': '#ff6600',
}


class HardwareKnob(QWidget):
    """Custom hardware-style rotary knob (compact)
    
    Emits valueChanged during dragging (for real-time audio updates)
    Emits valueChangeFinished on mouse release (for undo state save)
    """
    valueChanged = pyqtSignal(float)
    valueChangeFinished = pyqtSignal(float)  # Emitted on mouse release for undo save
    
    def __init__(self, label: str, min_val: float = 0, max_val: float = 100,
                 default: float = 0, unit: str = "", decimals: int = 0,
                 parent=None):
        super().__init__(parent)
        self.label = label
        self.min_val = min_val
        self.max_val = max_val
        self.value = default
        self.unit = unit
        self.decimals = decimals
        self.dragging = False
        self.last_y = 0
        self._start_value = default  # Track value at drag start
        
        self.setMinimumSize(58, 80)
        self.setMaximumSize(90, 110)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()

        # Keep a guaranteed text area at the bottom so value/label never overlap the knob
        label_height = 18
        value_height = 12
        text_bottom_padding = 2
        knob_top_padding = 12

        text_block_top = h - (label_height + value_height + text_bottom_padding)
        max_knob_bottom = text_block_top - 9  # leave room for LED under the knob

        knob_size = min(w - 18, max_knob_bottom - knob_top_padding)
        knob_size = max(24, knob_size)

        knob_x = (w - knob_size) // 2
        knob_y = knob_top_padding

        center_x = w // 2
        center_y = knob_y + knob_size // 2
        tick_radius = knob_size // 2 + 7

        # Normalized position (0..1)
        norm_value = (self.value - self.min_val) / (self.max_val - self.min_val)
        norm_value = max(0.0, min(1.0, norm_value))

        # Tick marks
        painter.setPen(QPen(QColor(COLORS['text_dim']), 1))
        for i in range(11):
            angle = math.radians(225 - i * 27)
            x1 = center_x + tick_radius * math.cos(angle)
            y1 = center_y - tick_radius * math.sin(angle)
            x2 = center_x + (tick_radius - 4) * math.cos(angle)
            y2 = center_y - (tick_radius - 4) * math.sin(angle)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # Base arc track (dark ring)
        arc_rect = QRectF(knob_x - 6, knob_y - 6, knob_size + 12, knob_size + 12)
        arc_start_deg = 225.0
        arc_span_total = 270.0
        qt_arc_start = int((90 - arc_start_deg) * 16)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor('#2c2c2c'), 4, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(arc_rect, qt_arc_start, int(-arc_span_total * 16))

        # Value-dependent color ring (GUI-style feedback)
        has_zero_center = self.min_val < 0 < self.max_val
        zero_norm = (0 - self.min_val) / (self.max_val - self.min_val) if has_zero_center else 0.0

        def blend_color(c1: str, c2: str, t: float) -> QColor:
            t = max(0.0, min(1.0, t))
            a = QColor(c1)
            b = QColor(c2)
            return QColor(
                int(a.red() + (b.red() - a.red()) * t),
                int(a.green() + (b.green() - a.green()) * t),
                int(a.blue() + (b.blue() - a.blue()) * t)
            )

        color_pen = None
        span_deg = 0.0
        arc_start_deg_value = arc_start_deg

        if has_zero_center:
            if norm_value >= zero_norm:
                magnitude = 0.0 if (1.0 - zero_norm) <= 1e-9 else (norm_value - zero_norm) / (1.0 - zero_norm)
                color_pen = blend_color('#ff8a00', '#ffe066', magnitude)  # orange -> yellow
                arc_start_deg_value = 225.0 - zero_norm * 270.0
                span_deg = -(norm_value - zero_norm) * 270.0
            else:
                magnitude = 0.0 if zero_norm <= 1e-9 else (zero_norm - norm_value) / zero_norm
                color_pen = blend_color('#2d9cff', '#66e0ff', magnitude)  # blue -> cyan
                arc_start_deg_value = 225.0 - zero_norm * 270.0
                span_deg = (zero_norm - norm_value) * 270.0
        else:
            magnitude = norm_value
            color_pen = blend_color('#ff8a00', '#ffe066', magnitude)  # orange -> yellow
            arc_start_deg_value = arc_start_deg
            span_deg = -norm_value * 270.0

        if abs(span_deg) > 0.1:
            qt_value_start = int((90 - arc_start_deg_value) * 16)
            painter.setPen(QPen(color_pen, 4, Qt.SolidLine, Qt.RoundCap))
            painter.drawArc(arc_rect, qt_value_start, int(span_deg * 16))

            # Subtle glow for active arc
            glow = QColor(color_pen)
            glow.setAlpha(70)
            painter.setPen(QPen(glow, 7, Qt.SolidLine, Qt.RoundCap))
            painter.drawArc(arc_rect, qt_value_start, int(span_deg * 16))

        # Outer ring
        ring_gradient = QRadialGradient(center_x, center_y, knob_size // 2 + 3)
        ring_gradient.setColorAt(0.8, QColor(COLORS['copper']))
        ring_gradient.setColorAt(1.0, QColor(COLORS['copper_dark']))
        painter.setBrush(QBrush(ring_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(knob_x - 2, knob_y - 2, knob_size + 4, knob_size + 4)

        # Knob body
        knob_gradient = QRadialGradient(center_x - 3, center_y - 3, knob_size)
        knob_gradient.setColorAt(0, QColor('#3a3a3a'))
        knob_gradient.setColorAt(0.5, QColor('#1a1a1a'))
        knob_gradient.setColorAt(1, QColor('#0a0a0a'))
        painter.setBrush(QBrush(knob_gradient))
        painter.drawEllipse(knob_x, knob_y, knob_size, knob_size)

        # Position marker
        angle = math.radians(225 - norm_value * 270)
        marker_inner = knob_size // 4
        marker_outer = knob_size // 2 - 3

        x1 = center_x + marker_inner * math.cos(angle)
        y1 = center_y - marker_inner * math.sin(angle)
        x2 = center_x + marker_outer * math.cos(angle)
        y2 = center_y - marker_outer * math.sin(angle)

        painter.setPen(QPen(QColor(COLORS['marker']), 2, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # LED indicator
        led_y = knob_y + knob_size + 4
        led_color = QColor(COLORS['meter_green']) if norm_value > 0.01 else QColor('#003300')
        painter.setBrush(QBrush(led_color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center_x - 3, led_y, 6, 6)

        # Label
        painter.setPen(QColor(COLORS['text']))
        font = QFont('Arial', 8, QFont.Bold)
        painter.setFont(font)
        label_y = h - label_height
        painter.drawText(0, label_y, w, label_height, Qt.AlignCenter, self.label)

        # Value
        if self.decimals > 0:
            value_text = f"{self.value:.{self.decimals}f}{self.unit}"
        else:
            value_text = f"{int(self.value)}{self.unit}"

        font = QFont('Arial', 7)
        painter.setFont(font)
        painter.setPen(QColor(COLORS['copper_light']))
        painter.drawText(0, label_y - value_height, w, value_height, Qt.AlignCenter, value_text)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.last_y = event.y()
            self._start_value = self.value  # Remember value at drag start
    
    def mouseReleaseEvent(self, event):
        if self.dragging and self.value != self._start_value:
            # Emit finished signal only if value actually changed
            self.valueChangeFinished.emit(self.value)
        self.dragging = False
    
    def mouseMoveEvent(self, event):
        if self.dragging:
            dy = self.last_y - event.y()
            self.last_y = event.y()
            range_val = self.max_val - self.min_val
            change = dy * range_val / 200
            new_value = max(self.min_val, min(self.max_val, self.value + change))
            if new_value != self.value:
                self.value = new_value
                self.valueChanged.emit(self.value)
                self.update()
    
    def wheelEvent(self, event):
        delta = event.angleDelta().y() / 120
        range_val = self.max_val - self.min_val
        change = delta * range_val / 50
        new_value = max(self.min_val, min(self.max_val, self.value + change))
        if new_value != self.value:
            self.value = new_value
            self.valueChanged.emit(self.value)
            self.update()
    
    def setValue(self, value: float):
        self.value = max(self.min_val, min(self.max_val, value))
        self.update()
    
    def getValue(self) -> float:
        return self.value


class OrbitButton(QWidget):
    """Glowing orbit button for denoiser frequency bands
    
    BUG 3 FIX: Much more dramatic color change when processing is active.
    Goes from subtle orange to bright RED with visible glow aura.
    """
    toggled = pyqtSignal(bool)
    
    def __init__(self, label: str, freq_range: str, parent=None):
        super().__init__(parent)
        self.label = label
        self.freq_range = freq_range
        self.active = True
        self.glow_level = 0.0  # 0.0 to 1.0
        
        self.setMinimumSize(50, 58)
        self.setMaximumSize(68, 72)
        self.setCursor(Qt.PointingHandCursor)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        center_x = w // 2
        center_y = h // 2 - 6
        radius = min(w, h) // 2 - 10
        
        # ENHANCED Glow effect - much more visible (BUG 3 FIX)
        if self.active and self.glow_level > 0.05:
            glow_radius = radius + int(16 * self.glow_level)
            glow_gradient = QRadialGradient(center_x, center_y, glow_radius)
            # Progressively brighter: orange -> red-orange -> bright red
            if self.glow_level > 0.6:
                core_color = QColor('#ff2200')   # Bright red
            elif self.glow_level > 0.3:
                core_color = QColor('#ff5500')   # Red-orange
            else:
                core_color = QColor(COLORS['orbit_glow'])  # Orange
            
            core_color.setAlpha(int(200 * self.glow_level))
            glow_gradient.setColorAt(0.3, core_color)
            core_color.setAlpha(int(120 * self.glow_level))
            glow_gradient.setColorAt(0.6, core_color)
            core_color.setAlpha(0)
            glow_gradient.setColorAt(1.0, core_color)
            painter.setBrush(QBrush(glow_gradient))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(center_x - glow_radius, center_y - glow_radius,
                               glow_radius * 2, glow_radius * 2)
        
        # Button background - dramatic color shift with glow
        if self.active:
            if self.glow_level > 0.5:
                bg_color = QColor('#ff3300')
                bg_color.setAlpha(240)
            elif self.glow_level > 0.2:
                bg_color = QColor('#ff5500')
                bg_color.setAlpha(210)
            else:
                bg_color = QColor(COLORS['orbit_active'])
                bg_color.setAlpha(150 + int(105 * self.glow_level))
        else:
            bg_color = QColor(COLORS['orbit_inactive'])
        
        # Border color intensifies with glow
        if self.active and self.glow_level > 0.3:
            border_color = QColor('#ff4400')
            border_width = 2
        else:
            border_color = QColor(COLORS['copper'])
            border_width = 1
        
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, border_width))
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)
        
        # Inner circle (button depth) - color intensifies with glow
        inner_radius = radius - 2
        inner_gradient = QRadialGradient(center_x - 1, center_y - 1, inner_radius)
        if self.active:
            if self.glow_level > 0.5:
                inner_gradient.setColorAt(0, QColor('#ffbb55'))
                inner_gradient.setColorAt(0.4, QColor('#ff6622'))
                inner_gradient.setColorAt(1, QColor('#ee2200'))
            elif self.glow_level > 0.2:
                inner_gradient.setColorAt(0, QColor('#ff9944'))
                inner_gradient.setColorAt(0.5, QColor('#dd5511'))
                inner_gradient.setColorAt(1, QColor('#bb3300'))
            else:
                inner_gradient.setColorAt(0, QColor('#ff9944'))
                inner_gradient.setColorAt(0.7, QColor('#cc6622'))
                inner_gradient.setColorAt(1, QColor('#aa4400'))
        else:
            inner_gradient.setColorAt(0, QColor('#444444'))
            inner_gradient.setColorAt(1, QColor('#222222'))
        
        painter.setBrush(QBrush(inner_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center_x - inner_radius, center_y - inner_radius,
                           inner_radius * 2, inner_radius * 2)
        
        # Label
        painter.setPen(QColor('#ffffff' if self.active else '#888888'))
        font = QFont('Arial', 6, QFont.Bold)
        painter.setFont(font)
        painter.drawText(0, center_y + radius + 1, w, 13, Qt.AlignCenter, self.label)
        
        # Frequency range (smaller)
        painter.setPen(QColor(COLORS['text_dim']))
        font = QFont('Arial', 5)
        painter.setFont(font)
        painter.drawText(0, center_y + radius + 12, w, 10, Qt.AlignCenter, self.freq_range)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.active = not self.active
            self.toggled.emit(self.active)
            self.update()
    
    def setActive(self, active: bool):
        self.active = active
        self.update()
    
    def setGlowLevel(self, level: float):
        self.glow_level = max(0.0, min(1.0, level))
        self.update()
    
    def isActive(self) -> bool:
        return self.active


class DenoiserWidget(QWidget):
    """Denoiser with horizontal orbit buttons and sensitivity knob"""
    sensitivityChanged = pyqtSignal(float)
    sensitivityChangeFinished = pyqtSignal(float)  # For undo state save
    bandToggled = pyqtSignal(str, bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(68)
        self.setMaximumHeight(80)
        
        layout = QHBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(6, 2, 6, 2)
        
        # Title label (vertical)
        title = QLabel("DENOISER")
        title.setStyleSheet(f"color: {COLORS['copper_light']}; font-weight: bold; font-size: 9px;")
        title.setAlignment(Qt.AlignCenter)
        title.setFixedWidth(52)
        layout.addWidget(title)
        
        # 6 orbit buttons in a single horizontal row
        self.btn_boomy = OrbitButton("BOOMY", "100-250Hz")
        self.btn_boxy = OrbitButton("BOXY", "150-250Hz")
        self.btn_muddy = OrbitButton("MUDDY", "200-500Hz")
        self.btn_honky = OrbitButton("HONKY", "500Hz-1.5kHz")
        self.btn_harsh = OrbitButton("HARSH", "2-6kHz")
        self.btn_sizzle = OrbitButton("SIZZLE", "8-12kHz")
        
        for btn in [self.btn_boomy, self.btn_boxy, self.btn_muddy,
                     self.btn_honky, self.btn_harsh, self.btn_sizzle]:
            layout.addWidget(btn)
        
        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet(f"color: {COLORS['copper']};")
        layout.addWidget(sep)
        
        # Sensitivity knob
        self.knob_sensitivity = HardwareKnob("SENS", 0, 100, 0, "%")
        self.knob_sensitivity.setMinimumSize(58, 62)
        self.knob_sensitivity.setMaximumSize(72, 76)
        layout.addWidget(self.knob_sensitivity)
        
        # Connect signals
        self.knob_sensitivity.valueChanged.connect(self.sensitivityChanged.emit)
        self.knob_sensitivity.valueChangeFinished.connect(self.sensitivityChangeFinished.emit)
        self.btn_boomy.toggled.connect(lambda v: self.bandToggled.emit('boomy', v))
        self.btn_boxy.toggled.connect(lambda v: self.bandToggled.emit('boxy', v))
        self.btn_muddy.toggled.connect(lambda v: self.bandToggled.emit('muddy', v))
        self.btn_honky.toggled.connect(lambda v: self.bandToggled.emit('honky', v))
        self.btn_harsh.toggled.connect(lambda v: self.bandToggled.emit('harsh', v))
        self.btn_sizzle.toggled.connect(lambda v: self.bandToggled.emit('sizzle', v))
    
    def setGlowLevels(self, levels: dict):
        """Update glow levels for orbit buttons"""
        if 'boomy' in levels:
            self.btn_boomy.setGlowLevel(levels['boomy'])
        if 'boxy' in levels:
            self.btn_boxy.setGlowLevel(levels['boxy'])
        if 'muddy' in levels:
            self.btn_muddy.setGlowLevel(levels['muddy'])
        if 'honky' in levels:
            self.btn_honky.setGlowLevel(levels['honky'])
        if 'harsh' in levels:
            self.btn_harsh.setGlowLevel(levels['harsh'])
        if 'sizzle' in levels:
            self.btn_sizzle.setGlowLevel(levels['sizzle'])
    
    def getSensitivity(self) -> float:
        return self.knob_sensitivity.getValue()
    
    def getBandStates(self) -> dict:
        return {
            'boomy': self.btn_boomy.isActive(),
            'boxy': self.btn_boxy.isActive(),
            'muddy': self.btn_muddy.isActive(),
            'honky': self.btn_honky.isActive(),
            'harsh': self.btn_harsh.isActive(),
            'sizzle': self.btn_sizzle.isActive(),
        }


class SpectrumAnalyzer(QWidget):
    """Classic LED-style spectrum analyzer with segmented bars and color gradient
    
    FIXED v4.1: Better visibility with lower dB floor and makeup gain
    FIXED v4.0: Bars now fill entire display width
    """
    
    # dB range for display - WIDENED for better visibility
    DB_MIN = -80.0  # Minimum dB level (silence) - lowered from -60
    DB_MAX = 6.0    # Maximum dB level (above full scale for headroom)
    
    # Number of LED segments per bar
    NUM_SEGMENTS = 24  # Increased for smoother display
    
    # Number of frequency bands - reduced for wider bars that fill the display
    NUM_BANDS = 24  # Reduced from 32 for better visual fill
    
    # Makeup gain to boost signal display
    MAKEUP_GAIN_DB = 20.0  # Boost spectrum by 20dB for better visibility
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.spectrum = np.zeros(self.NUM_BANDS)
        self.peaks = np.zeros(self.NUM_BANDS)
        self.peak_hold_counters = np.zeros(self.NUM_BANDS)
        self.smoothed_spectrum = np.zeros(self.NUM_BANDS)
        self.setMinimumSize(400, 90)
        self.setMaximumHeight(150)
        
        # Smoothing factor (0 = instant, 1 = no change) - FASTER response
        self.attack_smooth = 0.15   # Faster attack for snappier response
        self.release_smooth = 0.85  # Faster release to show dynamics better
        
        # Peak hold time (in update cycles, ~50ms each)
        self.peak_hold_time = 15  # Slightly shorter for more dynamic display
        self.peak_decay_rate = 0.8  # Faster decay for snappier peaks
    
    def _get_segment_color(self, segment_idx: int, total_segments: int) -> QColor:
        """Get color for a segment based on its position (bottom=green, top=red)"""
        ratio = segment_idx / total_segments
        
        if ratio < 0.5:
            # Green to Yellow (bottom half)
            r = int(255 * (ratio * 2))
            g = 255
            b = 0
        elif ratio < 0.75:
            # Yellow to Orange
            local_ratio = (ratio - 0.5) / 0.25
            r = 255
            g = int(255 - (80 * local_ratio))
            b = 0
        else:
            # Orange to Red (top quarter)
            local_ratio = (ratio - 0.75) / 0.25
            r = 255
            g = int(175 - (175 * local_ratio))
            b = 0
        
        return QColor(r, g, b)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)  # Sharp edges for LED look
        
        w = self.width()
        h = self.height()
        
        # Black background
        painter.fillRect(0, 0, w, h, QColor('#000000'))
        
        # Calculate bar dimensions - FIXED to fill entire width
        margin_left = 5    # Minimal left margin
        margin_right = 30  # Space for dB scale
        margin_top = 10
        margin_bottom = 20  # Space for labels
        
        usable_width = w - margin_left - margin_right
        usable_height = h - margin_top - margin_bottom
        
        # Gap between bars (2 pixels) and calculate bar width to fill space
        gap = 2
        total_gap_width = gap * (self.NUM_BANDS - 1)
        bar_width = (usable_width - total_gap_width) / self.NUM_BANDS
        bar_width = max(bar_width, 4)  # Minimum 4 pixels wide
        
        segment_height = usable_height / self.NUM_SEGMENTS
        segment_gap = 1  # Gap between segments
        
        # Draw frequency labels at specific positions
        painter.setPen(QColor('#666666'))
        font = QFont('Arial', 6)
        painter.setFont(font)
        
        # Map bands to frequencies (logarithmic spacing from 20Hz to 20kHz)
        freq_labels = ['32', '63', '125', '250', '500', '1k', '2k', '4k', '8k', '16k']
        # Position labels at evenly spaced intervals across the display
        label_count = len(freq_labels)
        for i, label in enumerate(freq_labels):
            # Calculate x position based on relative position
            band_idx = int(i * (self.NUM_BANDS - 1) / (label_count - 1))
            x = margin_left + band_idx * (bar_width + gap) + bar_width / 2
            painter.drawText(int(x) - 12, h - 14, 24, 12, Qt.AlignCenter, label)
        
        # Draw each frequency band - FILLS ENTIRE WIDTH
        for i in range(self.NUM_BANDS):
            # Normalize level to 0-1 range
            level_db = self.smoothed_spectrum[i]
            level = (level_db - self.DB_MIN) / (self.DB_MAX - self.DB_MIN)
            level = max(0.0, min(1.0, level))
            
            # Calculate how many segments to light up
            lit_segments = int(level * self.NUM_SEGMENTS)
            
            # Calculate bar position - evenly distributed across width
            bar_x = margin_left + i * (bar_width + gap)
            
            # Draw segments from bottom to top
            for seg in range(self.NUM_SEGMENTS):
                seg_y = h - margin_bottom - (seg + 1) * segment_height
                
                if seg < lit_segments:
                    # Lit segment - get color based on position
                    color = self._get_segment_color(seg, self.NUM_SEGMENTS)
                else:
                    # Unlit segment - dark gray
                    color = QColor('#1a1a1a')
                
                painter.fillRect(
                    int(bar_x), 
                    int(seg_y + segment_gap), 
                    int(bar_width), 
                    int(segment_height - segment_gap), 
                    color
                )
            
            # Draw peak indicator
            peak_db = self.peaks[i]
            peak_level = (peak_db - self.DB_MIN) / (self.DB_MAX - self.DB_MIN)
            peak_level = max(0.0, min(1.0, peak_level))
            peak_segment = int(peak_level * self.NUM_SEGMENTS)
            
            if peak_segment > lit_segments and peak_segment > 0:
                peak_y = h - margin_bottom - peak_segment * segment_height
                peak_color = self._get_segment_color(peak_segment - 1, self.NUM_SEGMENTS)
                # Make peak slightly brighter
                peak_color = QColor(
                    min(255, peak_color.red() + 30),
                    min(255, peak_color.green() + 30),
                    min(255, peak_color.blue() + 30)
                )
                painter.fillRect(
                    int(bar_x), 
                    int(peak_y + segment_gap), 
                    int(bar_width), 
                    int(segment_height - segment_gap), 
                    peak_color
                )
        
        # Draw dB scale on right side
        painter.setPen(QColor('#555555'))
        font = QFont('Arial', 6)
        painter.setFont(font)
        db_labels = ['0', '-20', '-40', '-60']
        for i, label in enumerate(db_labels):
            y = margin_top + int(i * usable_height / (len(db_labels) - 1)) - 4
            painter.drawText(w - 28, y, 25, 12, Qt.AlignRight, label)
    
    def setSpectrum(self, spectrum: np.ndarray):
        """Update spectrum data with proper dB scaling, makeup gain, and smoothing
        
        FIXED v4.1: Added makeup gain and better frequency-weighted display
        """
        # Resample to our number of bands using logarithmic spacing
        if len(spectrum) > self.NUM_BANDS:
            # Use logarithmic frequency spacing for perceptually even distribution
            indices = np.logspace(0, np.log10(len(spectrum) - 1), self.NUM_BANDS).astype(int)
            indices = np.clip(indices, 0, len(spectrum) - 1)
            raw_spectrum = spectrum[indices]
        else:
            raw_spectrum = np.zeros(self.NUM_BANDS)
            raw_spectrum[:len(spectrum)] = spectrum
        
        # The input is already in dB (from realtime_engine)
        # Apply MAKEUP GAIN for better visibility
        normalized_db = raw_spectrum + self.MAKEUP_GAIN_DB
        
        # Apply frequency-dependent weighting (boost lows slightly for visual balance)
        for i in range(self.NUM_BANDS):
            # Boost bass and sub-bass (first 6 bands) for visual balance
            if i < 3:
                normalized_db[i] += 6  # Boost sub-bass more
            elif i < 6:
                normalized_db[i] += 3  # Boost bass
        
        # Clamp to our display range
        normalized_db = np.clip(normalized_db, self.DB_MIN, self.DB_MAX)
        
        # Apply smoothing for natural movement - VECTORIZED for efficiency
        for i in range(self.NUM_BANDS):
            if normalized_db[i] > self.smoothed_spectrum[i]:
                # Attack - fast rise
                self.smoothed_spectrum[i] = (
                    self.attack_smooth * self.smoothed_spectrum[i] + 
                    (1 - self.attack_smooth) * normalized_db[i]
                )
            else:
                # Release - slower fall
                self.smoothed_spectrum[i] = (
                    self.release_smooth * self.smoothed_spectrum[i] + 
                    (1 - self.release_smooth) * normalized_db[i]
                )
        
        # Update peak hold
        for i in range(self.NUM_BANDS):
            if self.smoothed_spectrum[i] >= self.peaks[i]:
                # New peak
                self.peaks[i] = self.smoothed_spectrum[i]
                self.peak_hold_counters[i] = self.peak_hold_time
            else:
                # Decay peak
                if self.peak_hold_counters[i] > 0:
                    self.peak_hold_counters[i] -= 1
                else:
                    self.peaks[i] -= self.peak_decay_rate
                    self.peaks[i] = max(self.peaks[i], self.DB_MIN)
        
        self.update()


class GraphicalEQ(QWidget):
    """Interactive graphical EQ with ±2.4dB max"""
    eqChanged = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 90)
        
        self.bands = {
            60: 0, 125: 0, 250: 0, 500: 0, 1000: 0,
            2000: 0, 4000: 0, 8000: 0, 16000: 0
        }
        
        self.dragging = None
        self.max_gain = 2.4  # ±2.4dB maximum
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        margin = 35
        
        # Background
        painter.fillRect(0, 0, w, h, QColor('#1a1a2a'))
        
        # Grid
        painter.setPen(QPen(QColor('#2a2a4a'), 1))
        
        for db in [-2.4, -1.2, 0, 1.2, 2.4]:
            y = self._db_to_y(db, h, margin)
            painter.drawLine(margin, int(y), w - 10, int(y))
            painter.setPen(QColor('#666688'))
            painter.drawText(2, int(y) - 5, 30, 10, Qt.AlignRight, f"{db:+.1f}")
            painter.setPen(QPen(QColor('#2a2a4a'), 1))
        
        # Frequency labels
        painter.setPen(QColor('#666688'))
        font = QFont('Arial', 7)
        painter.setFont(font)
        
        for freq in self.bands.keys():
            x = self._freq_to_x(freq, w, margin)
            if freq >= 1000:
                label = f"{freq//1000}k"
            else:
                label = str(freq)
            painter.drawText(int(x) - 12, h - margin + 3, 24, 12, Qt.AlignCenter, label)
        
        # EQ curve
        path = QPainterPath()
        first = True
        
        for freq in sorted(self.bands.keys()):
            x = self._freq_to_x(freq, w, margin)
            y = self._db_to_y(self.bands[freq], h, margin)
            
            if first:
                path.moveTo(x, y)
                first = False
            else:
                path.lineTo(x, y)
        
        painter.setPen(QPen(QColor(COLORS['eq_line']), 2))
        painter.drawPath(path)
        
        # Control points
        for freq, gain in self.bands.items():
            x = self._freq_to_x(freq, w, margin)
            y = self._db_to_y(gain, h, margin)
            
            painter.setBrush(QBrush(QColor(COLORS['eq_point'])))
            painter.setPen(QPen(QColor('#ffffff'), 2))
            painter.drawEllipse(int(x) - 5, int(y) - 5, 10, 10)
        
        # Title
        painter.setPen(QColor(COLORS['copper_light']))
        font = QFont('Arial', 9, QFont.Bold)
        painter.setFont(font)
        painter.drawText(0, 3, w, 15, Qt.AlignCenter, "GRAPHICAL EQ (±2.4dB)")
    
    def _freq_to_x(self, freq: float, w: int, margin: int) -> float:
        log_freq = np.log10(freq)
        log_min = np.log10(20)
        log_max = np.log10(20000)
        return margin + (log_freq - log_min) / (log_max - log_min) * (w - margin - 10)
    
    def _db_to_y(self, db: float, h: int, margin: int) -> float:
        return margin + (self.max_gain - db) / (2 * self.max_gain) * (h - 2 * margin)
    
    def _y_to_db(self, y: float, h: int, margin: int) -> float:
        return self.max_gain - (y - margin) / (h - 2 * margin) * (2 * self.max_gain)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            w, h = self.width(), self.height()
            margin = 35
            
            for freq in self.bands.keys():
                x = self._freq_to_x(freq, w, margin)
                y = self._db_to_y(self.bands[freq], h, margin)
                
                if abs(event.x() - x) < 12 and abs(event.y() - y) < 12:
                    self.dragging = freq
                    break
    
    def mouseReleaseEvent(self, event):
        if self.dragging:
            self.eqChanged.emit(self.bands.copy())
        self.dragging = None
    
    def mouseMoveEvent(self, event):
        if self.dragging:
            h = self.height()
            margin = 35
            
            new_gain = self._y_to_db(event.y(), h, margin)
            new_gain = max(-self.max_gain, min(self.max_gain, new_gain))
            
            self.bands[self.dragging] = new_gain
            self.update()
    
    def setBands(self, bands: dict):
        for freq, gain in bands.items():
            if freq in self.bands:
                self.bands[freq] = max(-self.max_gain, min(self.max_gain, gain))
        self.update()
    
    def getBands(self) -> dict:
        return self.bands.copy()
    
    def reset(self):
        for freq in self.bands:
            self.bands[freq] = 0
        self.update()
        self.eqChanged.emit(self.bands.copy())


class AnalysisThread(QThread):
    """Background audio analysis"""
    finished = pyqtSignal(object)
    
    def __init__(self, audio_data, sample_rate):
        super().__init__()
        self.audio_data = audio_data
        self.sample_rate = sample_rate
    
    def run(self):
        if ANALYZER_AVAILABLE:
            try:
                analyzer = AudioAnalyzer(self.sample_rate)
                result = analyzer.analyze(self.audio_data, self.sample_rate)
                self.finished.emit(result)
            except Exception as e:
                print(f"Analysis error: {e}")
                self.finished.emit(None)
        else:
            self.finished.emit(None)


class ProcessingThread(QThread):
    """
    Memory-efficient streaming export thread.
    
    Uses StreamingExporter to process audio in small chunks, writing directly
    to disk. This prevents RAM exhaustion when exporting large files.
    
    Key improvements:
    - Never loads entire file into memory
    - Processes 2-second chunks at a time
    - Writes chunks directly to disk
    - Uses gc.collect() to free memory after each chunk
    - Memory usage stays stable regardless of file size
    """
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)  # Just message - file is already saved
    error = pyqtSignal(str)
    
    TARGET_SAMPLE_RATE = 96000  # Always export at 96kHz
    
    def __init__(self, processor, settings, input_path, output_path, dither_type="TPDF"):
        super().__init__()
        self.processor = processor
        self.settings = settings
        self.input_path = input_path
        self.output_path = output_path
        self.dither_type = dither_type
        self._exporter = None
        self._cancelled = False
    
    def cancel(self):
        self._cancelled = True
        if self._exporter:
            self._exporter.cancel()
    
    def run(self):
        try:
            if self._cancelled:
                return
            
            # Create streaming exporter
            self._exporter = StreamingExporter(self.processor)
            
            # Progress callback
            def progress_callback(pct):
                if self._cancelled:
                    return
                self.progress.emit(pct)
            
            # Stream-based export - processes in chunks, writes directly to disk
            success = self._exporter.export_streaming(
                input_path=self.input_path,
                output_path=self.output_path,
                settings=self.settings,
                target_sample_rate=self.TARGET_SAMPLE_RATE,
                bit_depth=24,
                dither_type=self.dither_type,
                progress_callback=progress_callback
            )
            
            if self._cancelled or not success:
                return
            
            self.finished.emit("Export complete!")
            
        except Exception as e:
            import traceback
            self.error.emit(f"{str(e)}\n{traceback.format_exc()}")


class HelpDialog(QDialog):
    """Help documentation"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Music Doctor - Help")
        self.setMinimumSize(650, 550)
        
        layout = QVBoxLayout(self)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        content = QLabel()
        content.setWordWrap(True)
        content.setTextFormat(Qt.RichText)
        content.setText(self._get_help_text())
        content.setStyleSheet("padding: 20px; background: #1a1a1a; color: #e0e0e0;")
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
    
    def _get_help_text(self) -> str:
        return """
        <h2 style='color: #b87333;'>AI Music Doctor v4.0</h2>
        <h3>Professional Mastering Suite for AI-Generated Music</h3>
        
        <h4 style='color: #d4955c;'>Signal Chain</h4>
        <p><b>Input → Denoiser → EQ → Knobs → Width → Volume (Output)</b></p>
        
        <h4 style='color: #d4955c;'>DENOISER</h4>
        <p>Psychoacoustic processor based on Fletcher-Munson curves and Bark Scale critical bands.</p>
        <ul>
            <li><b>SENSITIVITY:</b> Controls how aggressively problematic frequencies are detected (0-100%)</li>
            <li><b>BOOMY</b> (100-250Hz): Excessive low resonance</li>
            <li><b>BOXY</b> (150-250Hz): Hollow/resonant sound</li>
            <li><b>MUDDY</b> (200-500Hz): Lack of clarity</li>
            <li><b>HONKY</b> (500Hz-1.5kHz): Nasal midrange</li>
            <li><b>HARSH</b> (2-6kHz): Piercing high-mids</li>
            <li><b>SIZZLE</b> (8-12kHz): Excessive highs</li>
        </ul>
        <p>Each orbit button glows based on how much processing is needed. Click to toggle on/off.</p>
        
        <h4 style='color: #d4955c;'>Mastering Knobs (±3dB max)</h4>
        <ul>
            <li><b>AIR:</b> High frequency sparkle (8-16kHz shelf)</li>
            <li><b>BODY:</b> Low-mid warmth (100-300Hz)</li>
            <li><b>FOCUS:</b> Mid presence/clarity (1-4kHz)</li>
            <li><b>PUSH:</b> Gentle saturation/compression</li>
            <li><b>WIDTH:</b> Stereo width (M/S processing)</li>
            <li><b>VOLUME:</b> Output level (LAST in chain)</li>
            <li><b>TRANSIENTS:</b> Attack/sustain shaping</li>
            <li><b>ANALOG:</b> Warm even-harmonic saturation</li>
            <li><b>BASS PUNCH:</b> Low-end impact (60-120Hz)</li>
            <li><b>REVERB:</b> Mastering-grade reverb (Plate, Hall, Room, Chamber)</li>
        </ul>
        
        <h4 style='color: #d4955c;'>Graphical EQ</h4>
        <p>9-band EQ with maximum ±2.4dB per band. Drag points to adjust. Parameter smoothing prevents zipper noise.</p>
        
        <h4 style='color: #d4955c;'>Mono Monitoring</h4>
        <p>Click the <b>MONO</b> button to sum left and right channels to mono.
        This helps check mix compatibility on mono playback systems (phones, PA systems).
        Mono mode works even when bypass is enabled.</p>
        
        <h4 style='color: #d4955c;'>Export</h4>
        <p>Files are always exported as <b>WAV 24-bit 96kHz</b> for maximum quality.</p>
        
        <h4 style='color: #d4955c;'>Tips</h4>
        <ul>
            <li>Use BYPASS to compare processed vs original</li>
            <li>Use MONO to check mix compatibility</li>
            <li>Start with presets, then fine-tune</li>
            <li>Less is more - subtle adjustments sound best</li>
            <li>Watch the spectrum analyzer for visual feedback</li>
        </ul>
        """


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Music Doctor v4.0 - Professional Mastering")
        self.setMinimumSize(950, 620)
        
        # Initialize components
        self.processor = AudioProcessor()
        self.preset_manager = PresetManager()
        self.audio_engine = RealTimeAudioEngine() if REALTIME_AVAILABLE else None
        
        self.current_file = None
        self._loaded_filepath = None  # Store for streaming export
        self.processed_audio = None
        
        # Flag to prevent cascading updates during preset/batch changes
        self._batch_updating = False
        
        self._setup_ui()
        self._apply_dark_theme()
        self._connect_signals()
        
        # Timers
        self.spectrum_timer = QTimer()
        self.spectrum_timer.timeout.connect(self._update_spectrum)
        self.spectrum_timer.start(50)
        
        self.denoiser_timer = QTimer()
        self.denoiser_timer.timeout.connect(self._update_denoiser_levels)
        self.denoiser_timer.start(100)
    
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(3)
        main_layout.setContentsMargins(6, 4, 6, 4)
        
        # Top: Title and bypass
        top_panel = self._create_top_panel()
        main_layout.addWidget(top_panel)
        
        # Denoiser widget
        self.denoiser_widget = DenoiserWidget()
        main_layout.addWidget(self.denoiser_widget)
        
        # Knob panel (all 9 knobs)
        knob_panel = self._create_knob_panel()
        main_layout.addWidget(knob_panel)
        
        # Processing controls
        proc_panel = self._create_processing_panel()
        main_layout.addWidget(proc_panel)
        
        # Graphical EQ
        self.eq_widget = GraphicalEQ()
        main_layout.addWidget(self.eq_widget)
        
        # Spectrum analyzer
        self.spectrum_analyzer = SpectrumAnalyzer()
        main_layout.addWidget(self.spectrum_analyzer)
        
        # Bottom: Transport and file controls
        bottom_panel = self._create_bottom_panel()
        main_layout.addWidget(bottom_panel)
    
    def _create_top_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMaximumHeight(32)
        panel.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                           f"stop:0 {COLORS['copper']}, stop:0.5 {COLORS['copper_light']}, "
                           f"stop:1 {COLORS['copper_dark']});")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(6, 2, 6, 2)
        
        # Reset button
        reset_btn = QPushButton("RESET")
        reset_btn.setStyleSheet(self._button_style())
        reset_btn.clicked.connect(self._reset_all)
        layout.addWidget(reset_btn)
        
        # Title
        title = QLabel("AI MUSIC DOCTOR")
        title.setStyleSheet("color: #1a1a1a; font-size: 14px; font-weight: bold;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title, stretch=1)
        
        # Bypass button
        self.bypass_btn = QPushButton("BYPASS")
        self.bypass_btn.setCheckable(True)
        self.bypass_btn.setStyleSheet(self._button_style())
        self.bypass_btn.clicked.connect(self._toggle_bypass)
        layout.addWidget(self.bypass_btn)
        
        return panel
    
    def _create_knob_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMaximumHeight(105)
        panel.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                           f"stop:0 {COLORS['copper']}, stop:0.5 {COLORS['copper_light']}, "
                           f"stop:1 {COLORS['copper_dark']});")
        layout = QHBoxLayout(panel)
        layout.setSpacing(2)
        layout.setContentsMargins(4, 2, 4, 2)
        
        # Create all 9 mastering knobs
        self.knob_air = HardwareKnob("AIR", -100, 100, 0, "%")
        self.knob_body = HardwareKnob("BODY", -100, 100, 0, "%")
        self.knob_focus = HardwareKnob("FOCUS", -100, 100, 0, "%")
        self.knob_push = HardwareKnob("PUSH", 0, 100, 0, "%")
        self.knob_width = HardwareKnob("WIDTH", 0, 200, 100, "%")
        self.knob_volume = HardwareKnob("VOLUME", -12, 6, 0, "dB", decimals=1)
        self.knob_transients = HardwareKnob("TRANSIENTS", -100, 100, 0, "%")
        self.knob_analog = HardwareKnob("ANALOG", 0, 100, 0, "%")
        self.knob_bass_punch = HardwareKnob("BASS PUNCH", 0, 100, 0, "%")
        
        for knob in [self.knob_air, self.knob_body, self.knob_focus, self.knob_push,
                     self.knob_width, self.knob_volume, self.knob_transients,
                     self.knob_analog, self.knob_bass_punch]:
            layout.addWidget(knob)
        
        # Add reverb section
        reverb_frame = QFrame()
        reverb_frame.setStyleSheet(f"QFrame {{ border-left: 1px solid {COLORS['copper']}; padding-left: 5px; }}")
        reverb_layout = QVBoxLayout(reverb_frame)
        reverb_layout.setContentsMargins(2, 2, 2, 2)
        reverb_layout.setSpacing(2)
        
        # Reverb type selector
        reverb_label = QLabel("REVERB")
        reverb_label.setStyleSheet(f"color: {COLORS['copper_light']}; font-weight: bold; font-size: 9px;")
        reverb_label.setAlignment(Qt.AlignCenter)
        reverb_layout.addWidget(reverb_label)
        
        self.reverb_type_combo = QComboBox()
        self.reverb_type_combo.addItems(["Plate", "Hall", "Room", "Chamber"])
        self.reverb_type_combo.setStyleSheet(f"""
            QComboBox {{
                background: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['copper']};
                border-radius: 3px;
                padding: 2px;
                min-width: 55px;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {COLORS['panel']};
                color: {COLORS['text']};
                selection-background-color: {COLORS['copper']};
            }}
        """)
        reverb_layout.addWidget(self.reverb_type_combo)
        
        # Reverb amount knob (0-60% max for mastering)
        self.knob_reverb = HardwareKnob("WET", 0, 60, 0, "%")
        reverb_layout.addWidget(self.knob_reverb, 0, Qt.AlignHCenter | Qt.AlignTop)
        
        layout.addWidget(reverb_frame)
        
        return panel
    
    def _create_processing_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMaximumHeight(36)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)
        
        combo_style = self._combo_style()
        label_style = f"color: {COLORS['copper_light']}; font-weight: bold; font-size: 8px;"
        
        # Oversampling
        os_label = QLabel("OS:")
        os_label.setStyleSheet(label_style)
        layout.addWidget(os_label)
        self.oversample_combo = QComboBox()
        self.oversample_combo.addItems(["1x (Off)", "2x", "4x", "8x"])
        self.oversample_combo.setStyleSheet(combo_style)
        layout.addWidget(self.oversample_combo)
        
        # Undo/Redo buttons
        self.undo_btn = QPushButton("↶")
        self.redo_btn = QPushButton("↷")
        self.undo_btn.setToolTip("Undo")
        self.redo_btn.setToolTip("Redo")
        self.undo_btn.setStyleSheet(self._button_style())
        self.redo_btn.setStyleSheet(self._button_style())
        self.undo_btn.setFixedWidth(30)
        self.redo_btn.setFixedWidth(30)
        self.undo_btn.clicked.connect(self._undo)
        self.redo_btn.clicked.connect(self._redo)
        layout.addWidget(self.undo_btn)
        layout.addWidget(self.redo_btn)
        
        # Preset selector
        preset_label = QLabel("Preset:")
        preset_label.setStyleSheet(label_style)
        layout.addWidget(preset_label)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(self.preset_manager.get_preset_names())
        self.preset_combo.setStyleSheet(combo_style)
        layout.addWidget(self.preset_combo)
        
        # Processing mode
        mode_label = QLabel("Mode:")
        mode_label.setStyleSheet(label_style)
        layout.addWidget(mode_label)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Spectral (FFT)", "Time-Domain", "Hybrid"])
        self.mode_combo.setStyleSheet(combo_style)
        layout.addWidget(self.mode_combo)
        
        # Dither
        dither_label = QLabel("Dither:")
        dither_label.setStyleSheet(label_style)
        layout.addWidget(dither_label)
        self.dither_combo = QComboBox()
        self.dither_combo.addItems(["Off", "TPDF", "POWr1", "POWr2", "POWr3"])
        self.dither_combo.setCurrentText("TPDF")
        self.dither_combo.setStyleSheet(combo_style)
        layout.addWidget(self.dither_combo)
        
        return panel
    
    def _create_bottom_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMaximumHeight(36)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        
        # File controls
        self.load_btn = QPushButton("📂 Load Audio")
        self.load_btn.setStyleSheet(self._button_style())
        self.load_btn.clicked.connect(self._load_file)
        layout.addWidget(self.load_btn)
        
        self.file_label = QLabel("No file loaded")
        self.file_label.setStyleSheet(f"color: {COLORS['text']};")
        layout.addWidget(self.file_label, stretch=1)
        
        # Transport
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setStyleSheet(self._button_style())
        self.play_btn.clicked.connect(self._play)
        layout.addWidget(self.play_btn)
        
        self.stop_btn = QPushButton("⬛ Stop")
        self.stop_btn.setStyleSheet(self._button_style())
        self.stop_btn.clicked.connect(self._stop)
        layout.addWidget(self.stop_btn)
        
        # A/B comparison
        self.ab_btn = QPushButton("A/B")
        self.ab_btn.setCheckable(True)
        self.ab_btn.setStyleSheet(self._button_style())
        self.ab_btn.clicked.connect(self._toggle_ab)
        layout.addWidget(self.ab_btn)
        
        # Mono monitoring mode
        self.mono_btn = QPushButton("MONO")
        self.mono_btn.setCheckable(True)
        self.mono_btn.setStyleSheet(self._button_style())
        self.mono_btn.setToolTip("Toggle mono monitoring (L+R summed to mono)")
        self.mono_btn.clicked.connect(self._toggle_mono)
        layout.addWidget(self.mono_btn)
        
        # Export
        self.export_btn = QPushButton("💾 Export")
        self.export_btn.setStyleSheet(self._button_style())
        self.export_btn.clicked.connect(self._export)
        layout.addWidget(self.export_btn)
        
        # Help
        self.help_btn = QPushButton("❓ Help")
        self.help_btn.setStyleSheet(self._button_style())
        self.help_btn.clicked.connect(self._show_help)
        layout.addWidget(self.help_btn)
        
        # Progress
        self.progress = QProgressBar()
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background: {COLORS['panel']};
                border: 1px solid {COLORS['copper']};
                border-radius: 3px;
                text-align: center;
                color: {COLORS['text']};
            }}
            QProgressBar::chunk {{
                background: {COLORS['copper']};
            }}
        """)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        return panel
    
    def _button_style(self) -> str:
        return f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a4a4a, stop:0.5 #3a3a3a, stop:1 #2a2a2a);
                color: {COLORS['text']};
                border: 1px solid {COLORS['copper']};
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 10px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5a5a5a, stop:0.5 #4a4a4a, stop:1 #3a3a3a);
            }}
            QPushButton:pressed {{
                background: {COLORS['copper_dark']};
            }}
            QPushButton:checked {{
                background: {COLORS['copper']};
                color: #000000;
            }}
        """
    
    def _combo_style(self) -> str:
        return f"""
            QComboBox {{
                background: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['copper']};
                border-radius: 3px;
                padding: 4px;
                font-size: 10px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background: {COLORS['panel']};
                color: {COLORS['text']};
                selection-background-color: {COLORS['copper']};
            }}
        """
    
    def _apply_dark_theme(self):
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background: {COLORS['background']};
                color: {COLORS['text']};
            }}
            QGroupBox {{
                border: 1px solid {COLORS['copper']};
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }}
        """)
    
    def _connect_signals(self):
        # Knob signals - valueChanged for real-time updates (no undo save)
        # valueChangeFinished for undo state save on mouse release
        self.knob_air.valueChanged.connect(lambda v: self._update_params_no_undo(air=v))
        self.knob_air.valueChangeFinished.connect(lambda v: self._save_undo_state())
        
        self.knob_body.valueChanged.connect(lambda v: self._update_params_no_undo(body=v))
        self.knob_body.valueChangeFinished.connect(lambda v: self._save_undo_state())
        
        self.knob_focus.valueChanged.connect(lambda v: self._update_params_no_undo(focus=v))
        self.knob_focus.valueChangeFinished.connect(lambda v: self._save_undo_state())
        
        self.knob_push.valueChanged.connect(lambda v: self._update_params_no_undo(push=v))
        self.knob_push.valueChangeFinished.connect(lambda v: self._save_undo_state())
        
        self.knob_width.valueChanged.connect(lambda v: self._update_params_no_undo(width=v))
        self.knob_width.valueChangeFinished.connect(lambda v: self._save_undo_state())
        
        self.knob_volume.valueChanged.connect(lambda v: self._update_params_no_undo(volume=v))
        self.knob_volume.valueChangeFinished.connect(lambda v: self._save_undo_state())
        
        self.knob_transients.valueChanged.connect(lambda v: self._update_params_no_undo(transients=v))
        self.knob_transients.valueChangeFinished.connect(lambda v: self._save_undo_state())
        
        self.knob_analog.valueChanged.connect(lambda v: self._update_params_no_undo(analog=v))
        self.knob_analog.valueChangeFinished.connect(lambda v: self._save_undo_state())
        
        self.knob_bass_punch.valueChanged.connect(lambda v: self._update_params_no_undo(bass_punch=v))
        self.knob_bass_punch.valueChangeFinished.connect(lambda v: self._save_undo_state())
        
        # Reverb signals
        self.knob_reverb.valueChanged.connect(lambda v: self._update_params_no_undo(reverb=v))
        self.knob_reverb.valueChangeFinished.connect(lambda v: self._save_undo_state())
        self.reverb_type_combo.currentTextChanged.connect(
            lambda t: self._update_params_no_undo(reverb_type=t)
        )
        
        # Denoiser signals - also no undo during drag
        self.denoiser_widget.sensitivityChanged.connect(
            lambda v: self._update_params_no_undo(denoiser_sensitivity=v)
        )
        self.denoiser_widget.sensitivityChangeFinished.connect(lambda v: self._save_undo_state())
        self.denoiser_widget.bandToggled.connect(self._on_denoiser_band_toggled)
        
        # Combo signals
        self.preset_combo.currentTextChanged.connect(self._apply_preset)
        self.mode_combo.currentTextChanged.connect(lambda m: self._update_params(processing_mode=m))
        self.oversample_combo.currentIndexChanged.connect(self._update_oversampling)
        
        # EQ signal
        self.eq_widget.eqChanged.connect(self._update_eq)
        
        # Audio engine callbacks
        if self.audio_engine:
            self.audio_engine.on_position_change = self._on_position_change
            self.audio_engine.on_spectrum_update = self._on_spectrum_update
            self.audio_engine.on_playback_finished = self._on_playback_finished
            self.audio_engine.on_denoiser_update = self._on_denoiser_update
    
    def _update_params(self, **kwargs):
        """Update audio engine parameters - skips if batch updating"""
        if self._batch_updating:
            return  # Skip individual updates during batch operations
        if self.audio_engine:
            self.audio_engine.update_params(**kwargs)
        self._update_undo_buttons()
    
    def _update_params_no_undo(self, **kwargs):
        """Update audio engine parameters WITHOUT saving undo state
        
        Used for real-time knob dragging to prevent freezing from
        excessive undo state saves.
        """
        if self._batch_updating:
            return
        if self.audio_engine:
            self.audio_engine.update_params(save_undo=False, **kwargs)
    
    def _save_undo_state(self):
        """Save current state to undo history
        
        Called on mouse release after knob adjustment.
        """
        if self.audio_engine:
            self.audio_engine.undo_manager.save_state(self.audio_engine.params)
        self._update_undo_buttons()
    
    def _on_denoiser_band_toggled(self, band: str, active: bool):
        param_name = f'denoiser_{band}'
        self._update_params(**{param_name: active})
    
    def _update_eq(self, bands: dict):
        if self.audio_engine:
            self.audio_engine.update_params(eq_settings=bands)
    
    def _update_oversampling(self, index: int):
        factors = [1, 2, 4, 8]
        self.processor.set_oversampling(factors[index])
    
    def _update_undo_buttons(self):
        if self.audio_engine:
            self.undo_btn.setEnabled(self.audio_engine.can_undo())
            self.redo_btn.setEnabled(self.audio_engine.can_redo())
    
    def _undo(self):
        if self.audio_engine and self.audio_engine.undo():
            self._sync_ui_from_params()
    
    def _redo(self):
        if self.audio_engine and self.audio_engine.redo():
            self._sync_ui_from_params()
    
    def _sync_ui_from_params(self):
        """Sync UI controls from params with batch updating to prevent freezing"""
        if not self.audio_engine:
            return
        
        params = self.audio_engine.params.get_all()
        
        # Set batch flag to prevent cascading updates
        self._batch_updating = True
        
        try:
            self.knob_air.setValue(params.get('air', 0))
            self.knob_body.setValue(params.get('body', 0))
            self.knob_focus.setValue(params.get('focus', 0))
            self.knob_push.setValue(params.get('push', 0))
            self.knob_width.setValue(params.get('width', 100))
            self.knob_volume.setValue(params.get('volume', 0))
            self.knob_transients.setValue(params.get('transients', 0))
            self.knob_analog.setValue(params.get('analog', 0))
            self.knob_bass_punch.setValue(params.get('bass_punch', 0))
            
            # Reverb controls
            self.knob_reverb.setValue(params.get('reverb', 0))
            reverb_type = params.get('reverb_type', 'Plate')
            idx = self.reverb_type_combo.findText(reverb_type)
            if idx >= 0:
                self.reverb_type_combo.setCurrentIndex(idx)
            
            self.denoiser_widget.knob_sensitivity.setValue(params.get('denoiser_sensitivity', 0))
            
            # Sync denoiser buttons
            self.denoiser_widget.btn_boomy.setActive(params.get('denoiser_boomy', True))
            self.denoiser_widget.btn_boxy.setActive(params.get('denoiser_boxy', True))
            self.denoiser_widget.btn_muddy.setActive(params.get('denoiser_muddy', True))
            self.denoiser_widget.btn_honky.setActive(params.get('denoiser_honky', True))
            self.denoiser_widget.btn_harsh.setActive(params.get('denoiser_harsh', True))
            self.denoiser_widget.btn_sizzle.setActive(params.get('denoiser_sizzle', True))
            
            self.eq_widget.setBands(params.get('eq_settings', {}))
        finally:
            self._batch_updating = False
        
        self._update_undo_buttons()
    
    def _apply_preset(self, name: str):
        """Apply preset with batch updating to prevent freezing"""
        preset = self.preset_manager.get_preset(name)
        
        # Set batch flag to prevent individual updates during UI changes
        self._batch_updating = True
        
        try:
            # Apply knob values (signals blocked by batch flag)
            self.knob_air.setValue(preset.get('air', 0))
            self.knob_body.setValue(preset.get('body', 0))
            self.knob_focus.setValue(preset.get('focus', 0))
            self.knob_push.setValue(preset.get('push', 0))
            self.knob_width.setValue(preset.get('width', 100))
            self.knob_volume.setValue(preset.get('volume', 0))
            self.knob_transients.setValue(preset.get('transients', 0))
            self.knob_analog.setValue(preset.get('analog', 0))
            self.knob_bass_punch.setValue(preset.get('bass_punch', 0))
            
            # Reverb controls
            self.knob_reverb.setValue(preset.get('reverb', 0))
            reverb_type = preset.get('reverb_type', 'Plate')
            idx = self.reverb_type_combo.findText(reverb_type)
            if idx >= 0:
                self.reverb_type_combo.setCurrentIndex(idx)
            
            # Denoiser
            self.denoiser_widget.knob_sensitivity.setValue(preset.get('denoiser_sensitivity', 0))
            
            # Update orbit button states
            self.denoiser_widget.btn_boomy.setActive(preset.get('boomy', True))
            self.denoiser_widget.btn_boxy.setActive(preset.get('boxy', True))
            self.denoiser_widget.btn_muddy.setActive(preset.get('muddy', True))
            self.denoiser_widget.btn_honky.setActive(preset.get('honky', True))
            self.denoiser_widget.btn_harsh.setActive(preset.get('harsh', True))
            self.denoiser_widget.btn_sizzle.setActive(preset.get('sizzle', True))
            
            # EQ
            eq_settings = preset.get('eq_settings', {})
            clamped_eq = {f: max(-2.4, min(2.4, g)) for f, g in eq_settings.items()}
            self.eq_widget.setBands(clamped_eq)
            
            mode = preset.get('processing_mode', 'Hybrid')
            self.mode_combo.setCurrentText(mode)
        finally:
            # Clear batch flag
            self._batch_updating = False
        
        # Single batch update to audio engine
        if self.audio_engine:
            # Create a copy of preset and update eq_settings with clamped values
            preset_copy = dict(preset)
            preset_copy['eq_settings'] = clamped_eq
            # Add denoiser band states
            preset_copy['denoiser_boomy'] = preset.get('boomy', True)
            preset_copy['denoiser_boxy'] = preset.get('boxy', True)
            preset_copy['denoiser_muddy'] = preset.get('muddy', True)
            preset_copy['denoiser_honky'] = preset.get('honky', True)
            preset_copy['denoiser_harsh'] = preset.get('harsh', True)
            preset_copy['denoiser_sizzle'] = preset.get('sizzle', True)
            self.audio_engine.update_params(**preset_copy)
        
        self._update_undo_buttons()
    
    def _reset_all(self):
        """Reset all controls with batch updating to prevent freezing"""
        # Set batch flag to prevent individual updates
        self._batch_updating = True
        
        try:
            self.knob_air.setValue(0)
            self.knob_body.setValue(0)
            self.knob_focus.setValue(0)
            self.knob_push.setValue(0)
            self.knob_width.setValue(100)
            self.knob_volume.setValue(0)
            self.knob_transients.setValue(0)
            self.knob_analog.setValue(0)
            self.knob_bass_punch.setValue(0)
            
            # Reset reverb
            self.knob_reverb.setValue(0)
            self.reverb_type_combo.setCurrentIndex(0)  # Plate
            
            self.denoiser_widget.knob_sensitivity.setValue(0)
            
            # Reset denoiser buttons
            self.denoiser_widget.btn_boomy.setActive(True)
            self.denoiser_widget.btn_boxy.setActive(True)
            self.denoiser_widget.btn_muddy.setActive(True)
            self.denoiser_widget.btn_honky.setActive(True)
            self.denoiser_widget.btn_harsh.setActive(True)
            self.denoiser_widget.btn_sizzle.setActive(True)
            
            self.eq_widget.reset()
            self.preset_combo.setCurrentText("Default")
        finally:
            # Clear batch flag
            self._batch_updating = False
        
        # Single batch update to audio engine
        if self.audio_engine:
            self.audio_engine.update_params(
                air=0, body=0, focus=0, push=0, width=100, volume=0,
                transients=0, analog=0, bass_punch=0,
                reverb=0, reverb_type='Plate',
                denoiser_sensitivity=0,
                denoiser_boomy=True, denoiser_boxy=True, denoiser_muddy=True,
                denoiser_honky=True, denoiser_harsh=True, denoiser_sizzle=True,
                eq_settings={},
                bypass=False
            )
        
        self._update_undo_buttons()
    
    def _toggle_bypass(self):
        """Toggle bypass - when bypassed, audio passes through unprocessed"""
        if self.audio_engine:
            self.audio_engine.params.bypass = self.bypass_btn.isChecked()
    
    def _toggle_ab(self):
        """A/B comparison - same as bypass"""
        if self.audio_engine:
            self.audio_engine.params.bypass = self.ab_btn.isChecked()
    
    def _toggle_mono(self):
        """Toggle mono monitoring mode"""
        if self.audio_engine:
            self.audio_engine.params.mono = self.mono_btn.isChecked()
            # Update button style to show active state more clearly
            if self.mono_btn.isChecked():
                self.mono_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {COLORS['copper']};
                        color: #000000;
                        border: 2px solid {COLORS['meter_yellow']};
                        border-radius: 4px;
                        padding: 6px 12px;
                        font-weight: bold;
                        font-size: 10px;
                    }}
                """)
            else:
                self.mono_btn.setStyleSheet(self._button_style())
    
    def _load_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Audio File", "",
            "Audio Files (*.wav *.mp3 *.flac *.ogg *.aiff);;All Files (*)"
        )
        
        if filepath:
            try:
                audio_data, sample_rate = self.processor.load_audio(filepath)
                self.current_file = filepath
                self._loaded_filepath = filepath  # Store for streaming export
                self.file_label.setText(Path(filepath).name)
                
                if self.audio_engine:
                    self.audio_engine.load_audio(audio_data, sample_rate)
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file:\n{str(e)}")
    
    def _play(self):
        if self.audio_engine and self.audio_engine.audio_data is not None:
            if self.audio_engine.paused:
                self.audio_engine.play()
                self.play_btn.setText("⏸ Pause")
            elif self.audio_engine.playing:
                self.audio_engine.pause()
                self.play_btn.setText("▶ Play")
            else:
                self.audio_engine.play()
                self.play_btn.setText("⏸ Pause")
    
    def _stop(self):
        if self.audio_engine:
            self.audio_engine.stop()
            self.play_btn.setText("▶ Play")
    
    def _on_position_change(self, position: float):
        pass
    
    def _on_spectrum_update(self, block: np.ndarray):
        pass
    
    def _on_playback_finished(self):
        self.play_btn.setText("▶ Play")
    
    def _on_denoiser_update(self, levels: dict):
        """Update denoiser orbit button glow levels"""
        self.denoiser_widget.setGlowLevels(levels)
    
    def _update_spectrum(self):
        if self.audio_engine and self.audio_engine.playing:
            spectrum = self.audio_engine.get_current_spectrum()
            if spectrum is not None:
                self.spectrum_analyzer.setSpectrum(spectrum)
    
    def _update_denoiser_levels(self):
        """Periodic update of denoiser detection levels"""
        if self.audio_engine and self.audio_engine.playing and self.audio_engine.processor:
            levels = self.audio_engine.processor.get_denoiser_levels()
            self.denoiser_widget.setGlowLevels(levels)
    
    def _export(self):
        if self.processor.audio_data is None:
            QMessageBox.warning(self, "Warning", "No audio loaded")
            return
        
        # Need the original file path for streaming export
        if not hasattr(self, '_loaded_filepath') or not self._loaded_filepath:
            QMessageBox.warning(self, "Warning", "Please reload the audio file for export")
            return
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Audio (WAV 24-bit 96kHz)", "",
            "WAV Files (*.wav);;All Files (*)"
        )
        
        if filepath:
            # Ensure .wav extension
            if not filepath.lower().endswith('.wav'):
                filepath += '.wav'
            
            self.progress.setVisible(True)
            self.progress.setValue(0)
            self._export_filepath = filepath  # Store for callback
            
            # Get current settings from all controls
            denoiser_states = self.denoiser_widget.getBandStates()
            
            settings = {
                'air': self.knob_air.getValue(),
                'body': self.knob_body.getValue(),
                'focus': self.knob_focus.getValue(),
                'push': self.knob_push.getValue(),
                'width': self.knob_width.getValue(),
                'volume': self.knob_volume.getValue(),
                'transients': self.knob_transients.getValue(),
                'analog': self.knob_analog.getValue(),
                'bass_punch': self.knob_bass_punch.getValue(),
                'reverb': self.knob_reverb.getValue(),
                'reverb_type': self.reverb_type_combo.currentText(),
                'denoiser_sensitivity': self.denoiser_widget.getSensitivity() / 100,
                'denoiser_boomy': denoiser_states['boomy'],
                'denoiser_boxy': denoiser_states['boxy'],
                'denoiser_muddy': denoiser_states['muddy'],
                'denoiser_honky': denoiser_states['honky'],
                'denoiser_harsh': denoiser_states['harsh'],
                'denoiser_sizzle': denoiser_states['sizzle'],
                'processing_mode': self.mode_combo.currentText(),
                'eq_settings': self.eq_widget.getBands()
            }
            
            # Get dither type
            dither = self.dither_combo.currentText()
            
            # Use streaming export - processes in chunks, never loads full file into RAM
            self.export_thread = ProcessingThread(
                processor=self.processor,
                settings=settings,
                input_path=self._loaded_filepath,
                output_path=filepath,
                dither_type=dither
            )
            self.export_thread.progress.connect(self.progress.setValue)
            self.export_thread.finished.connect(self._on_export_complete)
            self.export_thread.error.connect(self._on_export_error)
            self.export_thread.start()
    
    def _on_export_error(self, error_msg: str):
        self.progress.setVisible(False)
        QMessageBox.critical(self, "Export Error", error_msg)
    
    def _on_export_complete(self, msg: str):
        """Called when streaming export completes - file is already saved"""
        self.progress.setVisible(False)
        QMessageBox.information(
            self, "Export Complete", 
            f"Exported to:\n{self._export_filepath}\n\n"
            f"Format: WAV 24-bit 96kHz\n\n"
            f"Memory-efficient streaming export completed successfully."
        )
    
    def _show_help(self):
        dialog = HelpDialog(self)
        dialog.exec_()
    
    def closeEvent(self, event):
        if self.audio_engine:
            self.audio_engine.stop()
        self.spectrum_timer.stop()
        self.denoiser_timer.stop()
        event.accept()


def run_app():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    run_app()

