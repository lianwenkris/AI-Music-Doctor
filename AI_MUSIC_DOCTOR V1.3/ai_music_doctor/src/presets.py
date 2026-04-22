<uploaded_files github_repo=mixdoktorz-bit/AI-Music-Doctor>
<file=AI_MUSIC_DOCTOR V1.3/ai_music_doctor/src/presets.py>
"""
AI Music Doctor - Professional Mastering Presets
Version: 4.1.0

Presets calibrated by top mixing/mastering engineer standards.
All knobs use ±3dB max gentle processing for clean, pristine sound.
REVERB: Default 0% in ALL presets (user's personal choice)

Knobs: Air, Body, Focus, Push, Width, Volume, Transients, Analog, Bass Punch, REVERB
Denoiser: Sensitivity + 6 frequency bands (Boomy, Boxy, Muddy, Honky, Harsh, Sizzle)
EQ: ±2.4dB max per band
"""


class PresetManager:
    """Manages professional mastering presets"""
    
    MAX_KNOB_RANGE = 100  # Knobs go from -100 to +100 or 0 to 100
    MAX_EQ_GAIN = 2.4     # ±2.4dB max for EQ
    
    def __init__(self):
        self.presets = self._initialize_presets()
    
    def _initialize_presets(self) -> dict:
        """Initialize all presets with mastering-grade settings"""
        
        return {
            # ============================================
            # DEFAULT
            # ============================================
            "Default": {
                "description": "Neutral starting point - no processing",
                "air": 0, "body": 0, "focus": 0, "push": 0,
                "width": 100, "volume": 0,
                "transients": 0, "analog": 0, "bass_punch": 0,
                "reverb": 0, "reverb_type": "Plate",
                "denoiser_sensitivity": 0,
                "denoiser_boomy": True, "denoiser_boxy": True,
                "denoiser_muddy": True, "denoiser_honky": True,
                "denoiser_harsh": True, "denoiser_sizzle": True,
                "processing_mode": "Hybrid",
                "eq_settings": {}
            },
            
            # ============================================
            # AI SERVICE PRESETS
            # Calibrated for specific AI music generation services
            # ============================================
            
            "Suno": {
                "description": "Optimized for Suno AI - reduces metallic sheen, adds warmth",
                "air": 15,           # Subtle high-end sparkle
                "body": 25,          # Add warmth to counter thinness
                "focus": 10,         # Gentle presence boost
                "push": 15,          # Light glue
                "width": 105,        # Slight stereo enhancement
                "volume": -0.5,      # Slight output trim
                "transients": 10,    # Slight attack emphasis
                "analog": 20,        # Warm saturation
                "bass_punch": 15,    # Low-end impact
                "reverb": 0, "reverb_type": "Plate",
                "denoiser_sensitivity": 35,
                "denoiser_boomy": False, "denoiser_boxy": True,
                "denoiser_muddy": True, "denoiser_honky": True,
                "denoiser_harsh": True, "denoiser_sizzle": True,
                "processing_mode": "Hybrid",
                "eq_settings": {
                    60: 1.0, 125: 0.5,      # Bass restoration
                    250: -1.5, 500: -0.5,    # Reduce mud/box
                    2000: 0.5, 4000: 1.0,    # Presence
                    8000: -1.0, 16000: 0.5   # Tame metallic, add air
                }
            },
            
            "Udio": {
                "description": "Optimized for Udio - improves vocal clarity and depth",
                "air": 20,           # Open up the top
                "body": 15,          # Subtle warmth
                "focus": 25,         # Vocal clarity
                "push": 10,          # Light compression
                "width": 110,        # Enhance stereo field
                "volume": 0,
                "transients": 5,     # Preserve dynamics
                "analog": 10,        # Subtle warmth
                "bass_punch": 10,    # Tight low end
                "reverb": 0, "reverb_type": "Plate",
                "denoiser_sensitivity": 25,
                "denoiser_boomy": True, "denoiser_boxy": True,
                "denoiser_muddy": True, "denoiser_honky": True,
                "denoiser_harsh": True, "denoiser_sizzle": False,
                "processing_mode": "Spectral (FFT)",
                "eq_settings": {
                    60: 0.5, 125: -0.5,      # Tighten bass
                    250: -1.0,                # Reduce mud
                    2000: 1.0, 4000: 1.5,    # Vocal presence
                    8000: 0.5, 16000: 1.0    # Detail and air
                }
            },
            
            "Tunee": {
                "description": "Optimized for Tunee AI - reduces robotic quality, adds life",
                "air": 10,
                "body": 20,          # Add organic warmth
                "focus": 15,
                "push": 20,          # More glue for cohesion
                "width": 100,        # Keep natural
                "volume": -0.5,
                "transients": -15,   # Soften harsh transients
                "analog": 30,        # More analog warmth
                "bass_punch": 20,
                "reverb": 0, "reverb_type": "Plate",
                "denoiser_sensitivity": 40,
                "denoiser_boomy": True, "denoiser_boxy": True,
                "denoiser_muddy": True, "denoiser_honky": True,
                "denoiser_harsh": True, "denoiser_sizzle": True,
                "processing_mode": "Hybrid",
                "eq_settings": {
                    60: 0.5, 125: 1.0,       # Bass presence
                    500: -1.0,                # Reduce boxiness
                    2000: -0.5, 4000: -1.5,  # Reduce robotic mid
                    8000: -0.5, 16000: 0.5   # Tame harsh, add air
                }
            },
            
            # ============================================
            # GENRE-SPECIFIC PRESETS
            # ============================================
            
            "Pop/Modern": {
                "description": "Bright, punchy, wide - modern pop sound",
                "air": 30,
                "body": 10,
                "focus": 20,
                "push": 25,
                "width": 115,
                "volume": 0,
                "transients": 20,
                "analog": 15,
                "bass_punch": 25,
                "reverb": 0, "reverb_type": "Plate",
                "denoiser_sensitivity": 20,
                "denoiser_boomy": True, "denoiser_boxy": True,
                "denoiser_muddy": True, "denoiser_honky": True,
                "denoiser_harsh": True, "denoiser_sizzle": False,
                "processing_mode": "Hybrid",
                "eq_settings": {
                    60: 1.5, 125: 0.5,
                    250: -1.0,
                    2000: 1.0, 4000: 1.5,
                    8000: 1.0, 16000: 1.5
                }
            },
            
            "EDM/Electronic": {
                "description": "Tight bass, crystal highs, wide stereo",
                "air": 25,
                "body": -10,          # Tight, not boomy
                "focus": 15,
                "push": 30,           # More energy
                "width": 120,         # Wide stereo
                "volume": 0,
                "transients": 30,     # Punchy
                "analog": 10,
                "bass_punch": 35,     # Maximum impact
                "reverb": 0, "reverb_type": "Room",
                "denoiser_sensitivity": 15,
                "denoiser_boomy": True, "denoiser_boxy": True,
                "denoiser_muddy": True, "denoiser_honky": False,
                "denoiser_harsh": False, "denoiser_sizzle": False,
                "processing_mode": "Hybrid",
                "eq_settings": {
                    60: 2.0,
                    250: -1.5, 500: -1.0,
                    4000: 1.0,
                    8000: 1.5, 16000: 2.0
                }
            },
            
            "Hip-Hop/Trap": {
                "description": "Deep bass, crisp highs, punchy drums",
                "air": 20,
                "body": 25,
                "focus": 15,
                "push": 25,
                "width": 105,
                "volume": 0,
                "transients": 25,
                "analog": 20,
                "bass_punch": 40,
                "reverb": 0, "reverb_type": "Room",
                "denoiser_sensitivity": 20,
                "denoiser_boomy": False, "denoiser_boxy": True,
                "denoiser_muddy": True, "denoiser_honky": True,
                "denoiser_harsh": True, "denoiser_sizzle": False,
                "processing_mode": "Hybrid",
                "eq_settings": {
                    60: 2.0, 125: 1.5,
                    250: -0.5,
                    2000: 0.5, 4000: 1.0,
                    8000: 1.0
                }
            },
            
            "Rock/Alternative": {
                "description": "Warm, full, punchy rock sound",
                "air": 15,
                "body": 30,
                "focus": 25,
                "push": 30,
                "width": 110,
                "volume": 0,
                "transients": 15,
                "analog": 35,
                "bass_punch": 30,
                "reverb": 0, "reverb_type": "Chamber",
                "denoiser_sensitivity": 15,
                "denoiser_boomy": True, "denoiser_boxy": True,
                "denoiser_muddy": True, "denoiser_honky": True,
                "denoiser_harsh": True, "denoiser_sizzle": True,
                "processing_mode": "Time-Domain",
                "eq_settings": {
                    60: 1.0, 125: 1.0,
                    500: 0.5,
                    2000: 1.5, 4000: 0.5,
                    8000: 0.5
                }
            },
            
            "Acoustic/Folk": {
                "description": "Natural, warm, intimate acoustic sound",
                "air": 20,
                "body": 20,
                "focus": 10,
                "push": 10,
                "width": 100,
                "volume": 0,
                "transients": 5,
                "analog": 25,
                "bass_punch": 10,
                "reverb": 0, "reverb_type": "Chamber",
                "denoiser_sensitivity": 10,
                "denoiser_boomy": True, "denoiser_boxy": True,
                "denoiser_muddy": True, "denoiser_honky": True,
                "denoiser_harsh": True, "denoiser_sizzle": True,
                "processing_mode": "Time-Domain",
                "eq_settings": {
                    125: 0.5,
                    250: -0.5,
                    2000: 0.5, 4000: 1.0,
                    8000: 0.5, 16000: 1.0
                }
            },
            
            "Classical/Orchestral": {
                "description": "Transparent, natural, wide dynamic range",
                "air": 15,
                "body": 15,
                "focus": 5,
                "push": 5,           # Minimal compression
                "width": 110,
                "volume": 0,
                "transients": 0,     # Preserve natural dynamics
                "analog": 10,
                "bass_punch": 5,
                "reverb": 0, "reverb_type": "Hall",
                "denoiser_sensitivity": 5,
                "denoiser_boomy": True, "denoiser_boxy": True,
                "denoiser_muddy": True, "denoiser_honky": True,
                "denoiser_harsh": True, "denoiser_sizzle": True,
                "processing_mode": "Spectral (FFT)",
                "eq_settings": {
                    60: 0.5,
                    250: -0.5,
                    2000: 0.5,
                    8000: 0.5, 16000: 1.0
                }
            },
            
            # ============================================
            # PROBLEM-SOLVING PRESETS
            # ============================================
            
            "De-Harsh": {
                "description": "Tames harsh, fatiguing high-mids (2-6kHz)",
                "air": 10,
                "body": 10,
                "focus": -20,        # Reduce harsh mids
                "push": 10,
                "width": 100,
                "volume": 0,
                "transients": -10,   # Soften attack
                "analog": 15,
                "bass_punch": 0,
                "reverb": 0, "reverb_type": "Plate",
                "denoiser_sensitivity": 30,
                "denoiser_boomy": False, "denoiser_boxy": False,
                "denoiser_muddy": False, "denoiser_honky": True,
                "denoiser_harsh": True, "denoiser_sizzle": True,
                "processing_mode": "Spectral (FFT)",
                "eq_settings": {
                    2000: -1.5, 4000: -2.0,
                    8000: -1.0
                }
            },
            
            "De-Muddy": {
                "description": "Clears muddy low-mids (200-500Hz)",
                "air": 15,
                "body": -20,         # Reduce mud
                "focus": 15,
                "push": 10,
                "width": 100,
                "volume": 0,
                "transients": 10,
                "analog": 10,
                "bass_punch": 10,
                "reverb": 0, "reverb_type": "Plate",
                "denoiser_sensitivity": 30,
                "denoiser_boomy": True, "denoiser_boxy": True,
                "denoiser_muddy": True, "denoiser_honky": False,
                "denoiser_harsh": False, "denoiser_sizzle": False,
                "processing_mode": "Spectral (FFT)",
                "eq_settings": {
                    250: -2.0, 500: -1.5,
                    2000: 1.0, 4000: 0.5
                }
            },
            
            "De-Thin": {
                "description": "Adds body and warmth to thin recordings",
                "air": 5,
                "body": 35,          # Add warmth
                "focus": 0,
                "push": 20,
                "width": 95,         # Slightly narrower
                "volume": 0,
                "transients": 0,
                "analog": 30,
                "bass_punch": 25,
                "reverb": 0, "reverb_type": "Chamber",
                "denoiser_sensitivity": 10,
                "denoiser_boomy": False, "denoiser_boxy": False,
                "denoiser_muddy": False, "denoiser_honky": True,
                "denoiser_harsh": True, "denoiser_sizzle": True,
                "processing_mode": "Time-Domain",
                "eq_settings": {
                    60: 1.5, 125: 2.0, 250: 1.0,
                    4000: -0.5
                }
            },
            
            "Vocal Clarity": {
                "description": "Enhances vocal presence and intelligibility",
                "air": 15,
                "body": 5,
                "focus": 30,         # Maximum vocal presence
                "push": 15,
                "width": 100,
                "volume": 0,
                "transients": 10,
                "analog": 10,
                "bass_punch": 0,
                "reverb": 0, "reverb_type": "Plate",
                "denoiser_sensitivity": 20,
                "denoiser_boomy": True, "denoiser_boxy": True,
                "denoiser_muddy": True, "denoiser_honky": False,
                "denoiser_harsh": True, "denoiser_sizzle": True,
                "processing_mode": "Hybrid",
                "eq_settings": {
                    250: -1.0,
                    2000: 1.5, 4000: 2.0,
                    8000: 0.5
                }
            },
            
            "Bass Restoration": {
                "description": "Restores lost low-end punch and weight",
                "air": 0,
                "body": 30,
                "focus": 0,
                "push": 15,
                "width": 95,         # Tighter stereo for bass
                "volume": -1,
                "transients": 15,
                "analog": 20,
                "bass_punch": 40,
                "reverb": 0, "reverb_type": "Plate",
                "denoiser_sensitivity": 15,
                "denoiser_boomy": False, "denoiser_boxy": True,
                "denoiser_muddy": True, "denoiser_honky": False,
                "denoiser_harsh": False, "denoiser_sizzle": False,
                "processing_mode": "Time-Domain",
                "eq_settings": {
                    60: 2.0, 125: 1.5,
                    250: -0.5
                }
            },
            
            "Open Up Highs": {
                "description": "Restores dull, lifeless high frequencies",
                "air": 40,           # Maximum air
                "body": 0,
                "focus": 10,
                "push": 10,
                "width": 110,
                "volume": 0,
                "transients": 15,
                "analog": 5,
                "bass_punch": 0,
                "reverb": 0, "reverb_type": "Plate",
                "denoiser_sensitivity": 10,
                "denoiser_boomy": False, "denoiser_boxy": False,
                "denoiser_muddy": False, "denoiser_honky": False,
                "denoiser_harsh": False, "denoiser_sizzle": False,
                "processing_mode": "Spectral (FFT)",
                "eq_settings": {
                    4000: 1.0,
                    8000: 1.5, 16000: 2.0
                }
            },
            
            # ============================================
            # INTENSITY PRESETS
            # ============================================
            
            "Light Touch": {
                "description": "Minimal, nearly transparent processing",
                "air": 5,
                "body": 5,
                "focus": 5,
                "push": 5,
                "width": 100,
                "volume": 0,
                "transients": 0,
                "analog": 5,
                "bass_punch": 5,
                "reverb": 0, "reverb_type": "Plate",
                "denoiser_sensitivity": 10,
                "denoiser_boomy": True, "denoiser_boxy": True,
                "denoiser_muddy": True, "denoiser_honky": True,
                "denoiser_harsh": True, "denoiser_sizzle": True,
                "processing_mode": "Hybrid",
                "eq_settings": {}
            },
            
            "Moderate Polish": {
                "description": "Balanced enhancement for most content",
                "air": 15,
                "body": 15,
                "focus": 15,
                "push": 15,
                "width": 105,
                "volume": 0,
                "transients": 10,
                "analog": 15,
                "bass_punch": 15,
                "reverb": 0, "reverb_type": "Plate",
                "denoiser_sensitivity": 25,
                "denoiser_boomy": True, "denoiser_boxy": True,
                "denoiser_muddy": True, "denoiser_honky": True,
                "denoiser_harsh": True, "denoiser_sizzle": True,
                "processing_mode": "Hybrid",
                "eq_settings": {
                    250: -0.5,
                    2000: 0.5, 4000: 0.5,
                    8000: 0.5
                }
            },
            
            "Full Mastering": {
                "description": "Complete mastering treatment",
                "air": 25,
                "body": 20,
                "focus": 20,
                "push": 25,
                "width": 110,
                "volume": 0,
                "transients": 15,
                "analog": 25,
                "bass_punch": 25,
                "reverb": 0, "reverb_type": "Plate",
                "denoiser_sensitivity": 35,
                "denoiser_boomy": True, "denoiser_boxy": True,
                "denoiser_muddy": True, "denoiser_honky": True,
                "denoiser_harsh": True, "denoiser_sizzle": True,
                "processing_mode": "Hybrid",
                "eq_settings": {
                    60: 0.5,
                    250: -1.0,
                    2000: 1.0, 4000: 1.0,
                    8000: 0.5, 16000: 1.0
                }
            },
        }
    
    def get_preset(self, name: str) -> dict:
        """Get a preset by name"""
        return self.presets.get(name, self.presets["Default"]).copy()
    
    def get_preset_names(self) -> list:
        """Get list of all preset names"""
        return list(self.presets.keys())
    
    def get_preset_description(self, name: str) -> str:
        """Get description for a preset"""
        preset = self.presets.get(name, {})
        return preset.get("description", "")


