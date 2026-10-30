; Licensed Autodata 3.45 file installer template.
; Requires AUTODATA_STAGED to point to a directory created by prepare_payload.py.
; No keygens, emulators, registry hacks or license bypasses are bundled.
#define SourceDir GetEnv("AUTODATA_STAGED")
#if SourceDir == ""
  #error "AUTODATA_STAGED is not set. Use build.ps1."
#endif
#define OutputDir GetEnv("AUTODATA_OUTPUT_DIR")
#if OutputDir == ""
  #define OutputDir ".\dist"
#endif

[Setup]
AppId=Autodata345LicensedFileInstaller
AppName=Autodata 3.45 (Licensed Files)
AppVersion=3.45
AppPublisher=Local licensed installation
DefaultDirName={autopf}\Autodata 3.45
DefaultGroupName=Autodata 3.45
OutputDir={#OutputDir}
OutputBaseFilename=Autodata_3_45_Licensed_Setup
Compression=lzma2
SolidCompression=yes
DiskSpanning=no
PrivilegesRequired=admin
WizardStyle=modern
UninstallDisplayIcon={app}\ADCDA2\ADBCD.exe
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes
ChangesAssociations=no
ChangesEnvironment=no

[Files]
Source: "{#SourceDir}\ADCDA2\*"; DestDir: "{app}\ADCDA2"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Autodata 3.45"; Filename: "{app}\ADCDA2\ADBCD.exe"; WorkingDir: "{app}\ADCDA2"

[Messages]
BeveledLabel=Requires genuine licensing; activation is not automated.

; Deliberately no [Run], [Registry], [Drivers] or license generation.
