#define SourceRoot GetEnv("AUTODATA_SOURCE")
#define DestinationRoot GetEnv("AUTODATA_OUTPUT")
#if SourceRoot == ""
  #error "AUTODATA_SOURCE must point to a reviewed and validated ADCDA2 directory"
#endif
#if DestinationRoot == ""
  #error "AUTODATA_OUTPUT must point to a build output directory"
#endif

[Setup]
AppId={{D70915E4-4D6E-48AA-A5F2-DA345B97276E}
AppName=Autodata 3.45
AppVersion=3.45
DefaultDirName={sd}\ADCDA2
DefaultGroupName=Autodata 3.45
OutputDir={#DestinationRoot}
OutputBaseFilename=Autodata_3_45_OneClick_Setup
Compression=lzma2
SolidCompression=yes
DiskSpanning=no
PrivilegesRequired=admin
DisableProgramGroupPage=yes
WizardStyle=modern
UninstallDisplayIcon={app}\ADBCD.exe
CloseApplications=yes

[Files]
Source: "{#SourceRoot}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Tasks]
Name: desktopicon; Description: "Create desktop shortcut"; Flags: unchecked

[Icons]
Name: "{autoprograms}\Autodata 3.45"; Filename: "{app}\ADBCD.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Autodata 3.45"; Filename: "{app}\ADBCD.exe"; WorkingDir: "{app}"; Tasks: desktopicon
