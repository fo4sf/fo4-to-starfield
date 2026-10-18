# Codex: dot-source only; loading this helper never starts a process or reads live configuration.
# Invoke-CodexHandover returns one Boolean, true only after a successful child exit and a new report.
function ConvertTo-CodexNativeArgument([AllowEmptyString()][string]$Value) {
  # Windows CommandLineToArgvW/CRT quoting, including quotes and trailing backslashes (PowerShell 5.1).
  $escaped = [regex]::Replace($Value, '(\\*)"', '$1$1\"')
  '"' + [regex]::Replace($escaped, '(\\+)$', '$1$1') + '"'
}

function Test-CodexBundle([string]$Executable) {
  if (-not $Executable -or -not (Test-Path -LiteralPath $Executable -PathType Leaf)) { return $false }
  if ([IO.Path]::GetExtension($Executable) -ine '.exe') { return $false }
  $folder = Split-Path -Parent $Executable
  foreach ($companion in @('codex-code-mode-host.exe', 'codex-command-runner.exe')) {
    if (-not (Test-Path -LiteralPath (Join-Path $folder $companion) -PathType Leaf)) { return $false }
  }
  return $true
}

function Resolve-CodexBundle([AllowNull()][object]$ConfiguredExe) {
  if ($null -ne $ConfiguredExe) {
    # Explicit configuration is authoritative, including an invalid/empty value. Never fall back.
    # IsPathRooted also accepts C:relative and \root-relative on Windows. Require a drive root or UNC share.
    if ($ConfiguredExe -isnot [string] -or
        $ConfiguredExe -notmatch '^(?:[A-Za-z]:[\\/]|[\\/]{2}[^\\/]+[\\/][^\\/]+[\\/])' -or
        -not (Test-CodexBundle $ConfiguredExe)) {
      throw 'configured codex_exe must be an absolute executable path with sibling codex-code-mode-host.exe and codex-command-runner.exe; no fallback'
    }
    return (Resolve-Path -LiteralPath $ConfiguredExe -ErrorAction Stop).ProviderPath
  }
  # Prefer installed PATH applications; skip copied/shim executables without their full bundle.
  foreach ($command in @(Get-Command codex.exe -CommandType Application -All -ErrorAction SilentlyContinue)) {
    if (Test-CodexBundle $command.Source) { return $command.Source }
  }
  # Desktop updates change the bundle directory name. Inspect only the installation's bin children.
  if ($env:LOCALAPPDATA) {
    $root = Join-Path $env:LOCALAPPDATA 'OpenAI\Codex\bin'
    if (Test-Path -LiteralPath $root -PathType Container) {
      $folders = Get-ChildItem -LiteralPath $root -Directory -ErrorAction Stop |
                 Sort-Object -Property @{ Expression = 'LastWriteTimeUtc'; Descending = $true }, Name
      foreach ($folder in $folders) {
        $candidate = Join-Path $folder.FullName 'codex.exe'
        if (Test-CodexBundle $candidate) { return $candidate }
      }
    }
  }
  throw 'no complete Codex bundle on PATH or under LOCALAPPDATA\OpenAI\Codex\bin; no hand-over'
}

