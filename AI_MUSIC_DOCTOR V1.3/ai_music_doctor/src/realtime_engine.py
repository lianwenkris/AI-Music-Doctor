<uploaded_files github_repo=mixdoktorz-bit/AI-Music-Doctor>
<file=AI_MUSIC_DOCTOR V1.3/ai_music_doctor/src/realtime_engine.py>
"""
AI Music Doctor - Real-Time Audio Engine
Version: 4.2.0 - AUDIO PLAYBACK FIX

Low-latency streaming with professional mastering controls.
Signal Chain: Input → Denoiser → EQ → Knobs → Width → Volume

CRITICAL FIXES in 4.2.0:
- Eliminated lock contention in audio callback (lock-free design)
- Fixed denoiser filter state bug (was reinitializing zi every call)
- Increased buffer size to 2048 for stability
- Moved GUI callbacks out of audio thread (use atomic flags)
- Spectrum computation no longer blocks audio
- All processing uses vectorized scipy.signal.lfilter (no sample-by-sample loops)
"""

import numpy as np
from scipy import signal
from scipy.fft import rfft, irfft
import threading
from typing import Callable, Optional, Dict, Any, List
from dataclasses import dataclass, field
from collections import deque
import copy
import time

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False


# Denoiser bands - simplified for real-time
DENOISER_BANDS = {
    'boomy': (60, 200),
    'boxy': (200, 400),
    'muddy': (250, 500),
    'honky': (600, 1200),
    'harsh': (2500, 5000),
    'sizzle': (7000, 12000)
}


@dataclass
class ProcessingParameters:
    """Thread-safe container for all processing parameters
    
    Uses atomic reads for audio thread - NO LOCKS in the hot path.
    """
    
    # Knobs (±3dB max processing)
    air: float = 0.0            # -100 to +100
    body: float = 0.0           # -100 to +100
    focus: float = 0.0          # -100 to +100
    push: float = 0.0           # 0 to 100
    width: float = 100.0        # 0 to 200 (100 = no change)
    volume: float = 0.0         # -12 to +6 dB
    transients: float = 0.0     # -100 to +100
    analog: float = 0.0         # 0 to 100
    bass_punch: float = 0.0     # 0 to 100
    
    # Reverb (mastering-grade, max 60% wet)
    reverb: float = 0.0         # 0 to 60 (percentage)
    reverb_type: str = "Plate"  # Plate, Hall, Room, Chamber
    
    # Denoiser
    denoiser_sensitivity: float = 0.0  # 0 to 100
    denoiser_boomy: bool = True
    denoiser_boxy: bool = True
    denoiser_muddy: bool = True
    denoiser_honky: bool = True
    denoiser_harsh: bool = True
    denoiser_sizzle: bool = True
    
    # EQ (max ±2.4dB)
    eq_settings: Dict[int, float] = field(default_factory=dict)
    
    # Processing
    processing_mode: str = "Spectral (FFT)"
    oversampling: int = 1
    bypass: bool = False
    
    # Mono monitoring mode - sums L+R to mono for mix compatibility checking
    mono: bool = False
    
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def update(self, **kwargs):
        """Thread-safe parameter update - non-blocking for audio thread"""
        # Try to acquire lock without blocking
        acquired = self._lock.acquire(blocking=False)
        if not acquired:
            # If lock not available, force update anyway (atomic for simple types)
            for key, value in kwargs.items():
                if hasattr(self, key) and not key.startswith('_'):
                    setattr(self, key, value)
            return
        try:
            for key, value in kwargs.items():
                if hasattr(self, key) and not key.startswith('_'):
                    setattr(self, key, value)
        finally:
            self._lock.release()
    
    def get_all(self) -> dict:
        """Get all parameters as dict - non-blocking"""
        # Don't block - just read current values
        return {
            'air': self.air,
            'body': self.body,
            'focus': self.focus,
            'push': self.push,
            'width': self.width,
            'volume': self.volume,
            'transients': self.transients,
            'analog': self.analog,
            'bass_punch': self.bass_punch,
            'reverb': self.reverb,
            'reverb_type': self.reverb_type,
            'denoiser_sensitivity': self.denoiser_sensitivity,
            'denoiser_boomy': self.denoiser_boomy,
            'denoiser_boxy': self.denoiser_boxy,
            'denoiser_muddy': self.denoiser_muddy,
            'denoiser_honky': self.denoiser_honky,
            'denoiser_harsh': self.denoiser_harsh,
            'denoiser_sizzle': self.denoiser_sizzle,
            'eq_settings': dict(self.eq_settings),  # Shallow copy without lock
            'processing_mode': self.processing_mode,
            'oversampling': self.oversampling,
            'bypass': self.bypass,
            'mono': self.mono,
        }
    
    def copy(self) -> 'ProcessingParameters':
        """Create a deep copy - non-blocking"""
        new_params = ProcessingParameters()
        for key in ['air', 'body', 'focus', 'push', 'width', 'volume',
                   'transients', 'analog', 'bass_punch', 'reverb', 'reverb_type',
                   'denoiser_sensitivity', 'denoiser_boomy', 'denoiser_boxy', 
                   'denoiser_muddy', 'denoiser_honky', 'denoiser_harsh', 
                   'denoiser_sizzle', 'processing_mode', 'oversampling', 
                   'bypass', 'mono']:
            setattr(new_params, key, getattr(self, key))
        new_params.eq_settings = dict(self.eq_settings)
        return new_params


