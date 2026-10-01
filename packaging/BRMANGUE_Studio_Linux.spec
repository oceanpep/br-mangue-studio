# PyInstaller spec for the Linux desktop executable.
# Build from the project root with:
#   pyinstaller packaging/BRMANGUE_Studio_Linux.spec --clean

from pathlib import Path

import pyproj

from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH).resolve().parent.parent
source_root = project_root / "src"
assets_root = source_root / "brmangue_studio" / "assets"

hiddenimports = [
    "brmangue_lua.persistent_blocks",
    "brmangue_lua.raster_inputs",
    "brmangue_lua.raster_runner",
    "brmangue_studio",
] + collect_submodules("rasterio") + collect_submodules("pyproj")

datas = [
    (str(source_root / "brmangue_lua" / "engine.py"), "brmangue_lua"),
    (str(source_root / "brmangue_lua" / "raster_inputs.py"), "brmangue_lua"),
    (str(source_root / "brmangue_lua" / "raster_runner.py"), "brmangue_lua"),
    (str(assets_root / "BR-MANGUE_STUDIO_preview_original.png"), "brmangue_studio/assets"),
    (str(assets_root / "BR-MANGUE_STUDIO_transparent_4k.png"), "brmangue_studio/assets"),
    (str(assets_root / "BR-MANGUE_BR_icon.png"), "brmangue_studio/assets"),
    (str(assets_root / "GEOTAM_logo.jpeg"), "brmangue_studio/assets"),
    (pyproj.datadir.get_data_dir(), "pyproj/proj_dir/share/proj"),
]

a = Analysis(
    [str(source_root / "brmangue_studio" / "__main__.py")],
    pathex=[str(source_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "dissmodel", "geopandas", "fiona", "shapely", "folium",
        "PyQt5", "qtpy", "IPython", "jupyter", "jupyterlab", "notebook",
        "dask", "distributed", "bokeh", "plotly", "scipy", "statsmodels",
        "skimage", "sklearn", "xarray", "h5py", "astropy", "intake",
        "altair", "panel", "pyviz_comms", "zmq", "tables", "sqlalchemy",
        "botocore", "openpyxl", "lxml", "pyarrow", "cloudpickle", "numba",
        "llvmlite", "cryptography", "bcrypt",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="BRMANGUE_Studio_Linux_x86_64",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
