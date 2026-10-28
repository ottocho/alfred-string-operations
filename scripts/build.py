"""Build a fresh Alfred package from the checked-in runtime files."""

from pathlib import Path
import plistlib
import zipfile

ROOT = Path(__file__).resolve().parent.parent
FILES = ("info.plist", "icon.png", "run.sh", "string_operations.py")


def build(output: Path | None = None) -> Path:
    source = ROOT / "workflow"
    metadata = plistlib.loads((source / "info.plist").read_bytes())
    if metadata["bundleid"] != "ottocho.alfred.string-operations":
        raise ValueError("Unexpected workflow bundle ID")
    output = output or ROOT / "dist" / "String-Operations.alfredworkflow"
    output.parent.mkdir(parents=True, exist_ok=True)
    # Fixed metadata makes unchanged builds byte-for-byte reproducible.
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            entry = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = (0o100755 if name == "run.sh" else 0o100644) << 16
            archive.writestr(entry, (source / name).read_bytes())
    return output


if __name__ == "__main__":
    print(build())
