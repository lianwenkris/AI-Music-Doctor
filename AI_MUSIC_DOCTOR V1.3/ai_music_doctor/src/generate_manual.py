<uploaded_files github_repo=mixdoktorz-bit/AI-Music-Doctor>
<file=AI_MUSIC_DOCTOR V1.3/ai_music_doctor/src/generate_manual.py>
#!/usr/bin/env python3
"""
AI Music Doctor - PDF Manual Generator
Generates comprehensive user documentation

Version: 2.0.0
"""

import os
import sys
from pathlib import Path

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.colors import HexColor
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("Warning: reportlab not available. Manual generation disabled.")


def generate_manual(output_path=None):
    """Generate the PDF user manual"""
    
    if not REPORTLAB_AVAILABLE:
        print("Cannot generate manual: reportlab not installed")
        return False
    
    # Determine output path
    if output_path is None:
        script_dir = Path(__file__).parent.parent
        docs_dir = script_dir / 'docs'
        docs_dir.mkdir(exist_ok=True)
        output_path = docs_dir / 'AI_Music_Doctor_Manual.pdf'
    
    output_path = Path(output_path)
    
    # Create document
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Styles
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=HexColor('#00CCCC')
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceBefore=20,
        spaceAfter=10,
        textColor=HexColor('#00AAAA')
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=12,
        spaceBefore=15,
        spaceAfter=8,
        textColor=HexColor('#008888')
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=10,
        leading=14
    )
    
    bullet_style = ParagraphStyle(
        'CustomBullet',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=20,
        spaceAfter=5,
        leading=12
    )
    
    # Build content
    content = []
    
    # Title page
    content.append(Paragraph("AI Music Doctor", title_style))
    content.append(Paragraph("User Manual v2.0.0", styles['Heading2']))
    content.append(Spacer(1, 0.5*inch))
    content.append(Paragraph("Real-Time AI Music Cleanup & Enhancement", body_style))
    content.append(Spacer(1, 0.3*inch))
    content.append(Paragraph("Denoise The Future Inc.", body_style))
    content.append(Paragraph("Copyright © 2026 All Rights Reserved", body_style))
    content.append(PageBreak())
    
    # What's New
    content.append(Paragraph("What's New in Version 2.0", heading_style))
    
    content.append(Paragraph("TRUE Real-Time Audio Monitoring", subheading_style))
    content.append(Paragraph(
        "AI Music Doctor now features true real-time audio monitoring! When you press Play, "
        "the audio is processed live through our streaming engine. Adjust any knob during "
        "playback and hear the change IMMEDIATELY - no need to click 'Process' first.",
        body_style
    ))
    
    content.append(Paragraph("Automatic Audio Analysis", subheading_style))
    content.append(Paragraph(
        "When you load an audio file, it's automatically analyzed for common AI music issues. "
        "The analyzer detects noise levels, artifacts, frequency imbalances, and even attempts "
        "to identify which AI service (Suno, Udio, or Tunee) generated the audio. Based on the "
        "analysis, optimal settings are suggested as a starting point.",
        body_style
    ))
    
    content.append(Paragraph("A/B Comparison", subheading_style))
    content.append(Paragraph(
        "Toggle between 'Original (Dry)' and 'Processed (Wet)' during playback to instantly "
        "compare before and after. This helps you fine-tune settings without over-processing.",
        body_style
    ))
    
    content.append(Paragraph("Seek and Loop Controls", subheading_style))
    content.append(Paragraph(
        "Use the seek slider to jump to any position in the audio. Enable loop mode for "
        "continuous playback of a section while fine-tuning parameters.",
        body_style
    ))
    
    content.append(PageBreak())
    
    # Workflow
    content.append(Paragraph("Recommended Workflow", heading_style))
    
    workflow_steps = [
        "1. Load your AI-generated audio file (WAV format recommended)",
        "2. Wait for automatic analysis to complete (usually 1-2 seconds)",
        "3. Review the analysis results - check detected issues and suggestions",
        "4. Click 'Apply Suggested Settings' or manually select a preset",
        "5. Press Play to hear the processed audio in real-time",
        "6. Adjust any knob while listening - changes are instant",
        "7. Use A/B toggle to compare Original vs Processed",
        "8. Fine-tune all parameters until satisfied",
        "9. Click Export to save the processed audio"
    ]
    
    for step in workflow_steps:
        content.append(Paragraph(step, bullet_style))
    
    content.append(PageBreak())
    
    # Controls
    content.append(Paragraph("Controls Guide", heading_style))
    
    content.append(Paragraph("Input/Output Gain", subheading_style))
    content.append(Paragraph(
        "• In Gain: Boosts the signal before processing. Use when audio is too quiet. "
        "Range: -12 to +12 dB<br/>"
        "• Out Gain: Adjusts final volume after processing. Use to prevent clipping. "
        "Range: -12 to +12 dB",
        body_style
    ))
    
    content.append(Paragraph("Hiss & Noise Removal", subheading_style))
    content.append(Paragraph(
        "FFT-based spectral denoising. Higher values remove more noise but may affect "
        "audio quality. Recommended: 25-50% for typical AI music. Range: 0-100%",
        body_style
    ))
    
    content.append(Paragraph("Artifact Cleanup", subheading_style))
    content.append(Paragraph(
        "Targets AI-specific artifacts like metallic sounds, robotic qualities, and "
        "unnatural tones. Higher values are more aggressive. Recommended: 30-55%. Range: 0-100%",
        body_style
    ))
    
    content.append(Paragraph("Frequency Suppression", subheading_style))
    content.append(Paragraph(
        "Reduces energy in a specific frequency range (defined by the current preset). "
        "Useful for targeting specific problem areas. Range: 0-100%",
        body_style
    ))
    
    content.append(PageBreak())
    
    # Presets
    content.append(Paragraph("Presets Guide", heading_style))
    
    content.append(Paragraph("AI Service Presets", subheading_style))
    
    content.append(Paragraph(
        "<b>Suno:</b> Optimized for Suno AI outputs. Targets metallic sheen (6-12kHz), "
        "unmuffles bass frequencies, and addresses phase issues common in Suno generations. "
        "Uses Hybrid processing mode with aggressive high-frequency suppression.",
        body_style
    ))
    
    content.append(Paragraph(
        "<b>Udio:</b> Optimized for Udio outputs. Addresses vocal-instrumental blending issues, "
        "drum artifacts, and 'mushy' mid frequencies. Uses Spectral processing with "
        "focus on mid-high clarity.",
        body_style
    ))
    
    content.append(Paragraph(
        "<b>Tunee:</b> Optimized for Tunee AI outputs. Targets robotic/synthetic vocal quality, "
        "pronunciation artifacts, and excessive digital harshness. Uses Hybrid processing "
        "with presence reduction.",
        body_style
    ))
    
    content.append(Paragraph("Problem-Specific Presets", subheading_style))
    
    problem_presets = [
        "De-Harsh: Removes harsh artifacts in 2-5 kHz range",
        "De-Ess: Reduces sibilance in 5-8 kHz range",
        "De-Muddy: Clears muddy low-mids (200-500 Hz)",
        "De-Metallic: Removes metallic sheen (6-12 kHz)",
        "Restore Highs: Enhances frequencies above 12 kHz",
        "Fix Phase: Addresses phase cancellation issues",
        "Vocal Clarity: Enhances vocal presence",
        "Drum Punch: Adds punch to drums",
        "Bass Restoration: Restores weak low end"
    ]
    
    for preset in problem_presets:
        content.append(Paragraph(f"• {preset}", bullet_style))
    
    content.append(Paragraph("Intensity Presets", subheading_style))
    
    intensity_presets = [
        "Light Touch: Subtle cleanup for good quality audio",
        "Moderate Cleanup: Balanced cleanup for typical AI music",
        "Heavy Cleanup: Aggressive processing for problematic audio",
        "Maximum Restoration: Most aggressive - may affect transients"
    ]
    
    for preset in intensity_presets:
        content.append(Paragraph(f"• {preset}", bullet_style))
    
    content.append(PageBreak())
    
    # Processing Modes
    content.append(Paragraph("Processing Modes", heading_style))
    
    content.append(Paragraph("Spectral (FFT)", subheading_style))
    content.append(Paragraph(
        "Processes audio in the frequency domain using Fast Fourier Transform. Best for "
        "broadband noise and general artifacts. May slightly smear transients.",
        body_style
    ))
    
    content.append(Paragraph("Time-Domain", subheading_style))
    content.append(Paragraph(
        "Processes audio in the time domain using adaptive filtering. Better for "
        "preserving transients and dynamics. May be less effective on broadband noise.",
        body_style
    ))
    
    content.append(Paragraph("Hybrid (Recommended)", subheading_style))
    content.append(Paragraph(
        "Combines spectral processing for noise reduction with time-domain processing "
        "for artifact removal. Provides the best balance for most AI-generated music.",
        body_style
    ))
    
    content.append(PageBreak())
    
    # Technical Info
    content.append(Paragraph("Technical Information", heading_style))
    
    content.append(Paragraph("Supported Formats", subheading_style))
    content.append(Paragraph(
        "• Input: WAV (recommended), FLAC, MP3<br/>"
        "• Output: WAV (16-bit, 24-bit, or 32-bit float)<br/>"
        "• Sample rates: All standard rates supported (44.1kHz, 48kHz, etc.)",
        body_style
    ))
    
    content.append(Paragraph("Dithering Options", subheading_style))
    content.append(Paragraph(
        "• Off: No dithering (for 32-bit float output)<br/>"
        "• TPDF: Triangular Probability Density Function - standard dithering<br/>"
        "• POWr1: Psychoacoustic noise shaping - subtle<br/>"
        "• POWr2: More aggressive noise shaping<br/>"
        "• POWr3: Maximum noise shaping (may color bright audio)",
        body_style
    ))
    
    content.append(Paragraph("Real-Time Engine", subheading_style))
    content.append(Paragraph(
        "The real-time engine uses a 512-sample buffer size for low latency (~12ms at 44.1kHz). "
        "Parameters are updated using thread-safe mechanisms to ensure smooth transitions "
        "without clicks or pops when adjusting controls during playback.",
        body_style
    ))
    
    # Build PDF
    doc.build(content)
    print(f"Manual generated: {output_path}")
    return True


if __name__ == '__main__':
    output_path = sys.argv[1] if len(sys.argv) > 1 else None
    generate_manual(output_path)

</file>

</uploaded_files>
