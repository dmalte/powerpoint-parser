#define AppName "PowerPoint Visual Archive"
#ifndef AppVersion
#define AppVersion "0.1.4"
#endif
#define AppPublisher "Internal Distribution"

[Setup]
AppId={{7D27218A-AAB8-4D43-88A9-FF65BD47B6E8}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\PowerPoint Visual Archive
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
OutputDir=..\..\dist\installer
OutputBaseFilename=PowerPointVisualArchiveSetup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; The prior windowless v0.1.0 agent has no usable GUI/HTTP shutdown path.
; Restart Manager first requests a normal close, then terminates an unresponsive
; owner of these two installed program files. Never inspect or close the
; independent source-development pythonw.exe (port 8081), and never auto-
; restart the old executable after copying the replacement. This is a per-user
; upgrade; user-owned config and SQLite live outside {app}.
CloseApplications=force
CloseApplicationsFilter=PowerPointArchiveAgent.exe,pptviewer.exe
RestartApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#AppName}

[Files]
Source: "..\..\dist\pptviewer.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\dist\PowerPointArchiveAgent.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\PowerPoint Visual Archive Agent"; Filename: "{app}\PowerPointArchiveAgent.exe"; WorkingDir: "{app}"
Name: "{group}\PowerPoint Visual Archive CLI"; Filename: "{app}\pptviewer.exe"; WorkingDir: "{app}"
Name: "{userstartup}\PowerPoint Visual Archive"; Filename: "{app}\PowerPointArchiveAgent.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\pptviewer.exe"; Parameters: "init-config --root ""{code:GetScanRoot}"" --include-pdf"; StatusMsg: "Creating your archive configuration..."; Flags: runhidden waituntilterminated; Check: not ConfigExists
Filename: "{app}\PowerPointArchiveAgent.exe"; Description: "Start PowerPoint Visual Archive now"; Flags: nowait postinstall skipifsilent

[Code]
var
  ScanDirPage: TInputDirWizardPage;

function ConfigPath: String;
begin
  Result := ExpandConstant('{localappdata}\PowerPointVisualArchive\config.yaml');
end;

function ConfigExists: Boolean;
begin
  Result := FileExists(ConfigPath);
end;

function GetScanRoot(Param: String): String;
begin
  Result := ScanDirPage.Values[0];
end;

procedure InitializeWizard;
begin
  ScanDirPage := CreateInputDirPage(
    wpSelectDir,
    'Choose presentations to index',
    'Select the top-level folder containing the PowerPoint and PDF files you want in your archive.',
    'You can change this later using the support CLI. Existing configurations are preserved during upgrades.',
    False,
    ''
  );
  ScanDirPage.Add('Presentation folder:');
  ScanDirPage.Values[0] := ExpandConstant('{userdocs}');
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := ConfigExists and (PageID = ScanDirPage.ID);
end;
