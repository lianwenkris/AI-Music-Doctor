
"""
AI Music Doctor - Automatic Audio Analyzer
Analyzes audio for common AI-generated music issues
Similar to iZotope Ozone's Master Assistant

Version: 2.0.0
"""

import numpy as np
from scipy import signal
from scipy.fft import rfft
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from enum import Enum


class IssueLevel(Enum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    SEVERE = 4


@dataclass
class AnalysisResult:
    """Container for audio analysis results"""
    
    # Overall score (0-100, higher is better)
    overall_score: float = 100.0
    
    # Issue levels
    noise_level: IssueLevel = IssueLevel.NONE
    artifact_level: IssueLevel = IssueLevel.NONE
    muddiness_level: IssueLevel = IssueLevel.NONE
    harshness_level: IssueLevel = IssueLevel.NONE
    sibilance_level: IssueLevel = IssueLevel.NONE
    metallic_level: IssueLevel = IssueLevel.NONE
    dynamic_range_issue: IssueLevel = IssueLevel.NONE
    phase_issue: IssueLevel = IssueLevel.NONE
    
    # Detailed metrics
    noise_floor_db: float = -96.0
    peak_db: float = 0.0
    rms_db: float = -20.0
    dynamic_range_db: float = 20.0
    crest_factor_db: float = 15.0
    stereo_correlation: float = 1.0  # 1 = mono compatible, -1 = out of phase
    
    # Frequency analysis
    bass_energy: float = 0.0  # 20-200 Hz
    low_mid_energy: float = 0.0  # 200-500 Hz
    mid_energy: float = 0.0  # 500-2000 Hz
    high_mid_energy: float = 0.0  # 2000-6000 Hz
    high_energy: float = 0.0  # 6000-20000 Hz
    
    # Problematic frequency ranges
    problem_frequencies: List[Tuple[int, int, str]] = field(default_factory=list)
    
    # Detected AI service (best guess)
    detected_service: str = "Unknown"
    service_confidence: float = 0.0
    
    # Suggested preset
    suggested_preset: str = "Default"
    
    # Suggested settings
    suggested_settings: Dict[str, float] = field(default_factory=dict)
    
    # Human-readable issues
    issues: List[str] = field(default_factory=list)
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    
    @property
    def metrics(self) -> Dict[str, float]:
        """Return metrics as dictionary for easy access"""
        return {
            'peak_db': self.peak_db,
            'rms_db': self.rms_db,
            'noise_floor_db': self.noise_floor_db,
            'dynamic_range_db': self.dynamic_range_db,
            'crest_factor_db': self.crest_factor_db,
            'stereo_correlation': self.stereo_correlation,
            'bass_energy': self.bass_energy,
            'low_mid_energy': self.low_mid_energy,
            'mid_energy': self.mid_energy,
            'high_mid_energy': self.high_mid_energy,
            'high_energy': self.high_energy,
        }


class AudioAnalyzer:
    """Analyzes audio for AI-generated music artifacts and issues"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.nyquist = sample_rate / 2
    
    def analyze(self, audio: np.ndarray, sample_rate: int = None) -> AnalysisResult:
        """Perform comprehensive audio analysis"""
        
        if sample_rate:
            self.sample_rate = sample_rate
            self.nyquist = sample_rate / 2
        
        result = AnalysisResult()
        
        # Ensure float64 and handle stereo
        audio = np.asarray(audio, dtype=np.float64)
        if len(audio.shape) > 1:
            mono = np.mean(audio, axis=1)
            is_stereo = True
        else:
            mono = audio
            is_stereo = False
        
        # Basic level analysis
        self._analyze_levels(mono, result)
        
        # Frequency analysis
        self._analyze_frequency_balance(mono, result)
        
        # Noise analysis
        self._analyze_noise(mono, result)
        
        # Artifact detection
        self._analyze_artifacts(mono, result)
        
        # Stereo analysis
        if is_stereo:
            self._analyze_stereo(audio, result)
        
        # Detect AI service
        self._detect_ai_service(result)
        
        # Generate suggestions
        self._generate_suggestions(result)
        
        # Calculate overall score
        self._calculate_overall_score(result)
        
        return result
    
    def _analyze_levels(self, audio: np.ndarray, result: AnalysisResult):
        """Analyze audio levels"""
        
        # Peak level
        peak = np.max(np.abs(audio))
        result.peak_db = 20 * np.log10(peak + 1e-10)
        
        # RMS level
        rms = np.sqrt(np.mean(audio ** 2))
        result.rms_db = 20 * np.log10(rms + 1e-10)
        
        # Crest factor (dynamic range indicator)
        result.crest_factor_db = result.peak_db - result.rms_db
        
        # Estimate noise floor (lowest 5% of RMS in short frames)
        frame_size = int(0.05 * self.sample_rate)  # 50ms frames
        frames = len(audio) // frame_size
        
        if frames > 10:
            frame_rms = []
            for i in range(frames):
                frame = audio[i * frame_size:(i + 1) * frame_size]
                frame_rms.append(np.sqrt(np.mean(frame ** 2)))
            
            # Noise floor is the 5th percentile
            noise_floor = np.percentile(frame_rms, 5)
            result.noise_floor_db = 20 * np.log10(noise_floor + 1e-10)
        
        # Dynamic range
        result.dynamic_range_db = result.peak_db - result.noise_floor_db
        
        # Check for dynamic range issues
        if result.crest_factor_db < 6:
            result.dynamic_range_issue = IssueLevel.HIGH
            result.issues.append("Over-compressed: Very low dynamic range detected")
        elif result.crest_factor_db < 10:
            result.dynamic_range_issue = IssueLevel.MEDIUM
            result.issues.append("Somewhat compressed: Limited dynamic range")
    
    def _analyze_frequency_balance(self, audio: np.ndarray, result: AnalysisResult):
        """Analyze frequency balance across bands"""
        
        # FFT analysis
        window_size = min(len(audio), 32768)
        if len(audio) > window_size:
            # Use middle section
            start = (len(audio) - window_size) // 2
            audio_chunk = audio[start:start + window_size]
        else:
            audio_chunk = audio
        
        window = np.hanning(len(audio_chunk))
        spectrum = np.abs(rfft(audio_chunk * window))
        frequencies = np.fft.rfftfreq(len(audio_chunk), 1 / self.sample_rate)
        
        # Convert to dB
        spectrum_db = 20 * np.log10(spectrum + 1e-10)
        
        # Calculate energy in bands
        def band_energy(low, high):
            mask = (frequencies >= low) & (frequencies < high)
            if np.any(mask):
                return np.mean(spectrum_db[mask])
            return -96
        
        result.bass_energy = band_energy(20, 200)
        result.low_mid_energy = band_energy(200, 500)
        result.mid_energy = band_energy(500, 2000)
        result.high_mid_energy = band_energy(2000, 6000)
        result.high_energy = band_energy(6000, 20000)
        
        # Normalize to overall energy
        avg_energy = np.mean([result.bass_energy, result.low_mid_energy, 
                            result.mid_energy, result.high_mid_energy, result.high_energy])
        
        # Check for muddiness (excessive low-mids 200-400 Hz)
        muddy_energy = band_energy(200, 400)
        if muddy_energy > avg_energy + 6:
            result.muddiness_level = IssueLevel.HIGH
            result.issues.append("Muddy low-mids: Excessive energy in 200-400 Hz range")
            result.problem_frequencies.append((200, 400, "Muddy"))
        elif muddy_energy > avg_energy + 3:
            result.muddiness_level = IssueLevel.MEDIUM
            result.issues.append("Slight muddiness in 200-400 Hz range")
            result.problem_frequencies.append((200, 400, "Slightly muddy"))
        
        # Check for harshness (excessive energy 2-5 kHz)
        harsh_energy = band_energy(2000, 5000)
        if harsh_energy > avg_energy + 8:
            result.harshness_level = IssueLevel.HIGH
            result.issues.append("Harsh upper-mids: Excessive energy in 2-5 kHz range")
            result.problem_frequencies.append((2000, 5000, "Harsh"))
        elif harsh_energy > avg_energy + 4:
            result.harshness_level = IssueLevel.MEDIUM
            result.issues.append("Somewhat harsh in 2-5 kHz range")
            result.problem_frequencies.append((2000, 5000, "Slightly harsh"))
        
        # Check for sibilance (excessive 5-8 kHz)
        sibilant_energy = band_energy(5000, 8000)
        if sibilant_energy > avg_energy + 6:
            result.sibilance_level = IssueLevel.HIGH
            result.issues.append("Excessive sibilance: Too much energy in 5-8 kHz")
            result.problem_frequencies.append((5000, 8000, "Sibilant"))
        elif sibilant_energy > avg_energy + 3:
            result.sibilance_level = IssueLevel.MEDIUM
            result.problem_frequencies.append((5000, 8000, "Slightly sibilant"))
        
        # Check for metallic sheen (excessive 8-12 kHz)
        metallic_energy = band_energy(8000, 12000)
        if metallic_energy > avg_energy + 5:
            result.metallic_level = IssueLevel.HIGH
            result.issues.append("Metallic sheen: Excessive energy in 8-12 kHz range")
            result.problem_frequencies.append((8000, 12000, "Metallic"))
        elif metallic_energy > avg_energy + 2:
            result.metallic_level = IssueLevel.MEDIUM
            result.problem_frequencies.append((8000, 12000, "Slightly metallic"))
        
        # Check for missing highs (AI often cuts above 16kHz)
        if result.high_energy < avg_energy - 15:
            result.issues.append("Missing high frequencies: Audio may be bandwidth-limited")
    
    def _analyze_noise(self, audio: np.ndarray, result: AnalysisResult):
        """Analyze noise levels"""
        
        # Use spectral flatness to detect noise
        window_size = 2048
        hop_size = window_size // 2
        
        flatness_values = []
        
        for i in range(0, len(audio) - window_size, hop_size):
            frame = audio[i:i + window_size]
            spectrum = np.abs(rfft(frame * np.hanning(window_size)))
            
            # Spectral flatness (Wiener entropy)
            geometric_mean = np.exp(np.mean(np.log(spectrum + 1e-10)))
            arithmetic_mean = np.mean(spectrum)
            
            if arithmetic_mean > 0:
                flatness = geometric_mean / arithmetic_mean
                flatness_values.append(flatness)
        
        if flatness_values:
            avg_flatness = np.mean(flatness_values)
            
            # High flatness indicates more noise-like content
            if avg_flatness > 0.3:
                result.noise_level = IssueLevel.HIGH
                result.issues.append("High noise/hiss levels detected")
            elif avg_flatness > 0.2:
                result.noise_level = IssueLevel.MEDIUM
                result.issues.append("Moderate noise levels detected")
            elif avg_flatness > 0.1:
                result.noise_level = IssueLevel.LOW
    
    def _analyze_artifacts(self, audio: np.ndarray, result: AnalysisResult):
        """Detect AI-specific artifacts"""
        
        # Analyze spectral variance (artifacts often have unusual spectral patterns)
        window_size = 2048
        hop_size = 512
        
        spectra = []
        for i in range(0, len(audio) - window_size, hop_size):
            frame = audio[i:i + window_size]
            spectrum = np.abs(rfft(frame * np.hanning(window_size)))
            spectra.append(spectrum)
        
        if len(spectra) > 10:
            spectra = np.array(spectra)
            
            # Calculate spectral variance
            spectral_var = np.var(spectra, axis=0)
            mean_variance = np.mean(spectral_var)
            
            # High variance in specific bands indicates artifacts
            freq_bins = np.fft.rfftfreq(window_size, 1 / self.sample_rate)
            
            # Check 2-5kHz band (common artifact region)
            artifact_mask = (freq_bins >= 2000) & (freq_bins <= 5000)
            artifact_variance = np.mean(spectral_var[artifact_mask])
            
            if artifact_variance > mean_variance * 3:
                result.artifact_level = IssueLevel.HIGH
                result.issues.append("Significant AI artifacts detected in 2-5 kHz range")
            elif artifact_variance > mean_variance * 2:
                result.artifact_level = IssueLevel.MEDIUM
                result.issues.append("Moderate AI artifacts detected")
            elif artifact_variance > mean_variance * 1.5:
                result.artifact_level = IssueLevel.LOW
    
    def _analyze_stereo(self, audio: np.ndarray, result: AnalysisResult):
        """Analyze stereo field and phase"""
        
        left = audio[:, 0]
        right = audio[:, 1]
        
        # Correlation coefficient
        correlation = np.corrcoef(left, right)[0, 1]
        result.stereo_correlation = correlation
        
        # Check for phase issues
        if correlation < 0.5:
            result.phase_issue = IssueLevel.MEDIUM
            result.issues.append("Phase correlation issues: May have mono compatibility problems")
        elif correlation < 0:
            result.phase_issue = IssueLevel.HIGH
            result.issues.append("Severe phase issues: Audio may cancel in mono")
    
    def _detect_ai_service(self, result: AnalysisResult):
        """Attempt to detect which AI service generated the audio"""
        
        # Suno characteristics: metallic sheen, muffled bass, phase issues
        suno_score = 0
        if result.metallic_level.value >= IssueLevel.MEDIUM.value:
            suno_score += 30
        if result.muddiness_level.value >= IssueLevel.MEDIUM.value:
            suno_score += 20
        if result.phase_issue.value >= IssueLevel.MEDIUM.value:
            suno_score += 20
        if result.bass_energy < result.mid_energy - 5:
            suno_score += 15
        
        # Udio characteristics: vocal-instrumental blending, drum artifacts
        udio_score = 0
        if result.harshness_level.value >= IssueLevel.MEDIUM.value:
            udio_score += 25
        if result.artifact_level.value >= IssueLevel.MEDIUM.value:
            udio_score += 25
        # Udio tends to have cleaner highs
        if result.high_energy > result.mid_energy - 3:
            udio_score += 15
        
        # Tunee characteristics: robotic vocals, pronunciation artifacts
        tunee_score = 0
        if result.harshness_level.value >= IssueLevel.HIGH.value:
            tunee_score += 30
        if result.sibilance_level.value >= IssueLevel.MEDIUM.value:
            tunee_score += 25
        if result.artifact_level.value >= IssueLevel.HIGH.value:
            tunee_score += 20
        
        # Determine most likely service
        scores = {
            "Suno": suno_score,
            "Udio": udio_score,
            "Tunee": tunee_score
        }
        
        max_service = max(scores, key=scores.get)
        max_score = scores[max_service]
        
        if max_score >= 40:
            result.detected_service = max_service
            result.service_confidence = min(max_score / 100, 0.9)
        else:
            result.detected_service = "Unknown"
            result.service_confidence = 0.0
    
    def _generate_suggestions(self, result: AnalysisResult):
        """Generate suggested settings based on analysis - GENTLE philosophy"""
        
        settings = {
            'in_gain': 0.0,
            'out_gain': 0.0,
            'hiss_noise_removal': 0.0,
            'artifact_cleanup': 0.0,
            'freq_suppression': 0.0,
            'freq_range': (2000, 5000)
        }
        
        recommendations = []
        
        # Noise reduction - GENTLE: Much lower values than before
        if result.noise_level.value >= IssueLevel.HIGH.value:
            settings['hiss_noise_removal'] = 0.30  # Reduced from 0.60
            recommendations.append("Apply gentle noise reduction (30%)")
        elif result.noise_level.value >= IssueLevel.MEDIUM.value:
            settings['hiss_noise_removal'] = 0.20  # Reduced from 0.40
            recommendations.append("Apply subtle noise reduction (20%)")
        elif result.noise_level.value >= IssueLevel.LOW.value:
            settings['hiss_noise_removal'] = 0.10  # Reduced from 0.25
            recommendations.append("Apply minimal noise reduction (10%)")
        
        # Artifact cleanup - GENTLE: Much lower values
        if result.artifact_level.value >= IssueLevel.HIGH.value:
            settings['artifact_cleanup'] = 0.25  # Reduced from 0.55
            recommendations.append("Apply gentle artifact cleanup (25%)")
        elif result.artifact_level.value >= IssueLevel.MEDIUM.value:
            settings['artifact_cleanup'] = 0.15  # Reduced from 0.40
            recommendations.append("Apply subtle artifact cleanup (15%)")
        elif result.artifact_level.value >= IssueLevel.LOW.value:
            settings['artifact_cleanup'] = 0.10  # Reduced from 0.25
        
        # Frequency suppression - GENTLE: Max 2dB reduction
        if result.harshness_level.value >= IssueLevel.MEDIUM.value:
            settings['freq_suppression'] = 0.20  # Reduced from 0.45
            settings['freq_range'] = (2000, 5000)
            recommendations.append("Gently reduce harsh frequencies (2-5 kHz)")
        elif result.metallic_level.value >= IssueLevel.MEDIUM.value:
            settings['freq_suppression'] = 0.25  # Reduced from 0.50
            settings['freq_range'] = (6000, 12000)
            recommendations.append("Gently reduce metallic frequencies (6-12 kHz)")
        elif result.sibilance_level.value >= IssueLevel.MEDIUM.value:
            settings['freq_suppression'] = 0.15  # Reduced from 0.40
            settings['freq_range'] = (5000, 8000)
            recommendations.append("Gently de-ess sibilant frequencies (5-8 kHz)")
        
        # Input gain if too quiet
        if result.rms_db < -24:
            settings['in_gain'] = min(6, -result.rms_db - 18)
            recommendations.append(f"Boost input gain by {settings['in_gain']:.1f} dB")
        
        # Output gain to prevent clipping
        if result.peak_db > -1:
            settings['out_gain'] = -2.0
        
        # Suggested preset
        if result.detected_service != "Unknown" and result.service_confidence > 0.5:
            result.suggested_preset = result.detected_service
            recommendations.insert(0, f"Use {result.detected_service} preset as starting point")
        elif result.harshness_level.value >= IssueLevel.HIGH.value:
            result.suggested_preset = "De-Harsh"
        elif result.noise_level.value >= IssueLevel.HIGH.value:
            result.suggested_preset = "Heavy Cleanup"
        elif result.metallic_level.value >= IssueLevel.HIGH.value:
            result.suggested_preset = "Suno"
        else:
            result.suggested_preset = "Default"
        
        result.suggested_settings = settings
        result.recommendations = recommendations
    
    def _calculate_overall_score(self, result: AnalysisResult):
        """Calculate overall audio quality score"""
        
        score = 100.0
        
        # Deduct for issues
        score -= result.noise_level.value * 5
        score -= result.artifact_level.value * 8
        score -= result.muddiness_level.value * 4
        score -= result.harshness_level.value * 6
        score -= result.sibilance_level.value * 4
        score -= result.metallic_level.value * 5
        score -= result.dynamic_range_issue.value * 5
        score -= result.phase_issue.value * 7
        
        # Bonus for good characteristics
        if result.crest_factor_db >= 10 and result.crest_factor_db <= 18:
            score += 5  # Good dynamic range
        
        if result.stereo_correlation >= 0.7:
            score += 3  # Good mono compatibility
        
        result.overall_score = max(0, min(100, score))
    
    def get_analysis_summary(self, result: AnalysisResult) -> str:
        """Get human-readable analysis summary"""
        
        lines = []
        lines.append(f"=== Audio Analysis Report ===")
        lines.append(f"Overall Quality Score: {result.overall_score:.0f}/100")
        lines.append("")
        
        if result.detected_service != "Unknown":
            lines.append(f"Detected AI Service: {result.detected_service} "
                        f"(confidence: {result.service_confidence:.0%})")
            lines.append("")
        
        lines.append("--- Levels ---")
        lines.append(f"Peak: {result.peak_db:.1f} dB")
        lines.append(f"RMS: {result.rms_db:.1f} dB")
        lines.append(f"Noise Floor: {result.noise_floor_db:.1f} dB")
        lines.append(f"Dynamic Range: {result.crest_factor_db:.1f} dB")
        lines.append("")
        
        if result.issues:
            lines.append("--- Issues Detected ---")
            for issue in result.issues:
                lines.append(f"• {issue}")
            lines.append("")
        
        if result.recommendations:
            lines.append("--- Recommendations ---")
            for rec in result.recommendations:
                lines.append(f"→ {rec}")
            lines.append("")
        
        lines.append(f"Suggested Preset: {result.suggested_preset}")
        
        return "\n".join(lines)

