# Extended Windows build with the optional DissModel adapter included.
# Build from the project root with:
#   pyinstaller packaging\BRMANGUE_Studio_DissModel.spec --clean --noconfirm

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = [
    "brmangue_lua.persistent_blocks",
    "brmangue_lua.raster_inputs",
    "brmangue_lua.raster_runner",
    "brmangue_lua.dissmodel_adapter",
    "brmangue_studio",
    "dissmodel",
    "dissmodel.core",
    "dissmodel.visualization",
    "dissmodel.visualization.chart",
    "dissmodel.visualization.widgets",
    "dissmodel.visualization.map",
    "dissmodel.visualization.raster_map",
] + collect_submodules("rasterio")

datas = [
    ("../src/brmangue_lua/engine.py", "brmangue_lua"),
    ("../src/brmangue_lua/raster_inputs.py", "brmangue_lua"),
    ("../src/brmangue_lua/raster_runner.py", "brmangue_lua"),
    ("../src/brmangue_lua/dissmodel_adapter.py", "brmangue_lua"),
    ("../src/brmangue_studio/assets/BR-MANGUE_STUDIO_preview_original.png", "brmangue_studio/assets"),
    ("../src/brmangue_studio/assets/BR-MANGUE_STUDIO_transparent_4k.png", "brmangue_studio/assets"),
    ("../src/brmangue_studio/assets/BR-MANGUE_BR_icon.png", "brmangue_studio/assets"),
    ("../src/brmangue_studio/assets/BR-MANGUE_BR_icon.ico", "brmangue_studio/assets"),
    ("../src/brmangue_studio/assets/GEOTAM_logo.jpeg", "brmangue_studio/assets"),
]

a = Analysis(
    ["../src/brmangue_studio/__main__.py"],
    pathex=["../src", r"C:\Users\felly\dissmodel"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "geopandas", "fiona", "shapely", "pyproj", "folium", "PyQt5",
        "qtpy", "IPython", "jupyter", "jupyterlab", "notebook", "dask",
        "distributed", "bokeh", "plotly", "scipy", "statsmodels", "skimage",
        "sklearn", "xarray", "h5py", "astropy", "intake", "altair", "panel",
        "pyviz_comms", "zmq", "tables", "sqlalchemy", "botocore", "openpyxl",
        "lxml", "pyarrow", "cloudpickle", "numba", "llvmlite", "cryptography",
        "bcrypt",
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
    name="BRMANGUE_Studio_DissModel",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="../src/brmangue_studio/assets/BR-MANGUE_BR_icon.ico",
)