function Invoke-CodexProcess {
  param([string]$Executable, [string[]]$Arguments, [string]$Workspace,
        [AllowEmptyString()][string]$InputText = '',
        [ValidateRange(1, 2147483647)][int]$TimeoutMilliseconds = 600000)
  $info = New-Object System.Diagnostics.ProcessStartInfo
  $info.FileName = $Executable
  $info.Arguments = ($Arguments | ForEach-Object { ConvertTo-CodexNativeArgument $_ }) -join ' '
  $info.WorkingDirectory = $Workspace
  $info.UseShellExecute = $false
  $info.CreateNoWindow = $true
  $info.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
  $info.RedirectStandardInput = $true
  $info.RedirectStandardOutput = $true
  $info.RedirectStandardError = $true
  $info.StandardOutputEncoding = [Text.Encoding]::UTF8
  $info.StandardErrorEncoding = [Text.Encoding]::UTF8
  $process = New-Object System.Diagnostics.Process
  $process.StartInfo = $info
  $started = $false
  $clock = [Diagnostics.Stopwatch]::StartNew()
  try {
    if (-not $process.Start()) { throw 'child did not start' }
    $started = $true
    # Drain both streams concurrently so neither a probe nor an exec can deadlock on a full pipe.
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    $inputError = $null
    $timedOut = $false
    try {
      $inputTask = $process.StandardInput.WriteAsync($InputText)
      $remaining = [int][Math]::Max(0, $TimeoutMilliseconds - $clock.ElapsedMilliseconds)
      $timedOut = -not $inputTask.Wait($remaining)
    } catch { $inputError = $_.Exception.Message }
    if (-not $timedOut) {
      try { $process.StandardInput.Close() } catch { if (-not $inputError) { $inputError = $_.Exception.Message } }
      $remaining = [int][Math]::Max(0, $TimeoutMilliseconds - $clock.ElapsedMilliseconds)
      $timedOut = -not $process.WaitForExit($remaining)
    }
    if (-not $timedOut) {
      # Descendants can hold inherited output handles after the CLI exits; keep that wait bounded too.
      $remaining = [int][Math]::Max(0, $TimeoutMilliseconds - $clock.ElapsedMilliseconds)
      $timedOut = -not [Threading.Tasks.Task]::WaitAll([Threading.Tasks.Task[]]@($stdout, $stderr), $remaining)
    }
    if ($timedOut) {
      if (-not $process.HasExited) { $process.Kill() }
      [void]$process.WaitForExit(1000)
      try { [void][Threading.Tasks.Task]::WaitAll([Threading.Tasks.Task[]]@($stdout, $stderr), 1000) } catch { }
    }
    $outputText = if ($stdout.IsCompleted -and -not $stdout.IsFaulted) { $stdout.GetAwaiter().GetResult() } else { '' }
    $errorText = if ($stderr.IsCompleted -and -not $stderr.IsFaulted) { $stderr.GetAwaiter().GetResult() }
                 else { 'child stderr pipe did not close; diagnostics may be incomplete' }
    $exitCode = if ($process.HasExited) { $process.ExitCode } else { -1 }
    [pscustomobject]@{ ExitCode = $exitCode; Stdout = $outputText; Stderr = $errorText;
                      TimedOut = $timedOut; InputError = $inputError }
  } finally {
    if ($started -and -not $process.HasExited) { $process.Kill() }
    $process.Dispose()
  }
}

function Add-CodexDiagnostic([string]$LogPath, [string]$Message) {
  "$(Get-Date -Format s) $Message" | Add-Content -LiteralPath $LogPath -Encoding utf8 -ErrorAction Stop
}

