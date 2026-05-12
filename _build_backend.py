from __future__ import annotations

import base64
import hashlib
import zipfile
from pathlib import Path


NAME = "constellation"
VERSION = "0.1.0"
SUMMARY = "Restriction-rewriting literature synthesis over claim/evidence sheaves"
DIST_INFO = f"{NAME}-{VERSION}.dist-info"
TAG = "py3-none-any"
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"


def get_requires_for_build_wheel(config_settings=None) -> list[str]:
    return []


def get_requires_for_build_editable(config_settings=None) -> list[str]:
    return []


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None) -> str:
    dist = Path(metadata_directory) / DIST_INFO
    _write_metadata_dir(dist)
    return DIST_INFO


def prepare_metadata_for_build_editable(metadata_directory, config_settings=None) -> str:
    return prepare_metadata_for_build_wheel(metadata_directory, config_settings)


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None) -> str:
    wheel_name = f"{NAME}-{VERSION}-{TAG}.whl"
    wheel_path = Path(wheel_directory) / wheel_name
    records: list[tuple[str, str, str]] = []
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted((SRC / NAME).rglob("*.py")):
            arcname = path.relative_to(SRC).as_posix()
            _write_file(zf, arcname, path.read_bytes(), records)
        _write_dist_info(zf, records)
    _write_record(wheel_path, records)
    return wheel_name


def build_editable(wheel_directory, config_settings=None, metadata_directory=None) -> str:
    wheel_name = f"{NAME}-{VERSION}-{TAG}.whl"
    wheel_path = Path(wheel_directory) / wheel_name
    records: list[tuple[str, str, str]] = []
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        _write_file(zf, f"{NAME}.pth", str(SRC).encode() + b"\n", records)
        _write_dist_info(zf, records)
    _write_record(wheel_path, records)
    return wheel_name


def _metadata_text() -> str:
    return (
        "Metadata-Version: 2.1\n"
        f"Name: {NAME}\n"
        f"Version: {VERSION}\n"
        f"Summary: {SUMMARY}\n"
        "Requires-Python: >=3.13\n"
        "Provides-Extra: dev\n"
    )


def _wheel_text() -> str:
    return (
        "Wheel-Version: 1.0\n"
        "Generator: constellation-local-backend\n"
        "Root-Is-Purelib: true\n"
        f"Tag: {TAG}\n"
    )


def _entry_points_text() -> str:
    return "[console_scripts]\nconstellation = constellation.cli:main\n"


def _write_metadata_dir(dist: Path) -> None:
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "METADATA").write_text(_metadata_text())
    (dist / "WHEEL").write_text(_wheel_text())
    (dist / "entry_points.txt").write_text(_entry_points_text())


def _write_dist_info(zf: zipfile.ZipFile, records: list[tuple[str, str, str]]) -> None:
    _write_file(zf, f"{DIST_INFO}/METADATA", _metadata_text().encode(), records)
    _write_file(zf, f"{DIST_INFO}/WHEEL", _wheel_text().encode(), records)
    _write_file(zf, f"{DIST_INFO}/entry_points.txt", _entry_points_text().encode(), records)


def _write_file(
    zf: zipfile.ZipFile,
    arcname: str,
    data: bytes,
    records: list[tuple[str, str, str]],
) -> None:
    zf.writestr(arcname, data)
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    records.append((arcname, f"sha256={digest}", str(len(data))))


def _write_record(wheel_path: Path, records: list[tuple[str, str, str]]) -> None:
    record_name = f"{DIST_INFO}/RECORD"
    lines = [",".join(row) for row in records]
    lines.append(f"{record_name},,")
    data = ("\n".join(lines) + "\n").encode()
    with zipfile.ZipFile(wheel_path, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(record_name, data)
