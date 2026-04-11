"""
AI Music Doctor - Advanced Audio Processing Engine
Version: 4.1.0

Implements professional mastering-grade processing with:
- Air, Body, Focus, Push, Width, Volume, Transients, Analog, Bass Punch knobs
- Psychoacoustic DENOISER based on Fletcher-Munson and Bark Scale
- Artifact-free EQ with parameter smoothing (max ±2.4dB)
- Zero-latency real-time processing
- MEMORY-EFFICIENT STREAMING EXPORT (fixes RAM exhaustion on large files)
- MASTERING REVERB: Plate, Hall, Room, Chamber types (max 60% wet)
- NEVE-STYLE PROCESSING: Soft-knee saturation, even harmonics, transformer warmth

Signal Chain: Input → Denoiser → EQ → Air/Body/Focus/Push/Transients/Analog/Bass Punch → REVERB → Width → Volume (OUTPUT)
"""

import numpy as np
from scipy import signal
from scipy.fft import rfft, irfft
import soundfile as sf
from typing import Tuple, Optional, Dict, List, Callable
from dataclasses import dataclass
import warnings
import gc

warnings.filterwarnings('ignore', category=RuntimeWarning)


# Bark Scale Critical Bands (24 bands)
BARK_BANDS = [
    (20, 100), (100, 200), (200, 300), (300, 400), (400, 510),
    (510, 630), (630, 770), (770, 920), (920, 1080), (1080, 1270),
    (1270, 1480), (1480, 1720), (1720, 2000), (2000, 2320), (2320, 2700),
    (2700, 3150), (3150, 3700), (3700, 4400), (4400, 5300), (5300, 6400),
    (6400, 7700), (7700, 9500), (9500, 12000), (12000, 15500)
]

# Denoiser frequency bands
DENOISER_BANDS = {
    'boomy': (100, 250),    # Excessive low resonance
    'boxy': (150, 250),     # Hollow/resonant sound (overlaps slightly with boomy)
    'muddy': (200, 500),    # Lack of clarity
    'honky': (500, 1500),   # Nasal, resonant midrange
    'harsh': (2000, 6000),  # Piercing high-mids
    'sizzle': (8000, 12000) # Excessive high-frequency
}

# Fletcher-Munson approximate sensitivity (relative, 1kHz = 1.0)
FLETCHER_MUNSON_SENSITIVITY = {
    100: 0.25, 200: 0.45, 500: 0.75, 1000: 1.0,
    2000: 1.1, 4000: 1.0, 8000: 0.8, 16000: 0.3
}

# Mastering Reverb Types - Based on research for subtle, hi-fi reverbs
REVERB_TYPES = {
    'Plate': {
        'description': 'Classic smooth, dense reverb (EMT 140 style)',
        'decay_time': 1.2,      # RT60 in seconds
        'pre_delay_ms': 12,     # Pre-delay in ms
        'diffusion': 0.8,       # High diffusion for density
        'damping': 0.4,         # Moderate high-freq damping
        'hp_freq': 300,         # High-pass filter
        'lp_freq': 8000,        # Low-pass filter
    },
    'Hall': {
        'description': 'Large space, natural decay (Lexicon style)',
        'decay_time': 1.5,      
        'pre_delay_ms': 18,     
        'diffusion': 0.7,       
        'damping': 0.3,         
        'hp_freq': 250,         
        'lp_freq': 10000,       
    },
    'Room': {
        'description': 'Subtle ambience, short decay',
        'decay_time': 0.5,      
        'pre_delay_ms': 8,      
        'diffusion': 0.5,       
        'damping': 0.5,         
        'hp_freq': 400,         
        'lp_freq': 7000,        
    },
    'Chamber': {
        'description': 'Warm, diffuse reverb',
        'decay_time': 1.0,      
        'pre_delay_ms': 15,     
        'diffusion': 0.9,       
        'damping': 0.45,        
        'hp_freq': 200,         
        'lp_freq': 6000,        
    }
}


@dataclass
class DenoiserState:
    """Holds denoiser detection and processing state"""
    boomy_level: float = 0.0
    boxy_level: float = 0.0
    muddy_level: float = 0.0
    honky_level: float = 0.0
    harsh_level: float = 0.0
    sizzle_level: float = 0.0
    
    boomy_active: bool = True
    boxy_active: bool = True
    muddy_active: bool = True
    honky_active: bool = True
    harsh_active: bool = True
    sizzle_active: bool = True


class SmoothedFilter:
    """Biquad filter with coefficient smoothing to prevent zipper noise"""
    
    def __init__(self, sample_rate: int, smoothing_time_ms: float = 5.0):
        self.sample_rate = sample_rate
        self.smoothing_factor = 1.0 - np.exp(-1.0 / (sample_rate * smoothing_time_ms / 1000))
        
        # Current and target coefficients
        self.b = np.array([1.0, 0.0, 0.0])
        self.a = np.array([1.0, 0.0, 0.0])
        self.target_b = self.b.copy()
        self.target_a = self.a.copy()
        
        # Filter state (Direct Form II Transposed)
        self.z1 = 0.0
        self.z2 = 0.0
    
    def set_peaking_eq(self, freq: float, gain_db: float, Q: float = 1.0):
        """Set target coefficients for peaking EQ"""
        gain_db = np.clip(gain_db, -2.4, 2.4)  # Max ±2.4dB
        
        if abs(gain_db) < 0.05:
            self.target_b = np.array([1.0, 0.0, 0.0])
            self.target_a = np.array([1.0, 0.0, 0.0])
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
        
        self.target_b = np.array([b0/a0, b1/a0, b2/a0])
        self.target_a = np.array([1.0, a1/a0, a2/a0])
    
    def set_low_shelf(self, freq: float, gain_db: float, Q: float = 0.707):
        """Set target coefficients for low shelf"""
        gain_db = np.clip(gain_db, -3.0, 3.0)
        
        if abs(gain_db) < 0.05:
            self.target_b = np.array([1.0, 0.0, 0.0])
            self.target_a = np.array([1.0, 0.0, 0.0])
            return
        
        A = 10 ** (gain_db / 40)
        w0 = 2 * np.pi * freq / self.sample_rate
        w0 = np.clip(w0, 0.001, np.pi - 0.001)
        
        alpha = np.sin(w0) / (2 * Q)
        cos_w0 = np.cos(w0)
        sqrt_A = np.sqrt(A)
        
        b0 = A * ((A + 1) - (A - 1) * cos_w0 + 2 * sqrt_A * alpha)
        b1 = 2 * A * ((A - 1) - (A + 1) * cos_w0)
        b2 = A * ((A + 1) - (A - 1) * cos_w0 - 2 * sqrt_A * alpha)
        a0 = (A + 1) + (A - 1) * cos_w0 + 2 * sqrt_A * alpha
        a1 = -2 * ((A - 1) + (A + 1) * cos_w0)
        a2 = (A + 1) + (A - 1) * cos_w0 - 2 * sqrt_A * alpha
        
        self.target_b = np.array([b0/a0, b1/a0, b2/a0])
        self.target_a = np.array([1.0, a1/a0, a2/a0])
    
    def set_high_shelf(self, freq: float, gain_db: float, Q: float = 0.707):
        """Set target coefficients for high shelf"""
        gain_db = np.clip(gain_db, -3.0, 3.0)
        
        if abs(gain_db) < 0.05:
            self.target_b = np.array([1.0, 0.0, 0.0])
            self.target_a = np.array([1.0, 0.0, 0.0])
            return
        
        A = 10 ** (gain_db / 40)
        w0 = 2 * np.pi * freq / self.sample_rate
        w0 = np.clip(w0, 0.001, np.pi - 0.001)
        
        alpha = np.sin(w0) / (2 * Q)
        cos_w0 = np.cos(w0)
        sqrt_A = np.sqrt(A)
        
        b0 = A * ((A + 1) + (A - 1) * cos_w0 + 2 * sqrt_A * alpha)
        b1 = -2 * A * ((A - 1) + (A + 1) * cos_w0)
        b2 = A * ((A + 1) + (A - 1) * cos_w0 - 2 * sqrt_A * alpha)
        a0 = (A + 1) - (A - 1) * cos_w0 + 2 * sqrt_A * alpha
        a1 = 2 * ((A - 1) - (A + 1) * cos_w0)
        a2 = (A + 1) - (A - 1) * cos_w0 - 2 * sqrt_A * alpha
        
        self.target_b = np.array([b0/a0, b1/a0, b2/a0])
        self.target_a = np.array([1.0, a1/a0, a2/a0])
    
    def process_sample(self, x: float) -> float:
        """Process a single sample with smoothed coefficients"""
        # Smooth coefficients towards target
        self.b += self.smoothing_factor * (self.target_b - self.b)
        self.a += self.smoothing_factor * (self.target_a - self.a)
        
        # Direct Form II Transposed
        y = self.b[0] * x + self.z1
        self.z1 = self.b[1] * x - self.a[1] * y + self.z2
        self.z2 = self.b[2] * x - self.a[2] * y
        
        return y
    
    def reset(self):
        """Reset filter state"""
        self.z1 = 0.0
        self.z2 = 0.0


