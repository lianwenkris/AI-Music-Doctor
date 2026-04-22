<uploaded_files github_repo=mixdoktorz-bit/AI-Music-Doctor>
<file=AI_MUSIC_DOCTOR V1.3/ai_music_doctor/installer/ai_music_doctor_installer.iss>
; AI Music Doctor - Inno Setup Script
; Version 2.0.0

#define MyAppName "AI Music Doctor"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Denoise The Future Inc."
#define MyAppURL "https://denoisethefuture.com"
#define MyAppExeName "AI_Music_Doctor.exe"

[Setup]
AppId={{8A9F3C2E-5B4D-4E6F-A1B2-C3D4E5F67890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=..\LICENSE.txt
OutputDir=..\dist
OutputBaseFilename=AI_Music_Doctor_v{#MyAppVersion}_Setup_x64
SetupIconFile=..\assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\AI_Music_Doctor.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\README.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\AI_Music_Doctor_Manual.pdf"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists(ExpandConstant('{src}\..\docs\AI_Music_Doctor_Manual.pdf'))

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\User Manual"; Filename: "{app}\AI_Music_Doctor_Manual.pdf"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  WelcomePage: TWizardPage;
  WelcomeLabel: TNewStaticText;

procedure InitializeWizard();
var
  WelcomeText: String;
begin
  WelcomeText := 
    'Welcome to AI Music Doctor v2.0!' + #13#10 + #13#10 +
    'NEW IN VERSION 2.0:' + #13#10 + #13#10 +
    '  ★ TRUE REAL-TIME MONITORING' + #13#10 +
    '     Hear changes INSTANTLY as you adjust knobs!' + #13#10 + #13#10 +
    '  ★ AUTOMATIC AUDIO ANALYSIS' + #13#10 +
    '     AI-powered detection of issues and suggestions' + #13#10 + #13#10 +
    '  ★ A/B COMPARISON' + #13#10 +
    '     Toggle Original vs Processed in real-time' + #13#10 + #13#10 +
    '  ★ 17 REFINED PRESETS' + #13#10 +
    '     Service-specific (Suno, Udio, Tunee) and more' + #13#10 + #13#10 +
    '  ★ SEEK & LOOP CONTROLS' + #13#10 +
    '     Navigate and loop for precise editing' + #13#10 + #13#10 +
    'SYSTEM REQUIREMENTS:' + #13#10 +
    '  • Windows 10/11 (64-bit)' + #13#10 +
    '  • 4GB RAM' + #13#10 +
    '  • Audio output device';
  
  WizardForm.WelcomeLabel2.Caption := WelcomeText;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    MsgBox('Thank you for using AI Music Doctor!' + #13#10 + #13#10 +
           'We hope it helped clean up your AI-generated music.' + #13#10 + #13#10 +
           'Visit denoisethefuture.com for updates and support.',
           mbInformation, MB_OK);
  end;
end;

</file>

</uploaded_files>
