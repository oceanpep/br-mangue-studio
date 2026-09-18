# PyInstaller spec for the optional desktop interface.
# Build from the project root with:
#   pyinstaller packaging/BRMANGUE_Studio.spec --clean

import os
import pyproj

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = [
    "brmangue_lua.persistent_blocks",
    "brmangue_lua.raster_inputs",
    "brmangue_lua.raster_runner",
    "brmangue_studio",
] + collect_submodules("rasterio") + collect_submodules("pyproj")

datas = [
    ("../src/brmangue_lua/engine.py", "brmangue_lua"),
    ("../src/brmangue_lua/raster_inputs.py", "brmangue_lua"),
    ("../src/brmangue_lua/raster_runner.py", "brmangue_lua"),
    ("../src/brmangue_studio/assets/BR-MANGUE_STUDIO_preview_original.png", "brmangue_studio/assets"),
    ("../src/brmangue_studio/assets/BR-MANGUE_STUDIO_transparent_4k.png", "brmangue_studio/assets"),
    ("../src/brmangue_studio/assets/BR-MANGUE_BR_icon.png", "brmangue_studio/assets"),
    ("../src/brmangue_studio/assets/BR-MANGUE_BR_icon.ico", "brmangue_studio/assets"),
    ("../src/brmangue_studio/assets/GEOTAM_logo.jpeg", "brmangue_studio/assets"),
]
pyproj_data = os.path.join(os.path.dirname(pyproj.__file__), "proj_dir", "share", "proj")
datas += [(pyproj_data, "pyproj/proj_dir/share/proj")]

a = Analysis(
    ["../src/brmangue_studio/__main__.py"],
    pathex=["../src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # The desktop raster build does not need the optional shapefile stack or
    # the full DissModel/Jupyter/Qt ecosystem. The Python source installation
    # still supports those integrations; a separate extended build can remove
    # these exclusions when required.
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
    name="BRMANGUE_Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="../src/brmangue_studio/assets/BR-MANGUE_BR_icon.ico",
)