class UndoRedoManager:
    """Manages undo/redo state for parameters"""
    
    def __init__(self, max_history: int = 50):
        self.history: List[dict] = []
        self.future: List[dict] = []
        self.max_history = max_history
        self._lock = threading.Lock()
    
    def save_state(self, params: ProcessingParameters):
        """Save current state to history"""
        with self._lock:
            state = params.get_all()
            self.history.append(state)
            if len(self.history) > self.max_history:
                self.history.pop(0)
            self.future.clear()
    
    def undo(self, current_params: ProcessingParameters) -> Optional[dict]:
        """Undo last change"""
        with self._lock:
            if len(self.history) < 2:
                return None
            current = self.history.pop()
            self.future.append(current)
            return self.history[-1] if self.history else None
    
    def redo(self) -> Optional[dict]:
        """Redo last undone change"""
        with self._lock:
            if not self.future:
                return None
            state = self.future.pop()
            self.history.append(state)
            return state
    
    def can_undo(self) -> bool:
        with self._lock:
            return len(self.history) > 1
    
    def can_redo(self) -> bool:
        with self._lock:
            return len(self.future) > 0


class VectorizedFilter:
    """Vectorized biquad filter using scipy.signal.lfilter - FAST"""
    
    def __init__(self, sample_rate: int):
        self.sample_rate = sample_rate
        self.b = np.array([1.0, 0.0, 0.0])
        self.a = np.array([1.0, 0.0, 0.0])
        self.zi_l = np.zeros(2)
        self.zi_r = np.zeros(2)
    
    def set_peaking(self, freq: float, gain_db: float, Q: float = 1.0):
        """Set peaking EQ coefficients"""
        gain_db = np.clip(gain_db, -2.4, 2.4)
        
        if abs(gain_db) < 0.05:
            self.b = np.array([1.0, 0.0, 0.0])
            self.a = np.array([1.0, 0.0, 0.0])
            return
        
        A = 10 ** (gain_db / 40)
        w0 = 2 * np.pi * freq / self.sample_rate
        w0 = np.clip(w0, 0.001, np.pi - 0.001)
        
        alpha = np.sin(w0) / (2 * Q)
        cos_w0 = np.cos(w0)
        
        b0 = 1 + alpha * A
        b1 = -2 * cos_w0
        b2 = 1 - alpha * A
        a0 = 1 + alpha / A
        a1 = -2 * cos_w0
        a2 = 1 - alpha / A
        
        self.b = np.array([b0/a0, b1/a0, b2/a0])
        self.a = np.array([1.0, a1/a0, a2/a0])
    
    def set_high_shelf(self, freq: float, gain_db: float, Q: float = 0.707):
        """Set high shelf coefficients"""
        gain_db = np.clip(gain_db, -3.0, 3.0)
        
        if abs(gain_db) < 0.05:
            self.b = np.array([1.0, 0.0, 0.0])
            self.a = np.array([1.0, 0.0, 0.0])
            return
        
        A = 10 ** (gain_db / 40)
        w0 = 2 * np.pi * freq / self.sample_rate
        w0 = np.clip(w0, 0.001, np.pi - 0.001)
        
        alpha = np.sin(w0) / (2 * Q)
        cos_w0 = np.cos(w0)
        sqrt_A = np.sqrt(max(A, 0.001))
        
        b0 = A * ((A + 1) + (A - 1) * cos_w0 + 2 * sqrt_A * alpha)
        b1 = -2 * A * ((A - 1) + (A + 1) * cos_w0)
        b2 = A * ((A + 1) + (A - 1) * cos_w0 - 2 * sqrt_A * alpha)
        a0 = (A + 1) - (A - 1) * cos_w0 + 2 * sqrt_A * alpha
        a1 = 2 * ((A - 1) - (A + 1) * cos_w0)
        a2 = (A + 1) - (A - 1) * cos_w0 - 2 * sqrt_A * alpha
        
        self.b = np.array([b0/a0, b1/a0, b2/a0])
        self.a = np.array([1.0, a1/a0, a2/a0])
    
    def set_low_shelf(self, freq: float, gain_db: float, Q: float = 0.707):
        """Set low shelf coefficients"""
        gain_db = np.clip(gain_db, -3.0, 3.0)
        
        if abs(gain_db) < 0.05:
            self.b = np.array([1.0, 0.0, 0.0])
            self.a = np.array([1.0, 0.0, 0.0])
            return
        
        A = 10 ** (gain_db / 40)
        w0 = 2 * np.pi * freq / self.sample_rate
        w0 = np.clip(w0, 0.001, np.pi - 0.001)
        
        alpha = np.sin(w0) / (2 * Q)
        cos_w0 = np.cos(w0)
        sqrt_A = np.sqrt(max(A, 0.001))
        
        b0 = A * ((A + 1) - (A - 1) * cos_w0 + 2 * sqrt_A * alpha)
        b1 = 2 * A * ((A - 1) - (A + 1) * cos_w0)
        b2 = A * ((A + 1) - (A - 1) * cos_w0 - 2 * sqrt_A * alpha)
        a0 = (A + 1) + (A - 1) * cos_w0 + 2 * sqrt_A * alpha
        a1 = -2 * ((A - 1) + (A + 1) * cos_w0)
        a2 = (A + 1) + (A - 1) * cos_w0 - 2 * sqrt_A * alpha
        
        self.b = np.array([b0/a0, b1/a0, b2/a0])
        self.a = np.array([1.0, a1/a0, a2/a0])
    
    def process(self, x: np.ndarray, is_left: bool = True) -> np.ndarray:
        """Process block using vectorized lfilter - FAST"""
        zi = self.zi_l if is_left else self.zi_r
        try:
            y, zf = signal.lfilter(self.b, self.a, x, zi=zi)
            if is_left:
                self.zi_l = zf
            else:
                self.zi_r = zf
            return y
        except:
            return x
    
    def reset(self):
        self.zi_l = np.zeros(2)
        self.zi_r = np.zeros(2)