function Invoke-CodexHandover {
  param([AllowNull()][object]$ConfiguredExe = $null,
        [Parameter(Mandatory = $true)][string]$Workspace,
        [Parameter(Mandatory = $true)][string]$Prompt,
        [Parameter(Mandatory = $true)][string]$OutputPath,
        [Parameter(Mandatory = $true)][string]$LogPath,
        [ValidateRange(1, 2147483647)][int]$ExecTimeoutMilliseconds = 600000)
  $ErrorActionPreference = 'Stop'
  $diagnosticPath = $null
  $pendingPath = $null
  $published = $false
  try {
    $workspacePath = (Resolve-Path -LiteralPath $Workspace -ErrorAction Stop).ProviderPath
    if (-not (Test-Path -LiteralPath $workspacePath -PathType Container)) { throw 'workspace must already exist' }
    $OutputPath = [IO.Path]::GetFullPath($OutputPath)
    $LogPath = [IO.Path]::GetFullPath($LogPath)
    foreach ($path in @($LogPath, $OutputPath)) {
      if ((Split-Path -Parent $path).TrimEnd('\', '/') -ine $workspacePath.TrimEnd('\', '/')) {
        throw 'report and diagnostic log must be in the existing workspace directory'
      }
      if ($path -eq $LogPath) { $diagnosticPath = $LogPath }
    }
    if ($OutputPath -ieq $LogPath) { throw 'report and diagnostic log must be different files' }
    if (Test-Path -LiteralPath $OutputPath) { throw 'report already exists; refusing to treat stale output as success' }
    $exe = Resolve-CodexBundle $ConfiguredExe
    Add-CodexDiagnostic $LogPath "Codex bundle selected: $exe"
    foreach ($probe in @(@('--version'), @('exec', '--help'))) {
      $result = Invoke-CodexProcess -Executable $exe -Arguments $probe -Workspace $workspacePath -TimeoutMilliseconds 15000
      Add-Content -LiteralPath "$OutputPath.log" -Encoding utf8 -Value $result.Stdout
      Add-Content -LiteralPath "$OutputPath.err" -Encoding utf8 -Value $result.Stderr
      if ($result.TimedOut) { throw "Codex probe '$($probe -join ' ')' timed out after 15000 ms: $($result.Stderr)" }
      if ($result.ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($result.Stdout)) {
        throw "Codex probe '$($probe -join ' ')' failed (exit $($result.ExitCode)): $($result.Stderr)"
      }
      if ($result.InputError) { throw "Codex probe stdin failed: $($result.InputError)" }
      if ($probe[0] -eq '--version') {
        if ($result.Stdout -notmatch 'codex(?:-cli)?\s+\d+\.\d+\.\d+') { throw 'unrecognized Codex version response' }
        Add-CodexDiagnostic $LogPath "Codex version: $($result.Stdout.Trim())"
      } else {
        foreach ($flag in @('--sandbox', '--config', '--cd', '--output-last-message', '--skip-git-repo-check')) {
          if (-not $result.Stdout.Contains($flag)) { throw "Codex exec probe missing supported flag $flag" }
        }
      }
    }
    # Reserve a unique same-directory report. The CLI never receives the final path, even if it appears during probes.
    $candidate = Join-Path $workspacePath ('.codex_handover_{0}.pending.md' -f [Guid]::NewGuid().ToString('N'))
    $reservation = [IO.File]::Open($candidate, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    $pendingPath = $candidate
    $reservation.Dispose()
    $arguments = @('exec', '--skip-git-repo-check', '-C', $workspacePath, '--sandbox', 'workspace-write',
                   '-c', 'sandbox_workspace_write.network_access=true', '-o', $pendingPath, '-')
    Add-CodexDiagnostic $LogPath "Codex hand-over started; awaiting child exit (temporary report $pendingPath; final $OutputPath)"
    $result = Invoke-CodexProcess -Executable $exe -Arguments $arguments -Workspace $workspacePath -InputText $Prompt `
                                  -TimeoutMilliseconds $ExecTimeoutMilliseconds
    Add-Content -LiteralPath "$OutputPath.log" -Encoding utf8 -Value $result.Stdout
    Add-Content -LiteralPath "$OutputPath.err" -Encoding utf8 -Value $result.Stderr
    if ($result.TimedOut) { throw "Codex child timed out after $ExecTimeoutMilliseconds ms: $($result.Stderr)" }
    if ($result.ExitCode -ne 0) { throw "Codex child failed (exit $($result.ExitCode)): $($result.Stderr)" }
    if ($result.InputError) { throw "Codex child stdin failed: $($result.InputError)" }
    if (-not (Test-Path -LiteralPath $pendingPath -PathType Leaf) -or (Get-Item -LiteralPath $pendingPath -Force).Length -eq 0) {
      throw 'Codex child exited 0 without a nonempty new report'
    }
    # The two-argument move refuses an existing destination; do not use a check followed by an overwrite.
    [IO.File]::Move($pendingPath, $OutputPath)
    $published = $true
    Add-CodexDiagnostic $LogPath "Codex hand-over completed (exit 0, report $OutputPath)"
    return $true
  } catch {
    $message = "Codex hand-over refused/failed: $_"
    if ($pendingPath -and -not $published) { $message += "; unpublished temporary report for diagnostics: $pendingPath" }
    try {
      if (-not $diagnosticPath) { throw 'no validated diagnostic path' }
      Add-CodexDiagnostic $diagnosticPath $message
    } catch { Write-Warning "$message; diagnostic log unavailable: $_" }
    return $false
  }
}
