<uploaded_files github_repo=mixdoktorz-bit/AI-Music-Doctor>
<file=AI_MUSIC_DOCTOR V1.3/ai_music_doctor/test_export_bug2.py>
#!/usr/bin/env python3
"""
Test for BUG 2: Export beat skip / audio corruption at the beginning.

Tests the StreamingExporter with all combinations of:
- Bit depths: 16, 24, 32-bit float
- Sample rates: 44100, 48000, 88200, 96000

For each combination:
1. Generate a test tone (440 Hz sine wave, 3 seconds)
2. Export using StreamingExporter 
3. Read back exported audio
4. Check first 100ms for corruption (discontinuities, zero-crossings, amplitude jumps)
5. Check chunk boundaries for discontinuities
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import numpy as np
import soundfile as sf
import tempfile
from audio_processor import AudioProcessor, StreamingExporter

SAMPLE_RATES = [44100, 48000, 88200, 96000]
BIT_DEPTHS = [16, 24, 32]

def generate_test_audio(sr, duration=3.0, freq=440.0):
    """Generate a stereo sine wave test signal."""
    t = np.arange(int(sr * duration)) / sr
    left = 0.5 * np.sin(2 * np.pi * freq * t)
    right = 0.5 * np.sin(2 * np.pi * freq * t * 1.01)  # Slightly detuned
    return np.column_stack((left, right))

def check_discontinuities(audio, sr, label="", threshold=0.05):
    """Check for sample-to-sample jumps that indicate corruption."""
    issues = []
    
    # Check first 100ms
    first_100ms = int(sr * 0.1)
    first_segment = audio[:first_100ms]
    
    if len(first_segment) < 2:
        issues.append(f"{label}: Too short")
        return issues
    
    # Check for large sample-to-sample jumps (discontinuities)
    diff = np.diff(first_segment, axis=0)
    max_jump = np.max(np.abs(diff))
    
    # For a 440Hz sine at 0.5 amplitude, max expected diff per sample:
    # d/dt[0.5*sin(2*pi*440*t)] = 0.5*2*pi*440*cos(...) 
    # max = 0.5*2*pi*440/sr
    max_expected = 0.5 * 2 * np.pi * 440 / sr * 2.0  # 2x headroom for processing
    
    if max_jump > max(threshold, max_expected * 5):
        issues.append(f"{label}: Large discontinuity in first 100ms: max_jump={max_jump:.6f} (expected <{max_expected:.6f})")
    
    # Check that first few samples aren't silence/zero (indicating data loss)
    first_10ms = audio[:int(sr * 0.01)]
    if len(first_10ms) > 0:
        rms_first = np.sqrt(np.mean(first_10ms ** 2))
        rms_full = np.sqrt(np.mean(audio[:int(sr * 0.5)] ** 2))
        if rms_full > 0.01 and rms_first < rms_full * 0.1:
            issues.append(f"{label}: First 10ms is much quieter ({rms_first:.6f}) than overall ({rms_full:.6f}) - possible corruption")
    
    # Check for chunk boundaries (every ~2 seconds of output)
    chunk_boundary_samples = int(sr * 2.0)
    if len(audio) > chunk_boundary_samples + 100:
        boundary_region = audio[chunk_boundary_samples - 50:chunk_boundary_samples + 50]
        boundary_diff = np.diff(boundary_region, axis=0)
        boundary_max_jump = np.max(np.abs(boundary_diff))
        if boundary_max_jump > max(threshold, max_expected * 5):
            issues.append(f"{label}: Discontinuity at chunk boundary (~2s): max_jump={boundary_max_jump:.6f}")
    
    return issues

def test_export(source_sr, target_sr, bit_depth):
    """Test export with specific settings."""
    label = f"src={source_sr}Hz -> dst={target_sr}Hz, {bit_depth}bit"
    
    # Generate test audio
    audio = generate_test_audio(source_sr, duration=3.0)
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        input_path = f.name
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        output_path = f.name
    
    try:
        # Write source
        sf.write(input_path, audio, source_sr, subtype='FLOAT')
        
        # Export using StreamingExporter
        processor = AudioProcessor()
        exporter = StreamingExporter(processor)
        
        # Minimal processing settings (just pass-through effectively)
        settings = {
            'air': 0, 'body': 0, 'focus': 0, 'push': 0,
            'width': 100, 'volume': 0, 'transients': 0, 'analog': 0,
            'bass_punch': 0, 'reverb_amount': 0, 'reverb_type': 'Plate',
            'denoiser_sensitivity': 0,
            'eq_bands': {60: 0, 125: 0, 250: 0, 500: 0, 1000: 0, 2000: 0, 4000: 0, 8000: 0, 16000: 0}
        }
        
        dither = "Off" if bit_depth == 32 else "TPDF"
        
        success = exporter.export_streaming(
            input_path, output_path, settings,
            target_sample_rate=target_sr,
            bit_depth=bit_depth,
            dither_type=dither
        )
        
        if not success:
            return [f"{label}: Export returned False"]
        
        # Read back and check
        exported, exported_sr = sf.read(output_path, dtype='float64')
        
        if exported_sr != target_sr:
            return [f"{label}: Wrong sample rate: {exported_sr} != {target_sr}"]
        
        issues = check_discontinuities(exported, exported_sr, label)
        
        # Check output length is roughly correct
        expected_duration = 3.0
        actual_duration = len(exported) / exported_sr
        if abs(actual_duration - expected_duration) > 0.1:
            issues.append(f"{label}: Duration mismatch: {actual_duration:.3f}s vs expected {expected_duration:.3f}s")
        
        return issues
        
    finally:
        os.unlink(input_path)
        if os.path.exists(output_path):
            os.unlink(output_path)
        # Clean up temp files
        for suffix in ['.tmp']:
            tmp = output_path + suffix
            if os.path.exists(tmp):
                os.unlink(tmp)

def main():
    all_issues = []
    total_tests = 0
    passed = 0
    
    print("=" * 70)
    print("BUG 2 TEST: Export Beat Skip / Audio Corruption")
    print("=" * 70)
    
    for source_sr in [44100, 48000]:  # Common source rates
        for target_sr in SAMPLE_RATES:
            for bit_depth in BIT_DEPTHS:
                total_tests += 1
                label = f"src={source_sr} -> dst={target_sr}, {bit_depth}bit"
                print(f"Testing {label}...", end=" ", flush=True)
                
                try:
                    issues = test_export(source_sr, target_sr, bit_depth)
                    if issues:
                        print("FAIL")
                        for issue in issues:
                            print(f"  ❌ {issue}")
                        all_issues.extend(issues)
                    else:
                        print("PASS ✓")
                        passed += 1
                except Exception as e:
                    print(f"ERROR: {e}")
                    all_issues.append(f"{label}: Exception: {e}")
    
    print("\n" + "=" * 70)
    print(f"Results: {passed}/{total_tests} passed")
    if all_issues:
        print(f"\n{len(all_issues)} issues found:")
        for issue in all_issues:
            print(f"  ❌ {issue}")
        return 1
    else:
        print("All tests PASSED! ✓")
        return 0

if __name__ == '__main__':
    sys.exit(main())

</file>

</uploaded_files>