class ReverbProcessor:
    """
    Algorithmic mastering reverb using Schroeder allpass-comb architecture.
    
    Optimized for mastering:
    - Clean, hi-fi sound
    - Low CPU usage
    - No memory leaks
    - Built-in high-pass and low-pass filtering
    """
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self._init_reverb_buffers()
    
    def _init_reverb_buffers(self):
        """Initialize delay lines for reverb algorithm"""
        # Allpass delay times (in samples) - prime numbers for diffusion
        self.ap_times = [
            int(0.0051 * self.sample_rate),  # ~225 samples
            int(0.0076 * self.sample_rate),  # ~335 samples
            int(0.010 * self.sample_rate),   # ~441 samples
            int(0.0123 * self.sample_rate),  # ~543 samples
        ]
        
        # Comb filter delay times (for decay)
        self.comb_times = [
            int(0.0297 * self.sample_rate),  # ~1310 samples
            int(0.0371 * self.sample_rate),  # ~1637 samples
            int(0.0411 * self.sample_rate),  # ~1812 samples
            int(0.0437 * self.sample_rate),  # ~1927 samples
        ]
        
        # Initialize buffers
        max_delay = max(max(self.ap_times), max(self.comb_times)) + 10
        self.delay_buffer_l = np.zeros(max_delay)
        self.delay_buffer_r = np.zeros(max_delay)
        self.comb_buffers_l = [np.zeros(t + 1) for t in self.comb_times]
        self.comb_buffers_r = [np.zeros(t + 1) for t in self.comb_times]
        self.ap_buffers_l = [np.zeros(t + 1) for t in self.ap_times]
        self.ap_buffers_r = [np.zeros(t + 1) for t in self.ap_times]
        
        # Buffer positions
        self.comb_pos = [0] * len(self.comb_times)
        self.ap_pos = [0] * len(self.ap_times)
    
    def process(self, audio: np.ndarray, reverb_type: str, wet_amount: float) -> np.ndarray:
        """
        Apply reverb to audio.
        
        Args:
            audio: Input audio (mono or stereo)
            reverb_type: One of 'Plate', 'Hall', 'Room', 'Chamber'
            wet_amount: 0-60 (percentage, capped at 60 for mastering)
        
        Returns:
            Processed audio with reverb
        """
        if wet_amount < 0.5 or reverb_type not in REVERB_TYPES:
            return audio
        
        # Cap at 60% for mastering-appropriate levels
        wet_amount = np.clip(wet_amount, 0, 60) / 100.0
        
        params = REVERB_TYPES[reverb_type]
        is_stereo = len(audio.shape) > 1
        
        # Pre-delay in samples
        pre_delay_samples = int(params['pre_delay_ms'] * self.sample_rate / 1000)
        
        # Calculate feedback coefficients from decay time
        # Using RT60 = -3 * decay_time / log10(feedback)
        feedback = 10 ** (-3.0 / (params['decay_time'] * self.sample_rate / 1000))
        feedback = np.clip(feedback, 0.0, 0.95)  # Safety limit
        
        # Damping coefficient
        damping = params['damping']
        
        def process_channel(channel, comb_buffers, ap_buffers):
            # Pre-filtering: High-pass to keep low end tight
            try:
                hp_freq = params['hp_freq'] / (self.sample_rate / 2)
                hp_freq = np.clip(hp_freq, 0.001, 0.999)
                b_hp, a_hp = signal.butter(2, hp_freq, 'highpass')
                filtered = signal.lfilter(b_hp, a_hp, channel)
            except:
                filtered = channel
            
            # Low-pass to darken reverb tail
            try:
                lp_freq = params['lp_freq'] / (self.sample_rate / 2)
                lp_freq = np.clip(lp_freq, 0.001, 0.999)
                b_lp, a_lp = signal.butter(2, lp_freq, 'lowpass')
                filtered = signal.lfilter(b_lp, a_lp, filtered)
            except:
                pass
            
            # Lightweight IR convolution - cap IR length for performance
            # Use shorter IR (max 0.5s) to keep CPU usage manageable
            ir_length = int(params['decay_time'] * self.sample_rate)
            ir_length = min(ir_length, int(self.sample_rate * 0.5))  # Max 0.5 seconds
            
            # Create impulse response
            t = np.arange(ir_length)
            decay_rate = -3.0 / (params['decay_time'] * self.sample_rate)
            ir = np.exp(decay_rate * t)
            
            # Add diffusion using random phase modulation
            rng = np.random.RandomState(42)  # Thread-safe, consistent reverb character
            diffusion_noise = 1 + params['diffusion'] * 0.3 * (rng.random(ir_length) - 0.5)
            ir *= diffusion_noise
            
            # Apply damping (reduce high frequencies over time)
            damping_curve = np.exp(-damping * t / ir_length)
            ir *= damping_curve
            
            # Normalize IR
            ir /= (np.sum(np.abs(ir)) + 1e-10)
            
            # Pre-delay: shift the IR
            if pre_delay_samples > 0 and pre_delay_samples < len(ir):
                ir = np.concatenate([np.zeros(pre_delay_samples), ir[:-pre_delay_samples]])
            
            # Convolve (using FFT for efficiency)
            reverb_signal = signal.fftconvolve(filtered, ir, mode='same')
            
            return reverb_signal
        
        # Process each channel
        if is_stereo:
            reverb_l = process_channel(audio[:, 0], self.comb_buffers_l, self.ap_buffers_l)
            reverb_r = process_channel(audio[:, 1], self.comb_buffers_r, self.ap_buffers_r)
            
            # Mix dry and wet with slight stereo decorrelation
            dry_amount = 1.0 - wet_amount
            output_l = audio[:, 0] * dry_amount + reverb_l * wet_amount
            output_r = audio[:, 1] * dry_amount + reverb_r * wet_amount * 0.98  # Slight decorrelation
            
            return np.column_stack((output_l, output_r))
        else:
            reverb = process_channel(audio, self.comb_buffers_l, self.ap_buffers_l)
            dry_amount = 1.0 - wet_amount
            return audio * dry_amount + reverb * wet_amount
    
    def reset(self):
        """Reset all reverb buffers"""
        self._init_reverb_buffers()


