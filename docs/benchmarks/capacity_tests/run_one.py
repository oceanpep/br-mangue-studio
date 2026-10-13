#!/usr/bin/env python3
import hashlib,json,sys
from pathlib import Path
import rasterio
from brmangue_lua.engine import ModelParameters
from brmangue_lua.raster_inputs import load_raster_inputs
from brmangue_lua.raster_runner import run_raster_simulation

lc,dem,out,ncells,engine,block=sys.argv[1:]
ncells=int(ncells); block=int(block)
inputs=load_raster_inputs(lc,dem,soil_enabled=False)
if inputs.n_cells!=ncells: raise RuntimeError(f"Loaded {inputs.n_cells:,}, expected {ncells:,}")
params=ModelParameters(start=1,final_time=5,tide_height=6.0,sea_level_rise_rate=0.5,
    allow_migration_without_soil=True,migration_maturity_years=1)
trajectory=run_raster_simulation(inputs,out,params,initial_year=2025,engine=engine,
    block_size=block or 100000,save_annual_states=False)
meta=json.loads((Path(out)/"metadata.json").read_text(encoding="utf-8"))
with rasterio.open(Path(out)/"final_usos_2030.tif") as ds:
    arr=ds.read(1)
    pixel_hash=hashlib.sha256(arr.tobytes()).hexdigest()
print(json.dumps({"engine":engine,"block_size_cells":block or None,"cells":ncells,
    "years":5,"initial_year":2025,"final_year":2030,"performance":meta["performance"],
    "trajectory_final_row":trajectory.tail(1).to_dict(orient="records")[0],
    "final_state_pixel_sha256":pixel_hash},separators=(",",":")))
