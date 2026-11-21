"""Shared test helper to locate or build an up-to-date PluginSpike.dll, skipping cleanly when dotnet is absent."""
from pathlib import Path
import shutil
import subprocess
import unittest


def ensure_pluginspike_dll(repo_root: str | Path) -> str:
    """Return path to an up-to-date PluginSpike.dll, building Release if missing/stale or skipping without dotnet."""
    dotnet = shutil.which("dotnet")
    if not dotnet:
        raise unittest.SkipTest(".NET SDK (dotnet) is required to build and run PluginSpike.dll")

    root = Path(repo_root)
    proj_dir = root / "dotnet" / "PluginSpike"
    csproj = proj_dir / "PluginSpike.csproj"
    if not csproj.is_file():
        raise FileNotFoundError(f"Missing project file: {csproj}")

    src_mtimes = [
        p.stat().st_mtime
        for p in proj_dir.rglob("*")
        if p.is_file()
        and p.suffix.lower() in (".cs", ".csproj")
        and "bin" not in p.parts
        and "obj" not in p.parts
    ]
    newest_src = max(src_mtimes, default=0.0)

    for cfg in ("Release", "Debug"):
        cand = proj_dir / "bin" / cfg / "net9.0" / "PluginSpike.dll"
        if cand.is_file() and cand.stat().st_mtime >= newest_src:
            return str(cand)

    subprocess.run(
        [dotnet, "build", str(csproj), "-c", "Release", "--nologo"],
        check=True,
        capture_output=True,
        text=True,
    )
    built = proj_dir / "bin" / "Release" / "net9.0" / "PluginSpike.dll"
    if built.is_file():
        return str(built)
    raise FileNotFoundError("PluginSpike.dll was not produced by dotnet build")