class AudioProcessor:
    """
    Professional audio processing engine with mastering-grade controls.
    
    Knobs (max ±3dB gentle processing):
    - Air: High frequency enhancement (8-16kHz shelf)
    - Body: Low-mid warmth (100-300Hz)
    - Focus: Mid presence/clarity (1-4kHz)
    - Push: Gentle saturation/compression
    - Width: Stereo width using M/S processing
    - Volume: Output level (LAST in chain)
    - Transients: Transient shaping
    - Analog: Analog-style saturation
    - Bass Punch: Low-end punch (60-120Hz)
    
    Denoiser: Psychoacoustic problem frequency minimizer
    """
    
    MODE_SPECTRAL = "Spectral (FFT)"
    MODE_TIME_DOMAIN = "Time-Domain"
    MODE_HYBRID = "Hybrid"
    
    MAX_KNOB_DB = 3.0       # ±3dB max for knobs
    MAX_EQ_GAIN_DB = 2.4    # ±2.4dB max for EQ bands
    
    def __init__(self):
        self.sample_rate = 44100
        self.audio_data = None
        self.original_audio = None
        self.is_stereo = False
        self.processing_mode = self.MODE_SPECTRAL
        
        # Oversampling
        self.oversampling_factor = 1
        
        # Denoiser state
        self.denoiser_state = DenoiserState()
        
        # Smoothed filters for EQ (9 bands)
        self._init_eq_filters()
        
        # Transient shaper state
        self._envelope_follower = 0.0
        self._transient_prev = 0.0
        
        # Reverb processor
        self.reverb_processor = ReverbProcessor(self.sample_rate)
    
    def _init_eq_filters(self):
        """Initialize smoothed EQ filters"""
        self.eq_filters = {}
        for freq in [60, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]:
            self.eq_filters[freq] = {
                'left': SmoothedFilter(self.sample_rate),
                'right': SmoothedFilter(self.sample_rate)
            }
    
    def load_audio(self, filepath: str) -> Tuple[np.ndarray, int]:
        """Load audio file"""
        self.audio_data, self.sample_rate = sf.read(filepath, dtype='float64')
        self.audio_data = np.asarray(self.audio_data, dtype=np.float64)
        self.original_audio = self.audio_data.copy()
        
        if len(self.audio_data.shape) > 1 and self.audio_data.shape[1] >= 2:
            self.is_stereo = True
        else:
            self.is_stereo = False
            if len(self.audio_data.shape) > 1:
                self.audio_data = self.audio_data.flatten()
                self.original_audio = self.original_audio.flatten()
        
        self._init_eq_filters()
        return self.audio_data.copy(), self.sample_rate
    
    def set_processing_mode(self, mode: str):
        if mode in [self.MODE_SPECTRAL, self.MODE_TIME_DOMAIN, self.MODE_HYBRID]:
            self.processing_mode = mode
    
    def set_oversampling(self, factor: int):
        if factor in [1, 2, 4, 8]:
            self.oversampling_factor = factor
    
    # =========================================================================
    # DITHERING AND FILE SAVING
    # =========================================================================
    
    def save_audio(self, filepath: str, audio_data: np.ndarray, 
                   sample_rate: int, bit_depth: int = 16,
                   dither_type: str = "TPDF"):
        """Save audio with optional dithering"""
        audio_data = np.asarray(audio_data, dtype=np.float64)
        
        if np.any(np.isnan(audio_data)) or np.any(np.isinf(audio_data)):
            audio_data = np.nan_to_num(audio_data, nan=0.0, posinf=0.9, neginf=-0.9)
        
        audio_data = np.clip(audio_data, -1.0, 1.0)
        
        if bit_depth < 32 and dither_type != "Off":
            audio_data = self._apply_dither(audio_data, bit_depth, dither_type)
        
        audio_data = np.clip(audio_data, -1.0, 1.0)
        
        subtype_map = {16: 'PCM_16', 24: 'PCM_24', 32: 'FLOAT'}
        sf.write(filepath, audio_data, sample_rate, 
                subtype=subtype_map.get(bit_depth, 'PCM_16'))
    
    def _apply_dither(self, audio: np.ndarray, bit_depth: int, 
                     dither_type: str) -> np.ndarray:
        lsb = 1.0 / (2 ** (bit_depth - 1))
        
        if dither_type == "TPDF":
            noise1 = np.random.uniform(-1, 1, audio.shape)
            noise2 = np.random.uniform(-1, 1, audio.shape)
            return audio + (noise1 + noise2) / 2 * lsb
        
        elif dither_type.startswith("POWr"):
            return self._apply_powr_dither(audio, bit_depth, dither_type)
        
        return audio
    
    def _apply_powr_dither(self, audio: np.ndarray, bit_depth: int,
                          variant: str) -> np.ndarray:
        lsb = 1.0 / (2 ** (bit_depth - 1))
        noise1 = np.random.uniform(-1, 1, audio.shape)
        noise2 = np.random.uniform(-1, 1, audio.shape)
        tpdf_noise = (noise1 + noise2) / 2 * lsb
        
        def shape_noise(noise_channel, order, cutoff):
            try:
                b, a = signal.butter(order, cutoff, 'high')
                return signal.filtfilt(b, a, noise_channel)
            except:
                return noise_channel
        
        order_cutoff = {"POWr1": (1, 0.5), "POWr2": (3, 0.4), "POWr3": (6, 0.35)}
        order, cutoff = order_cutoff.get(variant, (1, 0.5))
        
        if len(audio.shape) == 1:
            shaped_noise = shape_noise(tpdf_noise, order, cutoff)
        else:
            shaped_noise = np.column_stack([
                shape_noise(tpdf_noise[:, i], order, cutoff) 
                for i in range(audio.shape[1])
            ])
        
        return audio + shaped_noise
    
    # =========================================================================
    # OVERSAMPLING
    # =========================================================================
    
    def _upsample(self, audio: np.ndarray, factor: int) -> np.ndarray:
        if factor == 1:
            return audio
        
        is_stereo = len(audio.shape) > 1
        
        if is_stereo:
            left = signal.resample_poly(audio[:, 0], factor, 1)
            right = signal.resample_poly(audio[:, 1], factor, 1)
            return np.column_stack((left, right))
        else:
            return signal.resample_poly(audio, factor, 1)
    
    def _downsample(self, audio: np.ndarray, factor: int) -> np.ndarray:
        if factor == 1:
            return audio
        
        is_stereo = len(audio.shape) > 1
        
        if is_stereo:
            left = signal.resample_poly(audio[:, 0], 1, factor)
            right = signal.resample_poly(audio[:, 1], 1, factor)
            return np.column_stack((left, right))
        else:
            return signal.resample_poly(audio, 1, factor)
    
    # =========================================================================
    # DENOISER - Bark Scale / Fletcher-Munson based
    # =========================================================================
    
    def analyze_problematic_frequencies(self, audio: np.ndarray) -> Dict[str, float]:
        """
        Analyze audio for problematic frequencies using Bark Scale and Fletcher-Munson.
        Returns activity levels (0-1) for each frequency problem area.
        """
        if len(audio.shape) > 1:
            mono = np.mean(audio, axis=1)
        else:
            mono = audio
        
        # FFT analysis
        fft_size = 4096
        if len(mono) < fft_size:
            mono = np.pad(mono, (0, fft_size - len(mono)))
        
        window = np.hanning(fft_size)
        spectrum = np.abs(rfft(mono[:fft_size] * window))
        freqs = np.fft.rfftfreq(fft_size, 1/self.sample_rate)
        
        # Convert to dB with Fletcher-Munson weighting
        spectrum_db = 20 * np.log10(spectrum + 1e-10)
        
        # Calculate average level in each problem band
        results = {}
        
        for band_name, (low, high) in DENOISER_BANDS.items():
            mask = (freqs >= low) & (freqs <= high)
            if np.any(mask):
                band_level = np.mean(spectrum_db[mask])
                
                # Apply Fletcher-Munson sensitivity
                center_freq = (low + high) / 2
                sensitivity = self._interpolate_fm_sensitivity(center_freq)
                
                # Normalize to 0-1 range
                # Levels above -30dB are considered problematic
                normalized = np.clip((band_level + 60) / 40, 0, 1) * sensitivity
                results[band_name] = normalized
            else:
                results[band_name] = 0.0
        
        return results
    
    def _interpolate_fm_sensitivity(self, freq: float) -> float:
        """Interpolate Fletcher-Munson sensitivity for a frequency"""
        freqs = list(FLETCHER_MUNSON_SENSITIVITY.keys())
        for i, f in enumerate(freqs):
            if freq <= f:
                if i == 0:
                    return FLETCHER_MUNSON_SENSITIVITY[freqs[0]]
                prev_f = freqs[i-1]
                t = (freq - prev_f) / (f - prev_f)
                return (1-t) * FLETCHER_MUNSON_SENSITIVITY[prev_f] + t * FLETCHER_MUNSON_SENSITIVITY[f]
        return FLETCHER_MUNSON_SENSITIVITY[freqs[-1]]
    
    def apply_denoiser(self, audio: np.ndarray, sensitivity: float,
                      state: DenoiserState) -> Tuple[np.ndarray, DenoiserState]:
        """
        Apply psychoacoustic denoiser.
        
        Zero-latency, level-dependent processing.
        Dynamically minimizes problematic frequencies and restores masked frequencies.
        """
        if sensitivity <= 0:
            return audio, state
        
        sensitivity = np.clip(sensitivity, 0, 1)
        is_stereo = len(audio.shape) > 1
        
        # Analyze current audio
        levels = self.analyze_problematic_frequencies(audio)
        
        # Update state with activity levels
        state.boomy_level = levels.get('boomy', 0) if state.boomy_active else 0
        state.boxy_level = levels.get('boxy', 0) if state.boxy_active else 0
        state.muddy_level = levels.get('muddy', 0) if state.muddy_active else 0
        state.honky_level = levels.get('honky', 0) if state.honky_active else 0
        state.harsh_level = levels.get('harsh', 0) if state.harsh_active else 0
        state.sizzle_level = levels.get('sizzle', 0) if state.sizzle_active else 0
        
        # FFT-based processing for zero-latency
        fft_size = 2048
        hop_size = fft_size // 4
        window = np.hanning(fft_size)
        
        def process_channel(channel):
            pad_len = fft_size
            padded = np.concatenate([np.zeros(pad_len), channel, np.zeros(pad_len)])
            
            n_frames = (len(padded) - fft_size) // hop_size + 1
            output = np.zeros_like(padded)
            window_sum = np.zeros_like(padded)
            
            freqs = np.fft.rfftfreq(fft_size, 1/self.sample_rate)
            
            # Build reduction mask based on active bands
            reduction_mask = np.ones(len(freqs))
            
            for band_name, (low, high) in DENOISER_BANDS.items():
                active = getattr(state, f'{band_name}_active', True)
                level = getattr(state, f'{band_name}_level', 0)
                
                if active and level > 0.1:  # Only process if detected
                    # Calculate reduction (max 3dB)
                    max_reduction_db = 3.0 * sensitivity * level
                    reduction_linear = 10 ** (-max_reduction_db / 20)
                    
                    # Smooth bell-curve reduction
                    center = (low + high) / 2
                    width = (high - low) / 2
                    
                    for i, f in enumerate(freqs):
                        if low <= f <= high:
                            distance = abs(f - center) / width
                            # Cosine rolloff
                            amount = (1 + np.cos(distance * np.pi)) / 2
                            reduction_mask[i] *= 1 - (1 - reduction_linear) * amount
            
            for i in range(n_frames):
                start = i * hop_size
                frame = padded[start:start + fft_size] * window
                spectrum = rfft(frame)
                magnitude = np.abs(spectrum)
                phase = np.angle(spectrum)
                
                # Apply reduction mask
                magnitude *= reduction_mask
                
                # Restore masked frequencies (gentle high-frequency lift after reduction)
                if state.harsh_active and state.harsh_level > 0.2:
                    # Add subtle high-frequency restoration
                    for j, f in enumerate(freqs):
                        if 6000 <= f <= 16000:
                            boost = 1.0 + 0.1 * sensitivity * (1 - state.harsh_level)
                            magnitude[j] *= boost
                
                spectrum = magnitude * np.exp(1j * phase)
                output[start:start + fft_size] += irfft(spectrum, fft_size) * window
                window_sum[start:start + fft_size] += window ** 2
            
            window_sum = np.maximum(window_sum, 1e-10)
            output /= window_sum
            
            return output[pad_len:pad_len + len(channel)]
        
        if is_stereo:
            left = process_channel(audio[:, 0])
            right = process_channel(audio[:, 1])
            return np.column_stack((left, right)), state
        else:
            return process_channel(audio), state
    
    # =========================================================================
    # KNOB PROCESSING
    # =========================================================================
    
    def apply_air(self, audio: np.ndarray, amount: float) -> np.ndarray:
        """
        Air: Neve-style high frequency enhancement (8-16kHz shelf)
        Amount: -100 to +100 → -3dB to +3dB
        
        Neve characteristics:
        - Gentle slope high shelf at 12kHz (Neve 1073 style)
        - Subtle even harmonics (2nd, 4th) for silky top end
        - Smooth, musical high frequency character
        """
        if abs(amount) < 1:
            return audio
        
        gain_db = (amount / 100) * self.MAX_KNOB_DB
        
        try:
            # Neve 1073 style high shelf at 12kHz with gentle Q
            # Use proper biquad filter coefficient calculation
            freq = 12000
            w0 = 2 * np.pi * freq / self.sample_rate
            w0 = np.clip(w0, 0.001, np.pi - 0.001)
            
            # Gentler Q for smoother slope (Neve characteristic)
            A = 10 ** (gain_db / 40)
            Q = 0.5  # Lower Q = gentler slope (Neve style)
            
            alpha = np.sin(w0) / (2 * Q)
            cos_w0 = np.cos(w0)
            sqrt_A = np.sqrt(max(A, 0.001))
            
            b0 = A * ((A + 1) + (A - 1) * cos_w0 + 2 * sqrt_A * alpha)
            b1 = -2 * A * ((A - 1) + (A + 1) * cos_w0)
            b2 = A * ((A + 1) + (A - 1) * cos_w0 - 2 * sqrt_A * alpha)
            a0 = (A + 1) - (A - 1) * cos_w0 + 2 * sqrt_A * alpha
            a1 = 2 * ((A - 1) - (A + 1) * cos_w0)
            a2 = (A + 1) - (A - 1) * cos_w0 - 2 * sqrt_A * alpha
            
            # Normalize coefficients
            b = np.array([b0/a0, b1/a0, b2/a0])
            a = np.array([1.0, a1/a0, a2/a0])
            
            # Check for NaN/unstable coefficients
            if np.any(np.isnan(b)) or np.any(np.isnan(a)) or np.any(np.abs(a[1:]) > 2):
                return audio
            
            def process_channel(channel):
                # Apply high shelf using filtfilt for zero-phase
                filtered = signal.filtfilt(b, a, channel)
                
                # Add subtle even harmonics for Neve silky top (only when boosting)
                if amount > 0:
                    harmonic_amount = (amount / 100) * 0.015  # Very subtle
                    # Soft asymmetric saturation adds even harmonics
                    harmonic = harmonic_amount * np.abs(filtered) * filtered
                    filtered = filtered + harmonic
                
                # Clean up any NaN/Inf values
                filtered = np.nan_to_num(filtered, nan=0.0, posinf=0.99, neginf=-0.99)
                
                return filtered
            
            if len(audio.shape) > 1:
                left = process_channel(audio[:, 0])
                right = process_channel(audio[:, 1])
                return np.column_stack((left, right))
            else:
                return process_channel(audio)
        except:
            return audio
    
    def apply_body(self, audio: np.ndarray, amount: float) -> np.ndarray:
        """
        Body: Low-mid warmth (100-300Hz)
        Amount: -100 to +100 → -3dB to +3dB
        """
        if abs(amount) < 1:
            return audio
        
        gain_db = (amount / 100) * self.MAX_KNOB_DB
        
        # Peaking filter at 200Hz
        try:
            freq_norm = 200 / (self.sample_rate / 2)
            freq_norm = np.clip(freq_norm, 0.001, 0.999)
            Q = 0.8  # Wide Q
            
            A = 10 ** (gain_db / 40)
            w0 = 2 * np.pi * freq_norm
            alpha = np.sin(w0) / (2 * Q)
            cos_w0 = np.cos(w0)
            
            b0 = 1 + alpha * A
            b1 = -2 * cos_w0
            b2 = 1 - alpha * A
            a0 = 1 + alpha / A
            a1 = -2 * cos_w0
            a2 = 1 - alpha / A
            
            b = np.array([b0/a0, b1/a0, b2/a0])
            a = np.array([1, a1/a0, a2/a0])
            
            if len(audio.shape) > 1:
                left = signal.filtfilt(b, a, audio[:, 0])
                right = signal.filtfilt(b, a, audio[:, 1])
                return np.column_stack((left, right))
            else:
                return signal.filtfilt(b, a, audio)
        except:
            return audio
    
    def apply_focus(self, audio: np.ndarray, amount: float) -> np.ndarray:
        """
        Focus: Mid presence/clarity (1-4kHz)
        Amount: -100 to +100 → -3dB to +3dB
        """
        if abs(amount) < 1:
            return audio
        
        gain_db = (amount / 100) * self.MAX_KNOB_DB
        
        # Peaking filter at 2.5kHz
        try:
            freq_norm = 2500 / (self.sample_rate / 2)
            freq_norm = np.clip(freq_norm, 0.001, 0.999)
            Q = 1.0
            
            A = 10 ** (gain_db / 40)
            w0 = 2 * np.pi * freq_norm
            alpha = np.sin(w0) / (2 * Q)
            cos_w0 = np.cos(w0)
            
            b0 = 1 + alpha * A
            b1 = -2 * cos_w0
            b2 = 1 - alpha * A
            a0 = 1 + alpha / A
            a1 = -2 * cos_w0
            a2 = 1 - alpha / A
            
            b = np.array([b0/a0, b1/a0, b2/a0])
            a = np.array([1, a1/a0, a2/a0])
            
            if len(audio.shape) > 1:
                left = signal.filtfilt(b, a, audio[:, 0])
                right = signal.filtfilt(b, a, audio[:, 1])
                return np.column_stack((left, right))
            else:
                return signal.filtfilt(b, a, audio)
        except:
            return audio
    
    def apply_push(self, audio: np.ndarray, amount: float) -> np.ndarray:
        """
        Push: Neve-style gentle saturation/compression for energy and glue
        Amount: 0 to 100 (no negative)
        
        Neve characteristics:
        - Soft-knee saturation (not harsh at high settings)
        - Reduced harmonic content at higher settings to prevent distortion
        - Transformer-style compression (smooth, musical)
        - Should add warmth without harshness even at 100%
        """
        if amount < 1:
            return audio
        
        amount = np.clip(amount, 0, 100)
        # Use a softer curve: sqrt for gentler progression
        drive = np.sqrt(amount / 100) * 0.6  # Max effective drive reduced to 0.6
        
        def neve_saturate(x, drive_amt):
            """
            Neve-style soft-knee saturation:
            - Uses soft clipping curve that compresses gently
            - Emphasizes even harmonics (warmth) over odd (harshness)
            - Progressive compression that doesn't distort
            """
            # Soft-knee threshold
            threshold = 0.7 - drive_amt * 0.2  # Threshold lowers with drive
            
            # Calculate signal envelope for soft-knee behavior
            abs_x = np.abs(x)
            
            # Soft-knee compression: gradually compress above threshold
            # This is much gentler than hard tanh saturation
            knee_width = 0.2
            
            # Linear below threshold
            linear_region = abs_x < (threshold - knee_width)
            
            # Knee region: smooth transition
            knee_region = (abs_x >= (threshold - knee_width)) & (abs_x < (threshold + knee_width))
            
            # Compression region above threshold
            compress_region = abs_x >= (threshold + knee_width)
            
            output = np.zeros_like(x)
            
            # Linear pass-through below threshold
            output[linear_region] = x[linear_region]
            
            # Soft knee: quadratic interpolation for smooth transition
            knee_x = abs_x[knee_region]
            knee_input = (knee_x - threshold + knee_width) / (2 * knee_width)
            # Soft compression in knee
            compression = 1.0 - drive_amt * 0.3 * knee_input ** 2
            output[knee_region] = x[knee_region] * compression
            
            # Soft saturation above threshold using sinh^-1 (softer than tanh)
            compress_x = x[compress_region]
            # asinh provides softer saturation than tanh
            soft_sat = np.arcsinh(compress_x * (1 + drive_amt)) / (1 + drive_amt * 0.5)
            output[compress_region] = soft_sat
            
            # Add subtle even harmonic enhancement (Neve transformer style)
            # This adds warmth without harshness
            even_harmonic = drive_amt * 0.03 * (output ** 2) * np.sign(output)
            output = output + even_harmonic
            
            # Mix dry/wet to maintain punch at lower settings
            wet_mix = drive_amt * 0.7  # Not full wet even at max
            return x * (1 - wet_mix) + output * wet_mix
        
        if len(audio.shape) > 1:
            left = neve_saturate(audio[:, 0], drive)
            right = neve_saturate(audio[:, 1], drive)
            return np.column_stack((left, right))
        else:
            return neve_saturate(audio, drive)
    
    def apply_width(self, audio: np.ndarray, amount: float) -> np.ndarray:
        """
        Width: Neve-style stereo width using M/S processing
        Amount: 0 to 200 (100 = no change, >100 = wider, <100 = narrower)
        
        Neve characteristics:
        - Clean M/S processing with no phase issues
        - Subtle transformer-style coloration on the side channel
        - Phase-coherent expansion
        - Gentle high-frequency rolloff on extreme widening to prevent harshness
        """
        if len(audio.shape) < 2 or audio.shape[1] < 2:
            return audio  # Can't process mono
        
        width = amount / 100  # 0-2 range
        
        left = audio[:, 0]
        right = audio[:, 1]
        
        # Encode to M/S with proper gain compensation
        mid = (left + right) * 0.5
        side = (left - right) * 0.5
        
        # For extreme widening (>120%), apply gentle high-frequency rolloff 
        # to side channel to prevent harshness
        if width > 1.2:
            try:
                # Gentle low-pass on side channel to prevent harsh stereo
                lp_freq = 12000 / (self.sample_rate / 2)
                lp_freq = np.clip(lp_freq, 0.001, 0.999)
                b_lp, a_lp = signal.butter(1, lp_freq, 'lowpass')
                side = signal.filtfilt(b_lp, a_lp, side)
            except:
                pass
        
        # Adjust side level for width
        side_adjusted = side * width
        
        # Add subtle transformer coloration when widening (Neve character)
        if width > 1.0:
            transformer_amount = (width - 1.0) * 0.01  # Very subtle
            # Even harmonic enhancement on side channel
            side_adjusted = side_adjusted + transformer_amount * (side_adjusted ** 2) * np.sign(side_adjusted)
        
        # Decode back to L/R
        new_left = mid + side_adjusted
        new_right = mid - side_adjusted
        
        # Soft clip to prevent overs from width expansion
        if width > 1.0:
            clip_threshold = 0.95
            new_left = np.where(np.abs(new_left) > clip_threshold, 
                               np.tanh(new_left / clip_threshold) * clip_threshold, new_left)
            new_right = np.where(np.abs(new_right) > clip_threshold,
                                np.tanh(new_right / clip_threshold) * clip_threshold, new_right)
        
        return np.column_stack((new_left, new_right))
    
    def apply_volume(self, audio: np.ndarray, gain_db: float) -> np.ndarray:
        """
        Volume: Output level (MUST BE LAST IN CHAIN)
        Gain in dB
        """
        gain_db = np.clip(gain_db, -12, 6)
        gain_linear = 10 ** (gain_db / 20)
        return audio * gain_linear
    
    def apply_transients(self, audio: np.ndarray, amount: float) -> np.ndarray:
        """
        Transients: Neve-style transient shaping (attack/sustain control)
        Amount: -100 to +100 (+ = more attack, - = more sustain)
        
        Neve characteristics:
        - Smoother attack/release curves (musical, not clinical)
        - Soft saturation on boosted peaks
        - Natural envelope following
        - Program-dependent response
        """
        if abs(amount) < 1:
            return audio
        
        amount = np.clip(amount, -100, 100)
        
        # Neve-style envelope follower with program-dependent timing
        # Slower, more musical response than clinical transient shapers
        if amount > 0:
            attack_ms = 2.0   # Slightly slower attack for musical response
            release_ms = 80.0  # Longer release for smooth decay
        else:
            attack_ms = 15.0  # Slower attack when softening
            release_ms = 150.0  # Very smooth release for sustain
        
        attack_coef = np.exp(-1.0 / (self.sample_rate * attack_ms / 1000))
        release_coef = np.exp(-1.0 / (self.sample_rate * release_ms / 1000))
        
        def process_channel(channel):
            envelope = np.zeros_like(channel)
            env = 0.0
            
            for i, x in enumerate(channel):
                abs_x = abs(x)
                if abs_x > env:
                    env = attack_coef * env + (1 - attack_coef) * abs_x
                else:
                    env = release_coef * env
                envelope[i] = env
            
            # Smooth the envelope for more musical response
            try:
                smooth_samples = int(0.003 * self.sample_rate)  # 3ms smoothing
                kernel = np.ones(smooth_samples) / smooth_samples
                envelope = np.convolve(envelope, kernel, mode='same')
            except:
                pass
            
            # Differentiate envelope to detect transients
            diff = np.diff(envelope, prepend=envelope[0])
            
            # Smooth the diff for gentler response
            try:
                diff = np.convolve(diff, kernel, mode='same')
            except:
                pass
            
            # Apply transient shaping with soft-knee response
            strength = abs(amount) / 100
            
            if amount > 0:  # Boost transients (attack)
                # Soft-knee boost with saturation on peaks
                transient_detect = np.clip(diff * 8, 0, 1)
                # Soft-knee curve for smooth boost
                boost = transient_detect ** 0.7  # Sub-linear for soft knee
                gain = 1.0 + boost * strength * 0.4
                
                output = channel * gain
                
                # Apply Neve-style soft saturation on boosted peaks
                peak_threshold = 0.8
                peaks = np.abs(output) > peak_threshold
                if np.any(peaks):
                    # Soft clip the peaks
                    output[peaks] = np.sign(output[peaks]) * (
                        peak_threshold + (1 - peak_threshold) * np.tanh(
                            (np.abs(output[peaks]) - peak_threshold) / (1 - peak_threshold)
                        )
                    )
                return output
            else:  # Reduce transients (sustain)
                # Smoother reduction for natural sustain
                transient_detect = np.clip(diff * 6, 0, 1)
                reduction = transient_detect ** 0.8  # Soft knee
                gain = 1.0 - reduction * strength * 0.25
                return channel * gain
        
        if len(audio.shape) > 1:
            left = process_channel(audio[:, 0])
            right = process_channel(audio[:, 1])
            return np.column_stack((left, right))
        else:
            return process_channel(audio)
    
    def apply_analog(self, audio: np.ndarray, amount: float) -> np.ndarray:
        """
        Analog: Neve transformer-style saturation/warmth
        Amount: 0 to 100
        
        Neve characteristics:
        - Strong even harmonic emphasis (2nd, 4th - warmth)
        - Controlled odd harmonics (3rd - presence)
        - Transformer-style low-frequency warmth
        - Gentle high-frequency rolloff above 20kHz
        - Soft-knee clipping behavior
        """
        if amount < 1:
            return audio
        
        amount = np.clip(amount, 0, 100) / 100
        
        def neve_analog(x, amt):
            """
            Neve transformer emulation:
            - Asymmetric saturation for even harmonics
            - Frequency-dependent saturation (more on lows)
            - Subtle high-end rolloff
            """
            # Scale amount for gentler effect
            effective_amt = amt * 0.5  # Max 50% saturation blend
            
            # Asymmetric saturation curve (Neve transformer characteristic)
            # Positive half: slightly more compression
            # Negative half: slightly less compression
            # This asymmetry creates even harmonics
            pos_drive = 1 + effective_amt * 1.5
            neg_drive = 1 + effective_amt * 1.2
            
            # Use arcsinh for softer saturation than tanh
            positive = np.arcsinh(x * pos_drive) / pos_drive
            negative = np.arcsinh(x * neg_drive) / neg_drive
            saturated = np.where(x >= 0, positive, negative)
            
            # Add explicit even harmonic content (2nd harmonic)
            # This is the "warmth" of analog gear
            second_harmonic = effective_amt * 0.04 * (x ** 2) * np.sign(x)
            
            # Add subtle 3rd harmonic for presence (but less than 2nd)
            third_harmonic = effective_amt * 0.015 * (x ** 3)
            
            # Combine with careful mixing
            output = saturated + second_harmonic + third_harmonic
            
            # Mix dry/wet for transparency at lower settings
            wet_mix = effective_amt * 0.6
            return x * (1 - wet_mix) + output * wet_mix
        
        # Apply frequency-dependent saturation
        # More saturation on low frequencies (transformer behavior)
        try:
            # Split into low and high bands
            crossover = 500 / (self.sample_rate / 2)
            crossover = np.clip(crossover, 0.001, 0.999)
            b_lp, a_lp = signal.butter(2, crossover, 'lowpass')
            b_hp, a_hp = signal.butter(2, crossover, 'highpass')
            
            def process_channel(channel):
                low = signal.filtfilt(b_lp, a_lp, channel)
                high = signal.filtfilt(b_hp, a_hp, channel)
                
                # More saturation on lows (Neve transformer)
                low_saturated = neve_analog(low, amount * 1.3)
                # Less saturation on highs to prevent harshness
                high_saturated = neve_analog(high, amount * 0.7)
                
                return low_saturated + high_saturated
            
            if len(audio.shape) > 1:
                left = process_channel(audio[:, 0])
                right = process_channel(audio[:, 1])
                return np.column_stack((left, right))
            else:
                return process_channel(audio)
        except:
            # Fallback to simple processing
            if len(audio.shape) > 1:
                left = neve_analog(audio[:, 0], amount)
                right = neve_analog(audio[:, 1], amount)
                return np.column_stack((left, right))
            else:
                return neve_analog(audio, amount)
    
    def apply_bass_punch(self, audio: np.ndarray, amount: float) -> np.ndarray:
        """
        Bass Punch: Neve 1073 style low-end enhancement (60-120Hz)
        Amount: 0 to 100
        
        Neve 1073 characteristics:
        - Warm low shelf at 60Hz (selectable on 1073)
        - Even harmonic enhancement for weight
        - Tight, controlled punch (not boomy)
        - Transformer-style bass saturation
        - Musical transient enhancement
        """
        if amount < 1:
            return audio
        
        amount = np.clip(amount, 0, 100) / 100
        
        try:
            # Neve 1073 style low shelf at 60Hz
            shelf_freq = 60 / (self.sample_rate / 2)
            shelf_freq = np.clip(shelf_freq, 0.001, 0.999)
            
            # Low frequency crossover for multiband processing
            cross_freq = 150 / (self.sample_rate / 2)
            cross_freq = np.clip(cross_freq, 0.001, 0.999)
            
            # Design low shelf filter for bass boost (Neve 1073 @ 60Hz)
            gain_db = amount * 2.5  # Max +2.5dB boost
            A = 10 ** (gain_db / 40)
            w0 = 2 * np.pi * shelf_freq
            Q = 0.6  # Lower Q for gentle slope (Neve style)
            
            alpha = np.sin(w0) / (2 * Q)
            cos_w0 = np.cos(w0)
            sqrt_A = np.sqrt(A)
            
            b0 = A * ((A + 1) - (A - 1) * cos_w0 + 2 * sqrt_A * alpha)
            b1 = 2 * A * ((A - 1) - (A + 1) * cos_w0)
            b2 = A * ((A + 1) - (A - 1) * cos_w0 - 2 * sqrt_A * alpha)
            a0 = (A + 1) + (A - 1) * cos_w0 + 2 * sqrt_A * alpha
            a1 = -2 * ((A - 1) + (A + 1) * cos_w0)
            a2 = (A + 1) + (A - 1) * cos_w0 - 2 * sqrt_A * alpha
            
            b_shelf = np.array([b0/a0, b1/a0, b2/a0])
            a_shelf = np.array([1.0, a1/a0, a2/a0])
            
            # Crossover filter
            b_lp, a_lp = signal.butter(3, cross_freq, 'lowpass')
            
            def process_channel(channel):
                # Apply low shelf EQ
                shelved = signal.filtfilt(b_shelf, a_shelf, channel)
                
                # Extract bass for additional processing
                low = signal.filtfilt(b_lp, a_lp, shelved)
                high = shelved - low
                
                # Neve transformer bass saturation (even harmonics for warmth)
                # Gentle asymmetric saturation
                if amount > 0.3:
                    sat_amount = (amount - 0.3) * 0.3  # Only above 30%
                    # Asymmetric for even harmonics
                    low_sat = low + sat_amount * 0.05 * (low ** 2) * np.sign(low)
                    low = low_sat
                
                # Musical transient enhancement on bass
                # Slower, more musical timing than standard transient shaper
                envelope = np.zeros_like(low)
                env = 0.0
                attack = np.exp(-1.0 / (self.sample_rate * 0.003))  # 3ms attack
                release = np.exp(-1.0 / (self.sample_rate * 0.08))  # 80ms release
                
                for i, x in enumerate(low):
                    abs_x = abs(x)
                    if abs_x > env:
                        env = attack * env + (1 - attack) * abs_x
                    else:
                        env = release * env
                    envelope[i] = env
                
                # Smooth diff for musical response
                diff = np.diff(envelope, prepend=envelope[0])
                smooth_len = int(0.002 * self.sample_rate)  # 2ms smoothing
                if smooth_len > 1:
                    kernel = np.ones(smooth_len) / smooth_len
                    diff = np.convolve(diff, kernel, mode='same')
                
                # Soft-knee transient boost
                transient = np.clip(diff * 15, 0, 1) ** 0.8  # Sub-linear for soft knee
                gain = 1.0 + transient * amount * 0.35  # Max +35% gain on transients
                
                return low * gain + high
            
            if len(audio.shape) > 1:
                left = process_channel(audio[:, 0])
                right = process_channel(audio[:, 1])
                return np.column_stack((left, right))
            else:
                return process_channel(audio)
        except:
            return audio
    
    # =========================================================================
    # EQ - Artifact-free with parameter smoothing
    # =========================================================================
    
    def apply_eq(self, audio: np.ndarray, eq_settings: Dict[int, float]) -> np.ndarray:
        """
        Apply EQ with maximum ±2.4dB per band.
        Uses VECTORIZED scipy.signal.filtfilt for fast offline processing.
        """
        if not eq_settings:
            return audio
        
        is_stereo = len(audio.shape) > 1
        processed = audio.copy()
        
        for freq, gain_db in eq_settings.items():
            gain_db = np.clip(gain_db, -self.MAX_EQ_GAIN_DB, self.MAX_EQ_GAIN_DB)
            
            if abs(gain_db) < 0.05:
                continue
            
            # Skip frequencies too close to Nyquist
            if freq >= self.sample_rate * 0.45:
                continue
            
            # Design peaking EQ filter coefficients using Audio EQ Cookbook formulas
            try:
                Q = 1.0
                A = 10 ** (gain_db / 40)
                
                # w0 = 2*pi*f0/Fs (digital angular frequency)
                w0 = 2 * np.pi * freq / self.sample_rate
                w0 = np.clip(w0, 0.01, np.pi - 0.01)  # Keep away from boundaries
                
                alpha = np.sin(w0) / (2 * Q)
                cos_w0 = np.cos(w0)
                
                b0 = 1 + alpha * A
                b1 = -2 * cos_w0
                b2 = 1 - alpha * A
                a0 = 1 + alpha / A
                a1 = -2 * cos_w0
                a2 = 1 - alpha / A
                
                # Normalize coefficients
                b = np.array([b0/a0, b1/a0, b2/a0])
                a = np.array([1.0, a1/a0, a2/a0])
                
                # Check for filter stability
                if np.any(np.isnan(b)) or np.any(np.isnan(a)):
                    continue
                if np.any(np.abs(a[1:]) > 2):  # Basic stability check
                    continue
                
                # VECTORIZED filtering - much faster than sample-by-sample
                if is_stereo:
                    processed[:, 0] = signal.filtfilt(b, a, processed[:, 0])
                    processed[:, 1] = signal.filtfilt(b, a, processed[:, 1])
                else:
                    processed = signal.filtfilt(b, a, processed)
            except Exception:
                # Skip this band if filter design fails
                continue
        
        return processed
    
    # =========================================================================
    # REVERB - Mastering-grade algorithmic reverb
    # =========================================================================
    
    def apply_reverb(self, audio: np.ndarray, reverb_type: str, wet_amount: float) -> np.ndarray:
        """
        Apply mastering-grade reverb.
        
        Args:
            audio: Input audio (mono or stereo)
            reverb_type: One of 'Plate', 'Hall', 'Room', 'Chamber'
            wet_amount: 0-60 (percentage, capped at 60% for mastering)
        
        Returns:
            Processed audio with reverb
        """
        return self.reverb_processor.process(audio, reverb_type, wet_amount)
    
    # =========================================================================
    # MAIN PROCESSING PIPELINE
    # =========================================================================
    
    def process_audio(self, audio: np.ndarray, settings: dict, 
                     progress_callback: callable = None) -> np.ndarray:
        """
        Main processing pipeline with optional progress callback.
        Signal Chain: Input → Denoiser → EQ → Air/Body/Focus/Push/Transients/Analog/Bass Punch → REVERB → Width → Volume
        
        Args:
            audio: Input audio array
            settings: Processing settings dictionary
            progress_callback: Optional callback(int) for progress updates (0-100)
        """
        def report_progress(pct):
            if progress_callback:
                try:
                    progress_callback(int(pct))
                except:
                    pass
        
        report_progress(5)
        factor = self.oversampling_factor
        
        # Upsample if needed
        if factor > 1:
            audio = self._upsample(audio, factor)
        
        report_progress(10)
        processed = audio.copy()
        
        # 1. DENOISER (first in chain) - can be slow for long files, process in chunks
        denoiser_sens = settings.get('denoiser_sensitivity', 0)
        if denoiser_sens > 0:
            self.denoiser_state.boomy_active = settings.get('denoiser_boomy', True)
            self.denoiser_state.boxy_active = settings.get('denoiser_boxy', True)
            self.denoiser_state.muddy_active = settings.get('denoiser_muddy', True)
            self.denoiser_state.honky_active = settings.get('denoiser_honky', True)
            self.denoiser_state.harsh_active = settings.get('denoiser_harsh', True)
            self.denoiser_state.sizzle_active = settings.get('denoiser_sizzle', True)
            
            # Process denoiser in chunks for long files
            chunk_size = 44100 * 10  # 10 seconds at 44.1kHz
            if len(processed) > chunk_size:
                report_progress(15)
                chunks = []
                num_chunks = (len(processed) + chunk_size - 1) // chunk_size
                for i in range(num_chunks):
                    start = i * chunk_size
                    end = min((i + 1) * chunk_size, len(processed))
                    chunk = processed[start:end]
                    chunk_processed, self.denoiser_state = self.apply_denoiser(
                        chunk, denoiser_sens, self.denoiser_state
                    )
                    chunks.append(chunk_processed)
                    report_progress(15 + (i + 1) / num_chunks * 15)  # 15-30%
                processed = np.concatenate(chunks, axis=0)
            else:
                processed, self.denoiser_state = self.apply_denoiser(
                    processed, denoiser_sens, self.denoiser_state
                )
        
        report_progress(35)
        
        # 2. EQ (max ±2.4dB) - now vectorized, fast
        eq_settings = settings.get('eq_settings', {})
        if eq_settings:
            processed = self.apply_eq(processed, eq_settings)
        
        report_progress(45)
        
        # 3. Knob processing (max ±3dB each) - all vectorized
        processed = self.apply_air(processed, settings.get('air', 0))
        report_progress(50)
        processed = self.apply_body(processed, settings.get('body', 0))
        report_progress(55)
        processed = self.apply_focus(processed, settings.get('focus', 0))
        report_progress(60)
        processed = self.apply_push(processed, settings.get('push', 0))
        report_progress(65)
        processed = self.apply_transients(processed, settings.get('transients', 0))
        report_progress(70)
        processed = self.apply_analog(processed, settings.get('analog', 0))
        report_progress(75)
        processed = self.apply_bass_punch(processed, settings.get('bass_punch', 0))
        report_progress(78)
        
        # 4. REVERB (after knobs, before width)
        reverb_type = settings.get('reverb_type', 'Plate')
        reverb_amount = settings.get('reverb', 0)
        if reverb_amount > 0:
            processed = self.apply_reverb(processed, reverb_type, reverb_amount)
        report_progress(82)
        
        # 5. WIDTH (stereo processing)
        processed = self.apply_width(processed, settings.get('width', 100))
        report_progress(85)
        
        # 5. VOLUME (LAST in chain)
        processed = self.apply_volume(processed, settings.get('volume', 0))
        report_progress(90)
        
        # Downsample if needed
        if factor > 1:
            processed = self._downsample(processed, factor)
        
        report_progress(95)
        
        # Soft clip to prevent overs
        processed = np.tanh(processed * 0.95) / 0.95
        processed = np.clip(processed, -1.0, 1.0)
        
        report_progress(100)
        return processed
    
    # =========================================================================
    # UTILITIES
    # =========================================================================
    
    def normalize_audio(self, audio: np.ndarray, target_db: float = -1.0) -> np.ndarray:
        peak = np.max(np.abs(audio))
        if peak < 1e-10:
            return audio
        target_linear = 10 ** (target_db / 20)
        return audio * (target_linear / peak)
    
    def convert_to_mono(self, audio: np.ndarray) -> np.ndarray:
        if len(audio.shape) > 1 and audio.shape[1] >= 2:
            return np.mean(audio, axis=1)
        return audio
    
    def get_spectrum(self, audio: np.ndarray, fft_size: int = 4096) -> Tuple[np.ndarray, np.ndarray]:
        if len(audio.shape) > 1:
            audio = audio[:, 0]
        
        if len(audio) > fft_size:
            start = (len(audio) - fft_size) // 2
            audio = audio[start:start + fft_size]
        
        window = np.hanning(len(audio))
        spectrum = rfft(audio * window)
        magnitude_db = 20 * np.log10(np.abs(spectrum) + 1e-10)
        freqs = np.fft.rfftfreq(len(audio), 1/self.sample_rate)
        
        return freqs, magnitude_db
    
    def get_denoiser_state(self) -> DenoiserState:
        return self.denoiser_state
    
    def get_denoiser_levels(self) -> Dict[str, float]:
        """Get current denoiser detection levels for GUI display"""
        return {
            'boomy': self.denoiser_state.boomy_level,
            'boxy': self.denoiser_state.boxy_level,
            'muddy': self.denoiser_state.muddy_level,
            'honky': self.denoiser_state.honky_level,
            'harsh': self.denoiser_state.harsh_level,
            'sizzle': self.denoiser_state.sizzle_level,
        }
    
    def resample_audio(self, audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Resample audio to target sample rate"""
        if orig_sr == target_sr:
            return audio
        
        is_stereo = len(audio.shape) > 1
        
        # Calculate resample ratio
        ratio = target_sr / orig_sr
        new_length = int(len(audio) * ratio)
        
        if is_stereo:
            left = signal.resample(audio[:, 0], new_length)
            right = signal.resample(audio[:, 1], new_length)
            return np.column_stack((left, right))
        else:
            return signal.resample(audio, new_length)
    
    def process_chunk_lightweight(self, chunk: np.ndarray, settings: dict) -> np.ndarray:
        """
        Process a single audio chunk with minimal memory footprint.
        Used for streaming export. Simpler than full process_audio - 
        no oversampling, optimized for sequential chunk processing.
        """
        processed = chunk  # Don't copy initially
        
        # 1. EQ (max ±2.4dB) - fast vectorized
        eq_settings = settings.get('eq_settings', {})
        if eq_settings:
            processed = self.apply_eq(processed, eq_settings)
        
        # 2. Knob processing (max ±3dB each)
        if abs(settings.get('air', 0)) >= 1:
            processed = self.apply_air(processed, settings.get('air', 0))
        if abs(settings.get('body', 0)) >= 1:
            processed = self.apply_body(processed, settings.get('body', 0))
        if abs(settings.get('focus', 0)) >= 1:
            processed = self.apply_focus(processed, settings.get('focus', 0))
        if settings.get('push', 0) >= 1:
            processed = self.apply_push(processed, settings.get('push', 0))
        if abs(settings.get('transients', 0)) >= 1:
            processed = self.apply_transients(processed, settings.get('transients', 0))
        if settings.get('analog', 0) >= 1:
            processed = self.apply_analog(processed, settings.get('analog', 0))
        if settings.get('bass_punch', 0) >= 1:
            processed = self.apply_bass_punch(processed, settings.get('bass_punch', 0))
        
        # 3. REVERB (after knobs, before width)
        reverb_type = settings.get('reverb_type', 'Plate')
        reverb_amount = settings.get('reverb', 0)
        if reverb_amount > 0:
            processed = self.apply_reverb(processed, reverb_type, reverb_amount)
        
        # 4. WIDTH (stereo processing)
        width = settings.get('width', 100)
        if width != 100:
            processed = self.apply_width(processed, width)
        
        # 5. VOLUME (LAST in chain)
        vol = settings.get('volume', 0)
        if abs(vol) > 0.01:
            processed = self.apply_volume(processed, vol)
        
        # Soft clip to prevent overs
        processed = np.tanh(processed * 0.95) / 0.95
        processed = np.clip(processed, -1.0, 1.0)
        
        return processed


class StreamingExporter:
    """
    Memory-efficient streaming audio exporter.
    
    Processes audio in small chunks and writes directly to disk,
    never holding more than 2-3 chunks in memory at once.
    
    FIXED v4.1.1: Eliminated beat skip / audio corruption at the start
    by using proper overlap-add with Hann-window crossfading between chunks.
    The previous approach had a flawed overlap strategy that caused
    discontinuities at chunk boundaries, especially at the beginning.
    
    New approach:
    - Each chunk overlaps previous/next by OVERLAP samples
    - Chunks are windowed with a Hann crossfade in the overlap regions
    - This guarantees seamless, artifact-free transitions
    - No filter warm-up needed since filtfilt is zero-phase
    """
    
    # Chunk size in seconds
    CHUNK_SECONDS = 2.0
    # Overlap for crossfade (in seconds) - needs to be long enough
    # for smooth transitions. 50ms is enough for zero-phase filters.
    OVERLAP_SECONDS = 0.05
    
    def __init__(self, processor: AudioProcessor):
        self.processor = processor
        self._cancelled = False
    
    def cancel(self):
        """Cancel the export operation"""
        self._cancelled = True
    
    def export_streaming(
        self,
        input_path: str,
        output_path: str,
        settings: dict,
        target_sample_rate: int = 96000,
        bit_depth: int = 24,
        dither_type: str = "TPDF",
        progress_callback: Callable[[int], None] = None
    ) -> bool:
        """
        Stream-based export using overlap-add with Hann crossfade.
        
        Each chunk:
        1. Read [hop_start ... hop_start + chunk_size + overlap] from input
        2. Process the full chunk (denoiser + EQ + knobs + effects)
        3. Apply crossfade window in overlap zones
        4. Resample if needed
        5. Add overlapping parts together, write non-overlapping body to disk
        
        This eliminates the beat-skip / corruption at start of export.
        """
        def report_progress(pct):
            if progress_callback:
                try:
                    progress_callback(int(pct))
                except:
                    pass
        
        self._cancelled = False
        report_progress(0)
        
        # Get input file info
        with sf.SoundFile(input_path, 'r') as infile:
            source_sr = infile.samplerate
            channels = infile.channels
            total_frames = len(infile)
            is_stereo = channels >= 2
        
        # Chunk and overlap sizes in source-rate samples
        chunk_samples = int(self.CHUNK_SECONDS * source_sr)
        overlap_samples = int(self.OVERLAP_SECONDS * source_sr)
        # Hop = how far we advance each iteration (non-overlapping body)
        hop_samples = chunk_samples - overlap_samples
        
        # Calculate output parameters
        resample_ratio = target_sample_rate / source_sr
        
        # Track peak for normalization
        peak_amplitude = 0.0
        temp_output_path = output_path + '.tmp'
        
        # Denoiser pre-analysis
        denoiser_sens = settings.get('denoiser_sensitivity', 0)
        if denoiser_sens > 0:
            with sf.SoundFile(input_path, 'r') as infile:
                sample_size = min(total_frames, int(source_sr * 5))
                sample_audio = infile.read(sample_size, dtype='float64')
                if is_stereo and len(sample_audio.shape) == 1:
                    sample_audio = sample_audio.reshape(-1, 1)
                
                self.processor.denoiser_state.boomy_active = settings.get('denoiser_boomy', True)
                self.processor.denoiser_state.boxy_active = settings.get('denoiser_boxy', True)
                self.processor.denoiser_state.muddy_active = settings.get('denoiser_muddy', True)
                self.processor.denoiser_state.honky_active = settings.get('denoiser_honky', True)
                self.processor.denoiser_state.harsh_active = settings.get('denoiser_harsh', True)
                self.processor.denoiser_state.sizzle_active = settings.get('denoiser_sizzle', True)
                
                self.processor.analyze_problematic_frequencies(sample_audio)
                del sample_audio
                gc.collect()
        
        report_progress(5)
        
        # PASS 1: Process chunks with overlap-add and write to temp file
        try:
            subtype_map = {16: 'PCM_16', 24: 'PCM_24', 32: 'FLOAT'}
            
            with sf.SoundFile(input_path, 'r') as infile:
                with sf.SoundFile(
                    temp_output_path, 'w',
                    samplerate=target_sample_rate,
                    channels=channels,
                    subtype=subtype_map.get(bit_depth, 'PCM_24'),
                    format='WAV'
                ) as outfile:
                    
                    read_pos = 0  # Current read position in source file
                    chunk_index = 0
                    # Buffer holding the fade-out tail from previous chunk (in output rate)
                    prev_tail = None
                    
                    while read_pos < total_frames:
                        if self._cancelled:
                            # Clean up
                            import os
                            try:
                                outfile.close()
                                infile.close()
                            except:
                                pass
                            if os.path.exists(temp_output_path):
                                os.remove(temp_output_path)
                            return False
                        
                        # How many frames to read this iteration
                        frames_remaining = total_frames - read_pos
                        frames_to_read = min(chunk_samples, frames_remaining)
                        
                        infile.seek(read_pos)
                        chunk = infile.read(frames_to_read, dtype='float64')
                        
                        if len(chunk) == 0:
                            break
                        
                        actual_len = len(chunk)
                        
                        # Ensure correct shape for stereo
                        if is_stereo and len(chunk.shape) == 1:
                            chunk = np.column_stack((chunk, chunk))
                        elif not is_stereo and len(chunk.shape) > 1:
                            chunk = chunk[:, 0]
                        
                        # Apply denoiser if enabled
                        if denoiser_sens > 0 and len(chunk) > 2048:
                            chunk, _ = self.processor.apply_denoiser(
                                chunk, denoiser_sens, self.processor.denoiser_state
                            )
                        
                        # Process chunk (EQ, knobs, width, volume)
                        processed = self.processor.process_chunk_lightweight(chunk, settings)
                        del chunk
                        
                        # Resample if needed
                        if source_sr != target_sample_rate:
                            output_length = int(len(processed) * resample_ratio)
                            if output_length < 1:
                                output_length = 1
                            if is_stereo:
                                left = signal.resample(processed[:, 0], output_length)
                                right = signal.resample(processed[:, 1], output_length)
                                processed = np.column_stack((left, right))
                                del left, right
                            else:
                                processed = signal.resample(processed, output_length)
                        
                        out_len = len(processed)
                        out_overlap = int(overlap_samples * resample_ratio)
                        out_overlap = min(out_overlap, out_len)  # Safety clamp
                        
                        is_first = (chunk_index == 0)
                        is_last = (read_pos + actual_len >= total_frames)
                        
                        if is_first and is_last:
                            # Only one chunk - write everything
                            write_buf = processed
                        elif is_first:
                            # First chunk: write body, store tail for crossfade
                            body_end = out_len - out_overlap
                            write_buf = processed[:body_end]
                            # Store the fade-out tail
                            prev_tail = processed[body_end:].copy()
                        elif is_last:
                            # Last chunk: crossfade head with prev_tail, write rest
                            if prev_tail is not None and out_overlap > 0:
                                xfade_len = min(len(prev_tail), out_overlap, out_len)
                                # Create crossfade weights
                                fade_out = np.linspace(1.0, 0.0, xfade_len)
                                fade_in = np.linspace(0.0, 1.0, xfade_len)
                                
                                if is_stereo:
                                    fade_out_2d = fade_out[:, np.newaxis]
                                    fade_in_2d = fade_in[:, np.newaxis]
                                    xfade = prev_tail[:xfade_len] * fade_out_2d + processed[:xfade_len] * fade_in_2d
                                else:
                                    xfade = prev_tail[:xfade_len] * fade_out + processed[:xfade_len] * fade_in
                                
                                write_buf = np.concatenate([xfade, processed[xfade_len:]], axis=0)
                            else:
                                write_buf = processed
                            prev_tail = None
                        else:
                            # Middle chunk: crossfade head with prev_tail,
                            # write body, store new tail
                            body_end = out_len - out_overlap
                            
                            if prev_tail is not None and out_overlap > 0:
                                xfade_len = min(len(prev_tail), out_overlap, out_len)
                                fade_out = np.linspace(1.0, 0.0, xfade_len)
                                fade_in = np.linspace(0.0, 1.0, xfade_len)
                                
                                if is_stereo:
                                    fade_out_2d = fade_out[:, np.newaxis]
                                    fade_in_2d = fade_in[:, np.newaxis]
                                    xfade = prev_tail[:xfade_len] * fade_out_2d + processed[:xfade_len] * fade_in_2d
                                else:
                                    xfade = prev_tail[:xfade_len] * fade_out + processed[:xfade_len] * fade_in
                                
                                # Write crossfaded region + body (up to tail)
                                write_buf = np.concatenate([xfade, processed[xfade_len:body_end]], axis=0)
                            else:
                                write_buf = processed[:body_end]
                            
                            # Store the new fade-out tail
                            prev_tail = processed[body_end:].copy()
                        
                        # Track peak
                        if len(write_buf) > 0:
                            chunk_peak = np.max(np.abs(write_buf))
                            peak_amplitude = max(peak_amplitude, chunk_peak)
                            outfile.write(write_buf)
                        
                        del processed, write_buf
                        gc.collect()
                        
                        # Advance by hop (overlap will be re-read in next chunk)
                        read_pos += hop_samples
                        chunk_index += 1
                        
                        progress = min(70, int((read_pos / total_frames) * 70))
                        report_progress(progress)
            
            report_progress(75)
            
            # PASS 2: Normalize and apply dither
            target_peak = 10 ** (-1.0 / 20)  # -1dB
            normalize_gain = target_peak / max(peak_amplitude, 1e-10)
            
            if abs(normalize_gain - 1.0) > 0.001 or dither_type != "Off":
                import os
                
                with sf.SoundFile(temp_output_path, 'r') as infile:
                    with sf.SoundFile(
                        output_path, 'w',
                        samplerate=target_sample_rate,
                        channels=channels,
                        subtype=subtype_map.get(bit_depth, 'PCM_24'),
                        format='WAV'
                    ) as outfile:
                        
                        frames_processed = 0
                        total_output_frames = len(infile)
                        normalize_chunk_size = int(target_sample_rate * 2)
                        
                        while frames_processed < total_output_frames:
                            if self._cancelled:
                                return False
                            
                            chunk = infile.read(normalize_chunk_size, dtype='float64')
                            if len(chunk) == 0:
                                break
                            
                            chunk = chunk * normalize_gain
                            chunk = np.clip(chunk, -1.0, 1.0)
                            
                            if bit_depth < 32 and dither_type != "Off":
                                chunk = self.processor._apply_dither(chunk, bit_depth, dither_type)
                                chunk = np.clip(chunk, -1.0, 1.0)
                            
                            outfile.write(chunk)
                            
                            del chunk
                            gc.collect()
                            
                            frames_processed += normalize_chunk_size
                            progress = 75 + int((frames_processed / total_output_frames) * 25)
                            report_progress(min(99, progress))
                
                os.remove(temp_output_path)
            else:
                import os
                if os.path.exists(output_path):
                    os.remove(output_path)
                os.rename(temp_output_path, output_path)
            
            report_progress(100)
            gc.collect()
            return True
            
        except Exception as e:
            import os
            if os.path.exists(temp_output_path):
                try:
                    os.remove(temp_output_path)
                except:
                    pass
            raise e


# Backwards compatibility
class GentleAudioProcessor(AudioProcessor):
    pass
