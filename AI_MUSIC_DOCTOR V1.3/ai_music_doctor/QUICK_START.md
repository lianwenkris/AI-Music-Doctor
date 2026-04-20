# AI Music Doctor - Quick Start Guide

## For End Users

### Installation
1. Download `AI_Music_Doctor_v1.0.0_Setup.exe`
2. Double-click to install
3. Launch from Start Menu or desktop shortcut

### First Use
1. Click **"Add Files"** → Select your WAV files
2. Choose preset from dropdown:
   - **Suno** - For Suno AI music (most common issues)
   - **Udio** - For Udio music
   - **Tunee** - For Tunee AI music
3. Click **"Browse"** to choose output folder
4. Click **"PROCESS"** button
5. Wait for progress bar to complete
6. Find cleaned files in output folder (with `_cleaned` suffix)

### Quick Tips
- Start with service-specific presets (Suno/Udio/Tunee)
- Use TPDF dithering for 16-bit output (default)
- Enable "Mono Mode" to check for phase issues
- Click "Help" for detailed manual

---

## For Developers

### Quick Setup (5 minutes)
```bash
cd /home/ubuntu/ai_music_doctor

# Install dependencies
pip install -r requirements.txt

# Run tests
python test_audio_processor.py

# Launch application
python run_app.py
```

### Quick Build (Windows Executable)
```bash
# Generate manual
python src/generate_manual.py

# Build executable
python installer/build_installer.py

# Find executable in dist/ folder
```

### Project Structure
```
src/
  ├── audio_processor.py  # Core processing engine
  ├── presets.py          # Service-specific presets
  ├── gui.py              # User interface
  └── main.py             # Entry point
```

### Key Files to Modify
- **Add presets**: Edit `src/presets.py`
- **Change UI**: Edit `src/gui.py`
- **Modify processing**: Edit `src/audio_processor.py`

---

## Testing

### Run All Tests
```bash
python test_audio_processor.py
```

### Manual Testing
1. Launch app: `python run_app.py`
2. Add sample WAV file
3. Select a preset
4. Process and verify output

---

## Building & Distribution

### Windows Installer (Recommended)
1. Build executable: `python installer/build_installer.py`
2. Install Inno Setup: https://jrsoftware.org/isinfo.php
3. Open `installer/ai_music_doctor_installer.iss` in Inno Setup
4. Click "Compile"
5. Find installer in `dist/` folder

### Portable Version (Simpler)
1. Build: `python installer/build_installer.py`
2. Zip the `dist/` folder contents
3. Distribute ZIP file

---

## Common Issues

### Installation Issues
**Problem:** Dependencies won't install  
**Solution:** Use Python 3.9-3.11, upgrade pip: `pip install --upgrade pip`

**Problem:** PyQt5 installation fails  
**Solution:** Install Visual C++ Redistributable from Microsoft

### Runtime Issues
**Problem:** "Module not found" errors  
**Solution:** Ensure all dependencies installed: `pip install -r requirements.txt`

**Problem:** GUI doesn't appear  
**Solution:** Check if PyQt5 installed: `python -c "import PyQt5"`

### Processing Issues
**Problem:** "Invalid audio format"  
**Solution:** Only WAV files supported (16/24/32-bit, 44.1/48/96 kHz)

**Problem:** Output sounds worse  
**Solution:** Try different preset or reduce processing intensities

---

## Support

- **Email:** support@denoisethefuture.com
- **Documentation:** See `docs/AI_Music_Doctor_Manual.pdf`
- **Detailed Build Guide:** See `BUILD_INSTRUCTIONS.md`

---

## Quick Reference

### Presets
- **Suno** - Metallic sheen, muffled bass → Use for Suno tracks
- **Udio** - Vocal blending, drum issues → Use for Udio tracks
- **Tunee** - General AI artifacts → Use for Tunee tracks
- **De-Harsh** - Robotic vocals → Use when vocals sound harsh
- **De-Ess** - Sibilance → Use when "S" sounds are too strong
- **Restore Highs** - Dull sound → Use when track lacks brightness
- **Fix Phase** - Hollow sound → Use for phase cancellation
- **Heavy Cleanup** - Severe artifacts → Use as last resort

### Controls
- **In Gain**: Boost quiet input (-12 to +12 dB)
- **Out Gain**: Adjust output level (-12 to +12 dB)
- **Hiss & Noise**: Remove background noise (30-50% typical)
- **Artifact Cleanup**: Remove AI glitches (40-50% typical)
- **Freq Suppression**: Target problem frequencies (varies by preset)

### Dithering
- **Off** - No dithering (not recommended)
- **TPDF** - Standard (recommended for most uses) ⭐
- **POWr1** - Pop/EDM music
- **POWr2** - General music
- **POWr3** - Orchestral/acoustic

---

**Made with ❤️ by Denoise The Future Inc.**

*Get started in 5 minutes!*
