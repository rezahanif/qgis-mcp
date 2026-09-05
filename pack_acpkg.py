import hashlib
import zipfile
from pathlib import Path

root = Path(".").resolve()
dist = root / "dist"
dist.mkdir(exist_ok=True)
out_pkg = dist / "qgis-mcp-1.0.0-windows-x64.acpkg"

files = ["manifest.json", "marketplace.json", "TUTORIAL.md", "run_server.py"]
dirs = ["assets", "src", "_vendor"]

with zipfile.ZipFile(out_pkg, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for f in files:
        if (root / f).is_file():
            zf.write(root / f, f)
    for d in dirs:
        dp = root / d
        if dp.is_dir():
            for p in dp.rglob("*"):
                if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc":
                    zf.write(p, p.relative_to(root).as_posix())

# Generate SHA256 checksum file
sha256 = hashlib.sha256(out_pkg.read_bytes()).hexdigest()
(dist / f"{out_pkg.name}.sha256").write_text(f"{sha256} *{out_pkg.name}\n", encoding="ascii")
print(f"Built {out_pkg.name} ({out_pkg.stat().st_size:,} bytes) - SHA256: {sha256}")