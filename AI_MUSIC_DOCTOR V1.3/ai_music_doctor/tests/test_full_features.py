<uploaded_files github_repo=mixdoktorz-bit/AI-Music-Doctor>
<file=AI_MUSIC_DOCTOR V1.3/ai_music_doctor/test_full_features.py>
#!/usr/bin/env python3
"""Full feature test for AI Music Doctor v4.0"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import numpy as np
import soundfile as sf
import tempfile

from audio_processor import AudioProcessor, StreamingExporter, DenoiserState
from presets import PresetManager

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        print(f"  ✓ {name}")
        PASS += 1
    else:
        print(f"  ❌ {name} {detail}")
        FAIL += 1

def make_audio(sr=44100, dur=2.0):
    t = np.arange(int(sr * dur)) / sr
    left = 0.3 * np.sin(2 * np.pi * 440 * t) + 0.1 * np.sin(2 * np.pi * 200 * t)
    right = 0.3 * np.sin(2 * np.pi * 441 * t) + 0.1 * np.sin(2 * np.pi * 201 * t)
    return np.column_stack((left, right))

def test_knobs():
    print("\n### 9 Mastering Knobs ###")
    proc = AudioProcessor()
    audio = make_audio()
    
    knobs = [
        ('apply_air', 50), ('apply_body', -30), ('apply_focus', 40),
        ('apply_push', 30), ('apply_width', 150), ('apply_volume', -3),
        ('apply_transients', 50), ('apply_analog', 40), ('apply_bass_punch', 50),
    ]
    
    for method_name, value in knobs:
        try:
            method = getattr(proc, method_name)
            if method_name == 'apply_volume':
                result = method(audio.copy(), value)
            elif method_name == 'apply_width':
                result = method(audio.copy(), value)
            else:
                result = method(audio.copy(), value)
            check(f"{method_name}({value})", 
                  result.shape == audio.shape and not np.any(np.isnan(result)),
                  f"shape={result.shape}")
        except Exception as e:
            check(f"{method_name}({value})", False, str(e))

def test_denoiser():
    print("\n### Denoiser ###")
    proc = AudioProcessor()
    audio = make_audio()
    
    # Analyze
    try:
        proc.analyze_problematic_frequencies(audio)
        check("analyze_problematic_frequencies", True)
    except Exception as e:
        check("analyze_problematic_frequencies", False, str(e))
    
    # Apply denoiser
    try:
        state = DenoiserState()
        state.boomy_active = True
        state.boxy_active = True  
        state.muddy_active = True
        state.honky_active = True
        state.harsh_active = True
        state.sizzle_active = True
        
        result, levels = proc.apply_denoiser(audio.copy(), 50, state)
        check("apply_denoiser shape", result.shape == audio.shape)
        check("apply_denoiser no NaN", not np.any(np.isnan(result)))
        check("denoiser returns state", hasattr(levels, 'boomy_level'))
    except Exception as e:
        check("apply_denoiser", False, str(e))

def test_reverb():
    print("\n### Reverb Types ###")
    proc = AudioProcessor()
    audio = make_audio()
    
    for rtype in ['Plate', 'Hall', 'Room', 'Chamber']:
        try:
            result = proc.apply_reverb(audio.copy(), rtype, 30)
            check(f"reverb {rtype}", result.shape == audio.shape and not np.any(np.isnan(result)))
        except Exception as e:
            check(f"reverb {rtype}", False, str(e))

def test_eq():
    print("\n### Graphical EQ ###")
    proc = AudioProcessor()
    audio = make_audio()
    
    bands = {60: 2.0, 125: -1.5, 250: 0.5, 500: -0.5, 1000: 1.0, 
             2000: -1.0, 4000: 2.0, 8000: -2.0, 16000: 1.5}
    try:
        result = proc.apply_eq(audio.copy(), bands)
        check("EQ with all bands", result.shape == audio.shape and not np.any(np.isnan(result)))
    except Exception as e:
        check("EQ with all bands", False, str(e))
    
    # Zero bands
    bands_zero = {f: 0 for f in bands}
    try:
        result = proc.apply_eq(audio.copy(), bands_zero)
        diff = np.max(np.abs(result - audio))
        check("EQ zero = passthrough", diff < 0.01, f"diff={diff:.6f}")
    except Exception as e:
        check("EQ zero = passthrough", False, str(e))

def test_presets():
    print("\n### 19 Presets ###")
    pm = PresetManager()
    names = pm.get_preset_names()
    check(f"Preset count >= 19", len(names) >= 19, f"got {len(names)}")
    
    required = ['Default', 'Suno Fix', 'Udio Fix', 'Pop / Modern', 'EDM / Electronic',
                'Hip-Hop / Trap', 'Rock / Alternative', 'Acoustic / Folk',
                'De-Harsh', 'De-Muddy', 'Light Touch', 'Full Mastering']
    
    for name in required:
        preset = pm.get_preset(name)
        check(f"Preset '{name}' exists", preset is not None)
    
    # Check preset has all required keys
    for name in names:
        preset = pm.get_preset(name)
        if preset:
            has_keys = all(k in preset for k in ['air', 'body', 'focus', 'push', 'width', 
                                                    'volume', 'transients', 'analog', 'bass_punch',
                                                    'denoiser_sensitivity', 'eq_settings'])
            check(f"Preset '{name}' has all keys", has_keys)

def test_export():
    print("\n### Export (Streaming) ###")
    proc = AudioProcessor()
    audio = make_audio(dur=5.0)
    
    input_path = '/tmp/test_feat_in.wav'
    sf.write(input_path, audio, 44100, subtype='FLOAT')
    
    settings = {
        'air': 20, 'body': -10, 'focus': 10, 'push': 15,
        'width': 110, 'volume': -1, 'transients': 10, 'analog': 10,
        'bass_punch': 15, 'reverb_amount': 5, 'reverb_type': 'Room',
        'denoiser_sensitivity': 0,
        'eq_bands': {60: 1, 125: 0, 250: -0.5, 500: 0, 1000: 0.5, 2000: 0, 4000: 1, 8000: 0, 16000: -0.5}
    }
    
    for bit_depth, dither in [(16, 'TPDF'), (24, 'TPDF'), (32, 'Off')]:
        output_path = f'/tmp/test_feat_out_{bit_depth}.wav'
        try:
            exporter = StreamingExporter(proc)
            success = exporter.export_streaming(input_path, output_path, settings,
                                                 target_sample_rate=96000, bit_depth=bit_depth,
                                                 dither_type=dither)
            check(f"Export {bit_depth}bit", success)
            
            exported, esr = sf.read(output_path, dtype='float64')
            check(f"Export {bit_depth}bit sample rate", esr == 96000)
            check(f"Export {bit_depth}bit stereo", len(exported.shape) == 2 and exported.shape[1] == 2)
            check(f"Export {bit_depth}bit no NaN", not np.any(np.isnan(exported)))
            os.unlink(output_path)
        except Exception as e:
            check(f"Export {bit_depth}bit", False, str(e))
    
    os.unlink(input_path)

def test_dither():
    print("\n### Dither Types ###")
    proc = AudioProcessor()
    audio = make_audio()
    
    for dtype in ['Off', 'TPDF', 'POWr1', 'POWr2', 'POWr3']:
        try:
            if dtype == 'Off':
                check(f"Dither {dtype}", True)
                continue
            result = proc._apply_dither(audio.copy(), 16, dtype)
            check(f"Dither {dtype}", result.shape == audio.shape and not np.any(np.isnan(result)))
        except Exception as e:
            check(f"Dither {dtype}", False, str(e))

def test_process_chunk_lightweight():
    print("\n### process_chunk_lightweight ###")
    proc = AudioProcessor()
    audio = make_audio()
    
    settings = {
        'air': 30, 'body': -20, 'focus': 15, 'push': 25,
        'width': 120, 'volume': -2, 'transients': 20, 'analog': 15,
        'bass_punch': 30, 'reverb_amount': 10, 'reverb_type': 'Plate',
        'eq_bands': {60: 1, 125: -1, 250: 0.5, 500: 0, 1000: -0.5, 2000: 1, 4000: -1, 8000: 0.5, 16000: -0.5}
    }
    
    try:
        result = proc.process_chunk_lightweight(audio.copy(), settings)
        check("process_chunk_lightweight", result.shape == audio.shape and not np.any(np.isnan(result)))
    except Exception as e:
        check("process_chunk_lightweight", False, str(e))

def test_mono():
    print("\n### Mono Processing ###")
    proc = AudioProcessor()
    audio = make_audio()
    
    # Mono audio (1D)
    mono = audio[:, 0].copy()
    try:
        result = proc.apply_air(mono.copy(), 30)
        check("Mono air", result.shape == mono.shape and not np.any(np.isnan(result)))
    except Exception as e:
        check("Mono air", False, str(e))

def test_oversampling():
    print("\n### Oversampling ###")
    proc = AudioProcessor()
    audio = make_audio()
    
    for factor in [1, 2, 4]:
        try:
            settings = {
                'air': 10, 'body': 0, 'focus': 0, 'push': 0,
                'width': 100, 'volume': 0, 'transients': 0, 'analog': 0,
                'bass_punch': 0, 'reverb_amount': 0, 'reverb_type': 'Plate',
                'denoiser_sensitivity': 0,
                'eq_bands': {60: 0, 125: 0, 250: 0, 500: 0, 1000: 0, 2000: 0, 4000: 0, 8000: 0, 16000: 0},
                'oversampling': factor
            }
            result = proc.process_audio(audio.copy(), settings)
            check(f"Oversampling {factor}x", result.shape == audio.shape and not np.any(np.isnan(result)))
        except Exception as e:
            check(f"Oversampling {factor}x", False, str(e))

def main():
    print("=" * 60)
    print("AI Music Doctor v4.0 - Full Feature Test")
    print("=" * 60)
    
    test_knobs()
    test_denoiser()
    test_reverb()
    test_eq()
    test_presets()
    test_export()
    test_dither()
    test_process_chunk_lightweight()
    test_mono()
    test_oversampling()
    
    print("\n" + "=" * 60)
    print(f"TOTAL: {PASS} passed, {FAIL} failed out of {PASS + FAIL}")
    if FAIL == 0:
        print("ALL TESTS PASSED! ✓")
    else:
        print(f"{FAIL} TESTS FAILED ❌")
    return 1 if FAIL else 0

if __name__ == '__main__':
    sys.exit(main())

</file>

</uploaded_files>
