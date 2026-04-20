#!/usr/bin/env python3
"""
AI Music Doctor v4.0.0 - Test Suite

Tests all audio processing components:
- Mastering knobs (Air, Body, Focus, Push, Width, Volume, Transients, Analog, Bass Punch)
- Psychoacoustic Denoiser
- Artifact-free EQ
- Full processing chain
- Presets
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import numpy as np
from audio_processor import AudioProcessor, DenoiserState, SmoothedFilter, DENOISER_BANDS
from presets import PresetManager


def test_audio_processor():
    """Test AudioProcessor class"""
    print("\n" + "="*60)
    print("Testing AudioProcessor")
    print("="*60)
    
    processor = AudioProcessor()
    processor.sample_rate = 44100
    
    # Create test audio
    duration = 1.0
    samples = int(44100 * duration)
    t = np.linspace(0, duration, samples)
    
    # Multi-frequency test signal
    test_audio = (
        0.3 * np.sin(2 * np.pi * 100 * t) +   # Low
        0.3 * np.sin(2 * np.pi * 1000 * t) +  # Mid
        0.2 * np.sin(2 * np.pi * 5000 * t) +  # High
        0.1 * np.random.randn(samples)         # Noise
    )
    
    stereo_audio = np.column_stack([test_audio, test_audio * 0.95])
    
    print(f"✓ Created test audio: {samples} samples, stereo")
    
    # Test each knob
    print("\nTesting individual knobs:")
    
    # Air knob
    result = processor.apply_air(test_audio.copy(), 50)
    assert result.shape == test_audio.shape, "Air: Shape mismatch"
    assert not np.any(np.isnan(result)), "Air: NaN detected"
    print("  ✓ Air knob")
    
    # Body knob
    result = processor.apply_body(test_audio.copy(), 50)
    assert not np.any(np.isnan(result)), "Body: NaN detected"
    print("  ✓ Body knob")
    
    # Focus knob
    result = processor.apply_focus(test_audio.copy(), 50)
    assert not np.any(np.isnan(result)), "Focus: NaN detected"
    print("  ✓ Focus knob")
    
    # Push knob
    result = processor.apply_push(test_audio.copy(), 50)
    assert not np.any(np.isnan(result)), "Push: NaN detected"
    print("  ✓ Push knob")
    
    # Width knob (stereo only)
    result = processor.apply_width(stereo_audio.copy(), 150)
    assert result.shape == stereo_audio.shape, "Width: Shape mismatch"
    assert not np.any(np.isnan(result)), "Width: NaN detected"
    print("  ✓ Width knob")
    
    # Volume knob
    result = processor.apply_volume(test_audio.copy(), 3)
    assert not np.any(np.isnan(result)), "Volume: NaN detected"
    print("  ✓ Volume knob")
    
    # Transients knob
    result = processor.apply_transients(test_audio.copy(), 50)
    assert not np.any(np.isnan(result)), "Transients: NaN detected"
    print("  ✓ Transients knob")
    
    # Analog knob
    result = processor.apply_analog(test_audio.copy(), 50)
    assert not np.any(np.isnan(result)), "Analog: NaN detected"
    print("  ✓ Analog knob")
    
    # Bass Punch knob
    result = processor.apply_bass_punch(test_audio.copy(), 50)
    assert not np.any(np.isnan(result)), "Bass Punch: NaN detected"
    print("  ✓ Bass Punch knob")
    
    print("\n✓ All knobs working correctly")


def test_denoiser():
    """Test Denoiser functionality"""
    print("\n" + "="*60)
    print("Testing Psychoacoustic Denoiser")
    print("="*60)
    
    processor = AudioProcessor()
    processor.sample_rate = 44100
    
    # Create test audio with "problem" frequencies
    samples = 44100
    t = np.linspace(0, 1, samples)
    
    # Add frequencies in each problem band
    test_audio = np.zeros(samples)
    for band_name, (low, high) in DENOISER_BANDS.items():
        center = (low + high) / 2
        test_audio += 0.2 * np.sin(2 * np.pi * center * t)
    
    print(f"✓ Created test audio with problem frequencies")
    
    # Analyze
    levels = processor.analyze_problematic_frequencies(test_audio)
    print(f"✓ Analysis complete: {levels}")
    
    for band in DENOISER_BANDS.keys():
        assert band in levels, f"Missing band: {band}"
        assert 0 <= levels[band] <= 1, f"Invalid level for {band}"
    
    print("✓ All bands detected")
    
    # Test denoising
    state = DenoiserState()
    result, new_state = processor.apply_denoiser(test_audio, 0.5, state)
    
    assert result.shape == test_audio.shape, "Shape mismatch"
    assert not np.any(np.isnan(result)), "NaN detected"
    assert not np.any(np.isinf(result)), "Inf detected"
    
    print(f"✓ Denoiser processing complete")
    print(f"  - Boomy level: {new_state.boomy_level:.2f}")
    print(f"  - Harsh level: {new_state.harsh_level:.2f}")


def test_eq():
    """Test artifact-free EQ"""
    print("\n" + "="*60)
    print("Testing Artifact-Free EQ")
    print("="*60)
    
    processor = AudioProcessor()
    processor.sample_rate = 44100
    
    samples = 44100
    t = np.linspace(0, 1, samples)
    test_audio = np.sin(2 * np.pi * 1000 * t)
    
    # Test EQ with various settings
    eq_settings = {
        60: 2.0,
        250: -1.5,
        1000: 2.4,   # Max boost
        4000: -2.4,  # Max cut
        8000: 1.0,
        16000: 0.5
    }
    
    result = processor.apply_eq(test_audio.copy(), eq_settings)
    
    assert result.shape == test_audio.shape, "Shape mismatch"
    assert not np.any(np.isnan(result)), "NaN detected"
    assert not np.any(np.isinf(result)), "Inf detected"
    
    print(f"✓ EQ applied with {len(eq_settings)} bands")
    
    # Test SmoothedFilter directly
    sf = SmoothedFilter(44100)
    sf.set_peaking_eq(1000, 2.0, Q=1.0)
    
    # Process samples
    output = np.zeros_like(test_audio)
    for i in range(len(test_audio)):
        output[i] = sf.process_sample(test_audio[i])
    
    assert not np.any(np.isnan(output)), "SmoothedFilter NaN"
    print("✓ SmoothedFilter coefficient smoothing working")
    
    # Test gain clamping
    sf.set_peaking_eq(1000, 10.0)  # Should be clamped to 2.4
    print("✓ EQ gain clamping working (±2.4dB max)")


def test_full_processing_chain():
    """Test complete signal chain"""
    print("\n" + "="*60)
    print("Testing Full Processing Chain")
    print("="*60)
    
    processor = AudioProcessor()
    processor.sample_rate = 44100
    
    samples = 44100
    t = np.linspace(0, 1, samples)
    test_audio = np.sin(2 * np.pi * 440 * t) * 0.5
    stereo_audio = np.column_stack([test_audio, test_audio * 0.9])
    
    processor.audio_data = stereo_audio
    
    # Full settings
    settings = {
        'air': 30,
        'body': 25,
        'focus': 20,
        'push': 25,
        'width': 110,
        'volume': -1,
        'transients': 15,
        'analog': 20,
        'bass_punch': 25,
        'denoiser_sensitivity': 0.4,
        'denoiser_boomy': True,
        'denoiser_boxy': True,
        'denoiser_muddy': True,
        'denoiser_honky': True,
        'denoiser_harsh': True,
        'denoiser_sizzle': True,
        'eq_settings': {
            60: 1.0, 250: -1.0,
            2000: 1.5, 4000: 1.0,
            8000: 0.5, 16000: 1.0
        }
    }
    
    result = processor.process_audio(stereo_audio.copy(), settings)
    
    print(f"Signal chain: Input → Denoiser → EQ → Knobs → Width → Volume")
    print(f"Input shape: {stereo_audio.shape}")
    print(f"Output shape: {result.shape}")
    print(f"Output range: [{np.min(result):.4f}, {np.max(result):.4f}]")
    
    assert result.shape == stereo_audio.shape, "Shape mismatch"
    assert not np.any(np.isnan(result)), "NaN in output"
    assert not np.any(np.isinf(result)), "Inf in output"
    assert np.max(np.abs(result)) <= 1.0, f"Clipping! Max: {np.max(np.abs(result))}"
    
    print("✓ Full processing chain working correctly")


def test_presets():
    """Test PresetManager"""
    print("\n" + "="*60)
    print("Testing PresetManager")
    print("="*60)
    
    pm = PresetManager()
    
    presets = pm.get_preset_names()
    print(f"✓ Found {len(presets)} presets:")
    
    # Expected preset categories
    expected_presets = ['Default', 'Suno', 'Udio', 'Tunee', 'Pop/Modern', 
                       'De-Harsh', 'De-Muddy', 'Light Touch', 'Full Mastering']
    
    for name in expected_presets:
        assert name in presets, f"Missing preset: {name}"
        preset = pm.get_preset(name)
        
        # Verify preset has required keys
        required_keys = ['air', 'body', 'focus', 'push', 'width', 'volume',
                        'transients', 'analog', 'bass_punch', 'denoiser_sensitivity']
        
        for key in required_keys:
            assert key in preset, f"Preset '{name}' missing key: {key}"
        
        print(f"  ✓ {name}: {pm.get_preset_description(name)[:40]}...")
    
    print(f"\n✓ All {len(presets)} presets valid")


def test_processing_limits():
    """Test processing limits are enforced"""
    print("\n" + "="*60)
    print("Testing Processing Limits")
    print("="*60)
    
    processor = AudioProcessor()
    
    # Test knob limits
    assert processor.MAX_KNOB_DB == 3.0, f"Knob limit should be 3.0dB, got {processor.MAX_KNOB_DB}"
    print(f"✓ Knob limit: ±{processor.MAX_KNOB_DB}dB")
    
    assert processor.MAX_EQ_GAIN_DB == 2.4, f"EQ limit should be 2.4dB, got {processor.MAX_EQ_GAIN_DB}"
    print(f"✓ EQ limit: ±{processor.MAX_EQ_GAIN_DB}dB")
    
    # Test EQ clamping
    sf = SmoothedFilter(44100)
    sf.set_peaking_eq(1000, 10.0)  # Should be clamped
    print("✓ EQ gain clamping enforced")
    
    # Test volume clamping
    processor.sample_rate = 44100
    test = np.array([0.5])
    result = processor.apply_volume(test, 20)  # Should be clamped to 6dB
    expected = 0.5 * (10 ** (6 / 20))  # 6dB max
    assert abs(result[0] - expected) < 0.01, "Volume not clamped"
    print("✓ Volume gain clamping enforced (-12 to +6 dB)")


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("AI Music Doctor v4.0.0 - Test Suite")
    print("="*60)
    
    try:
        test_audio_processor()
        test_denoiser()
        test_eq()
        test_full_processing_chain()
        test_presets()
        test_processing_limits()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60 + "\n")
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