# Frequency band descriptions for UI tooltips
FREQUENCY_DESCRIPTIONS = {
    "Sub Bass": "20-60 Hz - Felt more than heard, adds weight",
    "Bass": "60-200 Hz - Fundamental bass frequencies",
    "Low Mids": "200-500 Hz - Warmth and body, can get muddy",
    "Mids": "500-2000 Hz - Presence and clarity",
    "Upper Mids": "2000-5000 Hz - Vocal presence, can get harsh",
    "Presence": "5000-8000 Hz - Detail and air",
    "Brilliance": "8000-20000 Hz - Sparkle and shimmer"
}

# Denoiser band descriptions
DENOISER_DESCRIPTIONS = {
    "boomy": "100-250 Hz - Excessive low resonance, overwhelming bass",
    "boxy": "150-250 Hz - Hollow, resonant sound like inside a box",
    "muddy": "200-500 Hz - Lack of clarity, overlapping frequencies",
    "honky": "500 Hz-1.5 kHz - Nasal, resonant midrange",
    "harsh": "2-6 kHz - Piercing high-mids, listener fatigue",
    "sizzle": "8-12 kHz - Excessive high-frequency energy"
}

# Issue to preset mapping for auto-suggestions
ISSUE_PRESET_MAPPING = {
    "muddy": "De-Muddy",
    "harsh": "De-Harsh",
    "thin": "De-Thin",
    "dull": "Open Up Highs",
    "thin_bass": "Bass Restoration",
    "vocal_unclear": "Vocal Clarity",
}

</file>

</uploaded_files>
