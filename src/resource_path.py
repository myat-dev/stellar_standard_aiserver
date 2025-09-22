import sys
from pathlib import Path

def src_path(relative_path: str) -> Path:
    """Get absolute path to src, for Development and PyInstaller EXE

    Args:
        relative_path (str): Path with respect to src directory

    Returns:
        Pahh: Full Path to the specified relative path
    """
    try:
        base_path = Path(sys._MEIPASS) / "src"
    except AttributeError:
        base_path = Path(__file__).parent

    return base_path / relative_path