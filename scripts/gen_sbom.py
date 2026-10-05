"""Write docs/sbom.json (CycloneDX-style) from installed, pinned dependencies."""
import json
from importlib import metadata
from pathlib import Path

components = []
for name in ("Django", "openpyxl", "et_xmlfile", "asgiref", "sqlparse", "tzdata"):
    try:
        d = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        continue
    lic = d.metadata.get("License-Expression") or d.metadata.get("License") or "see package"
    if len(lic) > 60:
        lic = (d.metadata.get_all("Classifier") or ["see package"])[0].split("::")[-1].strip()
    components.append({"type": "library", "name": d.metadata["Name"], "version": d.version, "licenses": [{"license": {"name": lic}}]})
Path("docs/sbom.json").write_text(json.dumps({"bomFormat": "CycloneDX", "specVersion": "1.5", "components": components}, indent=2))
print(f"SBOM written with {len(components)} components")