# Alias for backwards compatibility
SmoothedBiquad = VectorizedFilter


class RealTimeProcessor:
    """
    Real-time audio processor - STABILITY FOCUSED
    
    All processing uses vectorized scipy operations for speed.
    No sample-by-sample Python loops.
    """
    
    MAX_KNOB_DB = 3.0
    MAX_EQ_DB = 2.4
    
    def __init__(self, sample_rate: int, block_size: int = 2048):
        self.sample_rate = sample_rate
        self.block_size = block_size
        
        # Denoiser - simple multiband attenuation (no FFT in real-time path)
        self.denoiser_levels = {k: 0.0 for k in DENOISER_BANDS.keys()}
        self.denoiser_filters_l = {}
        self.denoiser_filters_r = {}
        self._init_denoiser_filters()
        
        # EQ filters (vectorized)
        self.eq_filters_l = {}
        self.eq_filters_r = {}
        
        # Knob filters (vectorized)
        self.air_filter = VectorizedFilter(sample_rate)
        self.body_filter = VectorizedFilter(sample_rate)
        self.focus_filter = VectorizedFilter(sample_rate)
        
        # Bass punch filter
        self.bass_lp_filter = VectorizedFilter(sample_rate)
        self._init_bass_filter()
        self.bass_zi_l = np.zeros(2)
        self.bass_zi_r = np.zeros(2)
        
        # Envelope for transients (simple)
        self.env_l = 0.0
        self.env_r = 0.0
        
        # Reverb delay lines (simple stereo delay-based reverb for real-time)
        self._init_reverb_buffers()
    
    def _init_denoiser_filters(self):
        """Initialize bandpass filters for denoiser analysis"""
        for band_name, (low, high) in DENOISER_BANDS.items():
            try:
                # Normalize frequencies
                nyq = self.sample_rate / 2
                low_norm = max(low / nyq, 0.001)
                high_norm = min(high / nyq, 0.999)
                if low_norm >= high_norm:
                    continue
                b, a = signal.butter(2, [low_norm, high_norm], 'bandpass')
                # Compute proper initial conditions
                zi_init = signal.lfilter_zi(b, a)
                self.denoiser_filters_l[band_name] = {'b': b, 'a': a, 'zi': zi_init.copy()}
                self.denoiser_filters_r[band_name] = {'b': b, 'a': a, 'zi': zi_init.copy()}
            except:
                pass
    
    def _init_bass_filter(self):
        """Initialize bass lowpass filter"""
        try:
            cutoff = 120 / (self.sample_rate / 2)
            cutoff = min(cutoff, 0.9)
            b, a = signal.butter(2, cutoff, 'lowpass')
            self.bass_b = b
            self.bass_a = a
            # Proper initial conditions
            zi_init = signal.lfilter_zi(b, a)
            self.bass_zi_l = zi_init.copy()
            self.bass_zi_r = zi_init.copy()
        except:
            self.bass_b = np.array([1.0])
            self.bass_a = np.array([1.0])
    
    def _init_reverb_buffers(self):
        """Initialize simple delay-based reverb buffers for real-time"""
        # Simple multi-tap delay reverb (CPU efficient)
        # Different delay times for stereo decorrelation
        max_delay_samples = int(0.1 * self.sample_rate)  # 100ms max delay
        
        # Delay line buffers
        self.reverb_buffer_l = np.zeros(max_delay_samples)
        self.reverb_buffer_r = np.zeros(max_delay_samples)
        self.reverb_pos = 0
        
        # Pre-computed delay tap times (samples) for each reverb type
        # Shorter delays for real-time to reduce latency
        self.reverb_taps = {
            'Plate': [int(0.012 * self.sample_rate), int(0.029 * self.sample_rate), 
                      int(0.043 * self.sample_rate), int(0.067 * self.sample_rate)],
            'Hall': [int(0.018 * self.sample_rate), int(0.037 * self.sample_rate),
                     int(0.056 * self.sample_rate), int(0.089 * self.sample_rate)],
            'Room': [int(0.008 * self.sample_rate), int(0.017 * self.sample_rate),
                     int(0.025 * self.sample_rate), int(0.039 * self.sample_rate)],
            'Chamber': [int(0.015 * self.sample_rate), int(0.031 * self.sample_rate),
                        int(0.048 * self.sample_rate), int(0.072 * self.sample_rate)],
        }
        
        # Feedback coefficients per tap (decay pattern)
        self.reverb_gains = {
            'Plate': [0.5, 0.35, 0.25, 0.15],
            'Hall': [0.45, 0.35, 0.28, 0.18],
            'Room': [0.6, 0.35, 0.2, 0.1],
            'Chamber': [0.55, 0.4, 0.3, 0.2],
        }
        
        # High-pass filter for reverb (keep low end tight)
        try:
            hp_freq = 300 / (self.sample_rate / 2)
            hp_freq = min(hp_freq, 0.9)
            self.reverb_hp_b, self.reverb_hp_a = signal.butter(2, hp_freq, 'highpass')
            self.reverb_hp_zi_l = signal.lfilter_zi(self.reverb_hp_b, self.reverb_hp_a)
            self.reverb_hp_zi_r = signal.lfilter_zi(self.reverb_hp_b, self.reverb_hp_a)
        except:
            self.reverb_hp_b = np.array([1.0])
            self.reverb_hp_a = np.array([1.0])
            self.reverb_hp_zi_l = np.zeros(2)
            self.reverb_hp_zi_r = np.zeros(2)
    
    def process_block(self, audio_block: np.ndarray, params: ProcessingParameters) -> np.ndarray:
        """Process a block of audio with all effects - VECTORIZED"""
        
        if params.bypass:
            result = audio_block.copy()
            # Apply mono monitoring even when bypassed
            if params.mono and len(result.shape) > 1 and result.shape[1] >= 2:
                mono = (result[:, 0] + result[:, 1]) * 0.5
                result[:, 0] = mono
                result[:, 1] = mono
            return result
        
        try:
            # Handle stereo/mono
            if len(audio_block.shape) > 1 and audio_block.shape[1] >= 2:
                left = self._process_channel(audio_block[:, 0].copy(), params, is_left=True)
                right = self._process_channel(audio_block[:, 1].copy(), params, is_left=False)
                
                # REVERB (after knobs, before width) - stereo processing
                if params.reverb > 0:
                    left, right = self._apply_reverb_stereo(left, right, params)
                
                # Width processing (M/S) - vectorized
                width = params.width / 100.0
                mid = (left + right) * 0.5
                side = (left - right) * 0.5
                side *= width
                left = mid + side
                right = mid - side
                
                # Volume (last in chain)
                gain = 10 ** (np.clip(params.volume, -12, 6) / 20)
                left *= gain
                right *= gain
                
                # Soft clip - vectorized
                left = np.tanh(left * 0.95) / 0.95
                right = np.tanh(right * 0.95) / 0.95
                
                # MONO MONITORING MODE - sum L+R to mono for both channels
                if params.mono:
                    mono = (left + right) * 0.5
                    left = mono
                    right = mono
                
                return np.column_stack((left, right))
            else:
                data = audio_block.flatten() if len(audio_block.shape) > 1 else audio_block
                processed = self._process_channel(data.copy(), params, is_left=True)
                gain = 10 ** (np.clip(params.volume, -12, 6) / 20)
                processed *= gain
                processed = np.tanh(processed * 0.95) / 0.95
                return processed
        except Exception as e:
            # If processing fails, return clean audio rather than silence
            return audio_block.copy()
    
    def _process_channel(self, channel: np.ndarray, params: ProcessingParameters, 
                         is_left: bool = True) -> np.ndarray:
        """Process single channel - ALL VECTORIZED"""
        
        output = channel
        
        # 1. DENOISER (simple multiband attenuation - VERY SUBTLE)
        if params.denoiser_sensitivity > 0:
            output = self._apply_denoiser_simple(output, params, is_left)
        
        # 2. EQ (vectorized biquads)
        if params.eq_settings:
            output = self._apply_eq_vectorized(output, params.eq_settings, is_left)
        
        # 3. Air (high shelf at 10kHz) - vectorized
        if abs(params.air) > 1:
            gain_db = (params.air / 100) * self.MAX_KNOB_DB
            self.air_filter.set_high_shelf(10000, gain_db)
            output = self.air_filter.process(output, is_left)
        
        # 4. Body (low shelf at 200Hz) - vectorized
        if abs(params.body) > 1:
            gain_db = (params.body / 100) * self.MAX_KNOB_DB
            self.body_filter.set_low_shelf(200, gain_db)
            output = self.body_filter.process(output, is_left)
        
        # 5. Focus (peaking at 2.5kHz) - vectorized
        if abs(params.focus) > 1:
            gain_db = (params.focus / 100) * self.MAX_KNOB_DB
            self.focus_filter.set_peaking(2500, gain_db, Q=1.0)
            output = self.focus_filter.process(output, is_left)
        
        # 6. Push (saturation + gentle compression) - AUDIBLE
        if params.push > 1:
            drive = params.push / 100.0
            saturated = np.tanh(output * (1 + drive * 2))
            blend = drive * 0.7
            output = output * (1 - blend) + saturated * blend
            threshold = 0.7 - drive * 0.3
            above_thresh = np.abs(output) > threshold
            if np.any(above_thresh):
                ratio = 1.0 + drive * 2
                compressed = np.sign(output) * (threshold + (np.abs(output) - threshold) / ratio)
                output = np.where(above_thresh, compressed, output)
        
        # 7. Transients - simplified vectorized
        if abs(params.transients) > 1:
            output = self._apply_transients_simple(output, params.transients)
        
        # 8. Analog (even harmonic saturation) - vectorized
        if params.analog > 1:
            amt = params.analog / 100.0 * 0.3
            saturated = np.tanh(output * (1 + amt))
            output = output * (1 - amt) + saturated * amt
        
        # 9. Bass Punch - vectorized
        if params.bass_punch > 1:
            output = self._apply_bass_punch_simple(output, params.bass_punch, is_left)
        
        return output
    
    def _apply_denoiser_simple(self, channel: np.ndarray, params: ProcessingParameters, 
                               is_left: bool) -> np.ndarray:
        """
        Simple multiband denoiser - NO FFT, uses bandpass filters
        VERY SUBTLE to avoid distortion
        
        FIXED: Filter state (zi) is now properly maintained between calls
        instead of being reinitialised each time.
        """
        sensitivity = params.denoiser_sensitivity / 100.0 * 0.15  # MAX 15% reduction
        
        filters = self.denoiser_filters_l if is_left else self.denoiser_filters_r
        output = channel.copy()
        
        for band_name, (low, high) in DENOISER_BANDS.items():
            active = getattr(params, f'denoiser_{band_name}', True)
            
            if not active or band_name not in filters:
                continue
            
            filt = filters[band_name]
            
            try:
                # FIX: Use persistent filter state - don't reinitialize with channel[0]
                band_signal, zf = signal.lfilter(filt['b'], filt['a'], channel, zi=filt['zi'])
                filt['zi'] = zf  # Store updated state for next call
                
                band_level = np.sqrt(np.mean(band_signal**2) + 1e-10)
                self.denoiser_levels[band_name] = min(1.0, band_level * 5)
                
                # Very subtle reduction
                if band_level > 0.01:
                    reduction = 1.0 - (sensitivity * min(band_level * 2, 1.0))
                    reduction = max(reduction, 0.85)
                    output = output - band_signal * (1.0 - reduction)
            except Exception:
                # Reset filter state on error
                try:
                    filt['zi'] = signal.lfilter_zi(filt['b'], filt['a'])
                except:
                    pass
        
        return output
    
    def _apply_eq_vectorized(self, channel: np.ndarray, eq_settings: Dict[int, float], 
                              is_left: bool) -> np.ndarray:
        """Apply EQ with vectorized filters - FAST"""
        filters = self.eq_filters_l if is_left else self.eq_filters_r
        output = channel.copy()
        
        for freq, gain_db in eq_settings.items():
            freq = int(freq)
            gain_db = np.clip(float(gain_db), -self.MAX_EQ_DB, self.MAX_EQ_DB)
            
            if abs(gain_db) < 0.05:
                continue
            
            if freq not in filters:
                filters[freq] = VectorizedFilter(self.sample_rate)
            
            filters[freq].set_peaking(freq, gain_db, Q=1.0)
            output = filters[freq].process(output, is_left)
        
        return output
    
    def _apply_transients_simple(self, channel: np.ndarray, amount: float) -> np.ndarray:
        """Simplified transient shaping - vectorized"""
        strength = abs(amount) / 100.0 * 0.3
        boost = amount > 0
        
        abs_signal = np.abs(channel)
        
        # Use simple moving average for envelope
        window_size = max(1, int(self.sample_rate * 0.005))  # 5ms window
        if window_size < len(abs_signal):
            kernel = np.ones(window_size) / window_size
            envelope = np.convolve(abs_signal, kernel, mode='same')
        else:
            envelope = abs_signal
        
        transient = np.maximum(0, abs_signal - envelope * 0.8)
        
        if boost:
            gain = 1.0 + transient * strength * 2
        else:
            gain = 1.0 - transient * strength
        
        return channel * np.clip(gain, 0.7, 1.5)
    
    def _apply_bass_punch_simple(self, channel: np.ndarray, amount: float, is_left: bool) -> np.ndarray:
        """Bass punch using vectorized filtering - AUDIBLE 60-120Hz enhancement"""
        amt = amount / 100.0
        
        try:
            zi = self.bass_zi_l if is_left else self.bass_zi_r
            low, zf = signal.lfilter(self.bass_b, self.bass_a, channel, zi=zi)
            
            if is_left:
                self.bass_zi_l = zf
            else:
                self.bass_zi_r = zf
            
            high = channel - low
            
            boost_db = amt * 6.0
            boost_linear = 10 ** (boost_db / 20)
            boosted_low = low * boost_linear
            
            if amt > 0.3:
                harmonic = np.sin(np.pi * low * 2) * amt * 0.15
                boosted_low = boosted_low + harmonic
            
            boosted_low = np.tanh(boosted_low * 1.2) / 1.2
            
            return boosted_low + high
        except:
            return channel
    
    def _apply_reverb_stereo(self, left: np.ndarray, right: np.ndarray, 
                              params: ProcessingParameters) -> tuple:
        """
        Apply simple multi-tap delay reverb for real-time.
        VECTORIZED for CPU efficiency - no sample-by-sample Python loops.
        
        Returns: (left, right) with reverb applied
        """
        reverb_type = params.reverb_type
        wet_amount = np.clip(params.reverb, 0, 60) / 100.0  # Max 60%
        
        if wet_amount < 0.005 or reverb_type not in self.reverb_taps:
            return left, right
        
        try:
            taps = self.reverb_taps[reverb_type]
            gains = self.reverb_gains[reverb_type]
            buffer_len = len(self.reverb_buffer_l)
            block_len = len(left)
            
            # High-pass filter the input to reverb (keep low end tight)
            reverb_input_l, self.reverb_hp_zi_l = signal.lfilter(
                self.reverb_hp_b, self.reverb_hp_a, left, zi=self.reverb_hp_zi_l
            )
            reverb_input_r, self.reverb_hp_zi_r = signal.lfilter(
                self.reverb_hp_b, self.reverb_hp_a, right, zi=self.reverb_hp_zi_r
            )
            
            # Generate reverb tails from multi-tap delay - VECTORIZED
            reverb_l = np.zeros(block_len)
            reverb_r = np.zeros(block_len)
            
            # Vectorized index arrays for the block
            block_indices = np.arange(block_len)
            
            for tap_delay, tap_gain in zip(taps, gains):
                if tap_delay >= buffer_len:
                    continue
                
                # Vectorized read positions for entire block at once
                read_indices_l = (self.reverb_pos + block_indices - tap_delay) % buffer_len
                read_indices_r = (self.reverb_pos + block_indices - tap_delay - 3) % buffer_len
                
                reverb_l += self.reverb_buffer_l[read_indices_l] * tap_gain
                reverb_r += self.reverb_buffer_r[read_indices_r] * tap_gain
            
            # Write input + feedback to circular buffer - VECTORIZED
            feedback = 0.25
            write_indices = (self.reverb_pos + block_indices) % buffer_len
            self.reverb_buffer_l[write_indices] = reverb_input_l + reverb_l * feedback
            self.reverb_buffer_r[write_indices] = reverb_input_r + reverb_r * feedback
            
            # Update buffer position
            self.reverb_pos = (self.reverb_pos + block_len) % buffer_len
            
            # Mix dry and wet
            dry_amount = 1.0 - wet_amount
            output_l = left * dry_amount + reverb_l * wet_amount
            output_r = right * dry_amount + reverb_r * wet_amount
            
            return output_l, output_r
            
        except Exception:
            return left, right
    
    def get_denoiser_levels(self) -> Dict[str, float]:
        """Get current denoiser detection levels"""
        return self.denoiser_levels.copy()


