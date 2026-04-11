# Changelog

All notable changes to AI Music Doctor are documented in this file.

## [4.0.1] - 2026-04-03

### CRITICAL FIX: Memory Leak During Export

#### Fixed - MEMORY EXHAUSTION DURING EXPORT
Resolved critical bug where export would consume 90%+ RAM and freeze the system:
- **Root Cause**: Entire audio file was loaded into memory and processed at once
- **Solution**: Implemented streaming export (like Ableton's "Freeze")

#### Added - StreamingExporter Class
New memory-efficient export system:
- **Chunk-based Processing**: Reads audio in 2-second chunks
- **Direct-to-Disk Writing**: Processed chunks written immediately
- **Automatic Memory Cleanup**: `gc.collect()` called after each chunk
- **Peak Tracking**: Two-pass system for accurate normalization

#### Technical Details
- Memory usage now stays stable regardless of file size
- Test: 3-minute file export uses only ~18MB additional RAM
- Previously would use 2-5GB for the same file
- Overlap handling for seamless filter processing between chunks

#### Changed - ProcessingThread
- Now uses StreamingExporter instead of in-memory processing
- Progress callback shows real-time chunk processing progress
- Cancellation support with proper temp file cleanup

---

## [4.0.0] - 2026-04-01

### MAJOR RELEASE: COMPLETE REBUILD

#### Changed - MASTERING KNOB SYSTEM
All knobs now work correctly with ±3dB maximum gentle processing:
- **Air** - High frequency enhancement (8-16kHz shelf), adds sparkle and openness
- **Body** - Low-mid warmth (100-300Hz), adds fullness
- **Focus** - Mid presence/clarity (1-4kHz), brings elements forward
- **Push** - Gentle saturation/compression for energy and glue
- **Width** - Stereo width using M/S processing (safe expansion, no phase issues)
- **Volume** - Output level (MUST BE LAST IN CHAIN)
- **Transients** - Transient shaping (attack/sustain control)
- **Analog** - Analog-style even-harmonic saturation/warmth
- **Bass Punch** - Low-end punch enhancement (60-120Hz)

#### Added - PSYCHOACOUSTIC DENOISER
New feature replacing old frequency suppressor:
- Based on Fletcher-Munson curves and Bark Scale critical bands
- One main "SENSITIVITY" knob controlling detection (0-100%)
- **6 Glowing Orbit Buttons** around the knob (clickable on/off toggles):
  - Boomy (100-250Hz) - Excessive low resonance
  - Boxy (150-250Hz) - Hollow/resonant sound
  - Muddy (200-500Hz) - Lack of clarity
  - Honky (500Hz-1.5kHz) - Nasal, resonant midrange
  - Harsh (2-6kHz) - Piercing high-mids, listener fatigue
  - Sizzle (8-12kHz) - Excessive high-frequency energy
- Each orbit button glows based on detected problem level
- Zero-latency processing
- Dynamically minimizes problematic frequencies
- Restores frequencies that were masked by problems

#### Fixed - EQ
- Removed the sweeping sound bug completely
- Implemented proper biquad filter design with coefficient smoothing
- Maximum boost/cut: ±2.4dB (was ±2.0dB)
- Surgical, clean adjustments
- NO zipper noise or artifacts when adjusting in real-time

#### Fixed - BYPASS
- Bypass button now works properly
- When bypassed, audio passes through completely unprocessed

#### Changed - SIGNAL CHAIN
New optimized signal chain order:
```
Input → Denoiser → EQ → Air/Body/Focus/Push/Transients/Analog/Bass Punch → Width → Volume (OUTPUT)
```

#### Changed - PRESETS
All 19 presets recalibrated for new knob system:
- AI Service: Suno, Udio, Tunee (optimized for each platform)
- Genre: Pop/Modern, EDM/Electronic, Hip-Hop/Trap, Rock/Alternative, Acoustic/Folk, Classical/Orchestral
- Problem-Solving: De-Harsh, De-Muddy, De-Thin, Vocal Clarity, Bass Restoration, Open Up Highs
- Intensity: Light Touch, Moderate Polish, Full Mastering

#### Removed
- Hiss removal feature (was not working properly)
- Artifact removal feature (was not working properly)
- VU meter (removed from UI)

#### Technical Improvements
- SmoothedFilter class for artifact-free real-time EQ
- DenoiserState dataclass for tracking detection levels
- Proper M/S encoding/decoding for Width control
- Transient detection with envelope followers
- Even-harmonic saturation for Analog warmth
- Multi-band transient shaping for Bass Punch

---

## [3.0.0] - 2026-04-01

### MAJOR RELEASE: GENTLE PROCESSING & NEW GUI

#### Changed - GENTLE PROCESSING PHILOSOPHY
- Maximum ±2dB EQ per band
- Maximum 6dB noise reduction even at 100%
- Maximum 30% wet artifact removal

#### Added - NEW HARDWARE-STYLE GUI
- Orange/copper aesthetic (T-RackS One style)
- Hardware-style rotary knobs
- VU meter display
- Spectrum analyzer

#### Added - WORKING GRAPHICAL EQ
- 9-band interactive EQ
- Draggable points
- Visual curve display

#### Added - UNDO/REDO FUNCTIONALITY
- 50-level state history
- Thread-safe UndoRedoManager

#### Added - OVERSAMPLING
- 2x, 4x, 8x options
- Anti-aliasing filters

---

## [2.0.0] - 2026-03-15

### MAJOR RELEASE: REAL-TIME MONITORING

#### Added
- True real-time audio monitoring
- Automatic audio analysis
- A/B comparison
- Seek & loop controls
- Live spectrum analyzer
- 17 refined presets

---

## [1.1.0] - 2026-03-01

#### Fixed
- Silent WAV file bug
- Audio playback issues

#### Added
- Multiple processing modes
- New presets

---

## [1.0.0] - 2026-02-15

### Initial Release
- Basic audio processing
- Noise reduction
- Artifact cleanup
- Simple GUI