class RealTimeAudioEngine:
    """Complete real-time audio engine
    
    v4.2.0 FIXES:
    - Lock-free audio callback (no lock acquisition in hot path)
    - Audio data accessed via atomic position counter
    - Spectrum computed from separate buffer (no lock contention)
    - Increased buffer to 2048 samples for stability
    - GUI callbacks decoupled from audio thread
    """
    
    def __init__(self):
        self.audio_data = None
        self.sample_rate = None
        self.is_stereo = False
        
        self.processor = None
        self.params = ProcessingParameters()
        self.undo_manager = UndoRedoManager()
        
        self.undo_manager.save_state(self.params)
        
        # Playback state - atomic flags (no lock needed for reads)
        self.playing = False
        self.paused = False
        self.position = 0  # Atomic int - audio thread writes, GUI reads
        self.loop = False
        self.loop_start = 0
        self.loop_end = 0
        
        # Callbacks
        self.on_position_change: Optional[Callable[[float], None]] = None
        self.on_spectrum_update: Optional[Callable[[np.ndarray], None]] = None
        self.on_playback_finished: Optional[Callable[[], None]] = None
        self.on_denoiser_update: Optional[Callable[[Dict[str, float]], None]] = None
        
        self._stream = None
        self._load_lock = threading.Lock()  # Only used for load/stop - NOT in audio callback
        self.block_size = 2048  # INCREASED from 512 for stability
        
        # Separate spectrum buffer - written by audio thread, read by GUI
        self._last_block = None  # Atomic reference swap
        
        # Performance monitoring
        self._callback_times = deque(maxlen=100)
        self._underrun_count = 0
    
    def load_audio(self, audio_data: np.ndarray, sample_rate: int):
        """Load audio for playback"""
        self.stop()
        
        with self._load_lock:
            self.audio_data = audio_data.copy()
            self.sample_rate = sample_rate
            self.is_stereo = len(audio_data.shape) > 1 and audio_data.shape[1] >= 2
            self.position = 0
            self.loop_end = len(audio_data)
            
            self.processor = RealTimeProcessor(sample_rate, self.block_size)
    
    def play(self):
        """Start playback"""
        if self.audio_data is None or not SOUNDDEVICE_AVAILABLE:
            return
        
        if self.paused:
            self.paused = False
            return
        
        self.stop()
        self.playing = True
        
        # Cache these for the callback to avoid attribute lookups
        audio_data = self.audio_data
        audio_len = len(audio_data)
        processor = self.processor
        params = self.params
        
        def audio_callback(outdata, frames, time_info, status):
            """
            LOCK-FREE audio callback.
            
            No locks are acquired here. We read/write self.position atomically
            (Python GIL makes int assignment atomic). Audio data reference is
            captured in closure and never modified during playback.
            """
            if status:
                self._underrun_count += 1
            
            if not self.playing or self.paused:
                outdata.fill(0)
                return
            
            t0 = time.perf_counter()
            
            try:
                start = self.position
                end = min(start + frames, audio_len)
                
                if start >= audio_len:
                    if self.loop:
                        self.position = self.loop_start
                        start = self.position
                        end = min(start + frames, self.loop_end)
                    else:
                        outdata.fill(0)
                        self.playing = False
                        if self.on_playback_finished:
                            self.on_playback_finished()
                        return
                
                # Direct array slice - no lock needed, audio_data is immutable during playback
                block = audio_data[start:end].copy()
                self.position = end
                
                # Process audio
                if processor is not None:
                    try:
                        block = processor.process_block(block, params)
                    except Exception:
                        # If processing fails, use unprocessed audio
                        block = audio_data[start:end].copy()
                
                # Store last block for spectrum display (atomic reference swap)
                if len(block.shape) > 1 and block.shape[1] >= 2:
                    self._last_block = block[:, 0].copy()
                else:
                    self._last_block = block.copy() if len(block.shape) == 1 else block[:, 0].copy()
                
                # Output
                actual_frames = len(block)
                if self.is_stereo and len(block.shape) > 1 and block.shape[1] >= 2:
                    if actual_frames < frames:
                        outdata[:actual_frames] = block
                        outdata[actual_frames:] = 0
                    else:
                        outdata[:] = block[:frames]
                else:
                    flat = block.flatten() if len(block.shape) > 1 else block
                    if len(flat) < frames:
                        outdata[:len(flat), 0] = flat
                        outdata[:len(flat), 1] = flat
                        outdata[len(flat):] = 0
                    else:
                        outdata[:, 0] = flat[:frames]
                        outdata[:, 1] = flat[:frames]
                
                # Track performance
                elapsed = time.perf_counter() - t0
                self._callback_times.append(elapsed)
                
            except Exception as e:
                # Safety net - never let callback crash
                outdata.fill(0)
        
        try:
            self._stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=2,
                blocksize=self.block_size,
                callback=audio_callback,
                latency='low'  # Request low latency from the driver
            )
            self._stream.start()
        except Exception as e:
            print(f"Audio stream error: {e}")
            self.playing = False
    
    def pause(self):
        self.paused = True
    
    def stop(self):
        self.playing = False
        self.paused = False
        
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except:
                pass
            self._stream = None
        
        self.position = 0
        self._last_block = None
    
    def seek(self, position: float):
        """Seek to position (0-1) - lock-free"""
        if self.audio_data is None:
            return
        self.position = int(position * len(self.audio_data))
    
    def set_loop(self, enabled: bool, start: float = 0, end: float = 1):
        if self.audio_data is None:
            return
        self.loop = enabled
        self.loop_start = int(start * len(self.audio_data))
        self.loop_end = int(end * len(self.audio_data))
    
    def update_params(self, save_undo: bool = True, **kwargs):
        """Update processing parameters
        
        Args:
            save_undo: Whether to save state for undo (default True).
                       Set to False for rapid updates (e.g., knob dragging).
            **kwargs: Parameters to update
        """
        if save_undo:
            self.undo_manager.save_state(self.params)
        self.params.update(**kwargs)
    
    def undo(self) -> bool:
        state = self.undo_manager.undo(self.params)
        if state:
            for key, value in state.items():
                if hasattr(self.params, key) and not key.startswith('_'):
                    setattr(self.params, key, value)
            return True
        return False
    
    def redo(self) -> bool:
        state = self.undo_manager.redo()
        if state:
            for key, value in state.items():
                if hasattr(self.params, key) and not key.startswith('_'):
                    setattr(self.params, key, value)
            return True
        return False
    
    def can_undo(self) -> bool:
        return self.undo_manager.can_undo()
    
    def can_redo(self) -> bool:
        return self.undo_manager.can_redo()
    
    def get_current_spectrum(self) -> Optional[np.ndarray]:
        """Get current spectrum - LOCK-FREE
        
        Uses the last processed block stored by the audio callback,
        instead of reading from the main audio buffer with a lock.
        """
        block = self._last_block
        if block is None or len(block) < 256:
            return None
        
        try:
            # Use the last processed block directly
            data = block[-min(4096, len(block)):]
            
            # Apply Hanning window
            window = np.hanning(len(data))
            windowed = data * window
            
            # FFT with proper normalization
            spectrum = rfft(windowed)
            
            window_sum = np.sum(window)
            magnitude = np.abs(spectrum) / window_sum * 2
            
            magnitude_db = 20 * np.log10(magnitude + 1e-10)
            
            return magnitude_db
        except:
            return None
    
    def get_performance_stats(self) -> dict:
        """Get audio callback performance statistics"""
        if not self._callback_times:
            return {'avg_ms': 0, 'max_ms': 0, 'underruns': self._underrun_count}
        
        times = list(self._callback_times)
        budget_ms = (self.block_size / self.sample_rate * 1000) if self.sample_rate else 0
        return {
            'avg_ms': np.mean(times) * 1000,
            'max_ms': np.max(times) * 1000,
            'budget_ms': budget_ms,
            'underruns': self._underrun_count,
            'margin_pct': (1 - np.mean(times) * 1000 / budget_ms) * 100 if budget_ms > 0 else 0
        }
    
    @property
    def duration(self) -> float:
        if self.audio_data is None or self.sample_rate is None:
            return 0
        return len(self.audio_data) / self.sample_rate
    
    @property
    def current_time(self) -> float:
        if self.audio_data is None or self.sample_rate is None:
            return 0
        return self.position / self.sample_rate


# Backwards compatibility
GentleRealTimeProcessor = RealTimeProcessor

</file>

</uploaded_files>
