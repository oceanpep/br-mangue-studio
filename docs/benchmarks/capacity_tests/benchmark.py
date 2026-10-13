#!/usr/bin/env python3
"""Deterministic synthetic capacity benchmark for BR-MANGUE raster runner."""
from __future__ import annotations
import hashlib, json, math, os, platform, re, subprocess, sys, time
from importlib import metadata as importlib_metadata
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import psutil
import rasterio
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "dados_sinteticos"
RUNS = ROOT / "execucoes" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
SIZES = [(1024, 1024), (2048, 2048), (2048, 4096), (4096, 4096)]
ENGINES = [("continuous", None), ("blocks", 100_000)]


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b""): h.update(chunk)
    return h.hexdigest()


def generate_inputs(height:int,width:int)->tuple[Path,Path]:
    cells=height*width
    folder=DATA/f"grid_{cells:,}_cells".replace(",", "")
    lc=folder/"synthetic_land_cover.tif"; dem=folder/"synthetic_dem.tif"
    if lc.exists() and dem.exists(): return lc,dem
    folder.mkdir(parents=True,exist_ok=True)
    profile={"driver":"GTiff","height":height,"width":width,"count":1,"crs":"EPSG:3857",
             "transform":from_origin(1_000_000,1_000_000+height*30,30,30),
             "tiled":True,"blockxsize":256,"blockysize":256,"compress":"deflate","predictor":2}
    col=np.arange(width,dtype=np.int32)[None,:]
    with rasterio.open(lc,"w",**profile,dtype="uint8",nodata=0) as dst_lc, \
         rasterio.open(dem,"w",**profile,dtype="float32",nodata=-9999) as dst_dem:
        for r0 in range(0,height,128):
            r1=min(r0+128,height)
            row=np.arange(r0,r1,dtype=np.int32)[:,None]
            pattern=((col//32 + row//32)%4)
            block=np.where(pattern==0,5,np.where(pattern==1,11,np.where(pattern==2,33,15))).astype(np.uint8)
            elevation=(0.2 + (row%400)*0.012 + (col%300)*0.014).astype(np.float32)
            dst_lc.write(block,1,window=((r0,r1),(0,width)))
            dst_dem.write(elevation,1,window=((r0,r1),(0,width)))
    return lc,dem


def run_one(lc:Path,dem:Path,ncells:int,engine:str,block_size:int|None)->dict:
    out=RUNS/f"{ncells}_cells"/(f"{engine}_{block_size}" if block_size else engine)
    out.mkdir(parents=True,exist_ok=True)
    runner=ROOT/"run_one.py"
    cmd=[sys.executable,str(runner),str(lc),str(dem),str(out),str(ncells),engine,str(block_size or 0)]
    proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    ps=psutil.Process(proc.pid); peak=0; started=time.perf_counter()
    while proc.poll() is None:
        try: peak=max(peak,ps.memory_info().rss)
        except psutil.Error: pass
        time.sleep(0.25)
    try: peak=max(peak,ps.memory_info().rss)
    except psutil.Error: pass
    stdout,stderr=proc.communicate()
    (out/"runner_stdout.json").write_text(stdout,encoding="utf-8")
    if proc.returncode:
        (out/"runner_stderr.log").write_text(stderr,encoding="utf-8")
        raise RuntimeError(f"{cmd} failed ({proc.returncode}): {stderr[-3000:]}\n{stdout[-1000:]}")
    result=json.loads(stdout)
    result["externally_sampled_peak_rss_bytes_including_load"]=peak
    result["wall_seconds_parent_process"]=round(time.perf_counter()-started,3)
    result["stderr_tail"]=stderr[-1000:]
    return result


def _cpu_model()->str|None:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":",1)[1].strip()
    except OSError: pass
    return platform.processor() or None


def _package_versions()->dict[str,str]:
    names=("numpy","rasterio","pandas","psutil","affine","pyproj")
    return {name:importlib_metadata.version(name) for name in names}


def main():
    results=[]
    env={"utc":datetime.now(timezone.utc).isoformat(),"python":sys.version,"platform":platform.platform(),
         "processor":platform.processor(),"cpu_model":_cpu_model(),"package_versions":_package_versions(),
         "logical_cpus":os.cpu_count(),"ram_bytes":psutil.virtual_memory().total,
         "source_tag":"v1.1.0","source_commit":"61630971869a5b9747d1b0dcf638e464446bc1b3",
         "input_design":"synthetic grid; 30 m cells; EPSG:3857 with arbitrary origin; repeated 32-cell classes (5,11,33,15) and deterministic 0.2-9.174 m elevation pattern; all pixels valid; no ecological meaning.",
         "duration_years":5,"annual_state_exports":False,"engines":["continuous","blocks"],
         "synthetic_source_class_mapping":{"5":"mangrove","11":"natural_candidate","33":"water","15":"managed_or_blocked"},
         "block_size_cells":100000,"parameters":{"tide_height":6.0,"sea_level_rise_rate":0.5,"allow_migration_without_soil":True,"migration_maturity_years":1}}
    RUNS.mkdir(parents=True,exist_ok=True)
    record={"environment":env,"grid_results":results}
    out_json=ROOT/"synthetic_capacity_benchmark.json"
    for height,width in SIZES:
        n=height*width
        print(f"Generating grid {n:,} cells ({height} x {width})",flush=True)
        lc,dem=generate_inputs(height,width)
        info={"shape":[height,width],"cells":n,"land_cover_sha256":sha256(lc),"dem_sha256":sha256(dem),"engines":[]}
        for engine,block in ENGINES:
            print(f"Running {engine} on {n:,} cells for five annual steps...",flush=True)
            item=run_one(lc,dem,n,engine,block)
            info["engines"].append(item)
            out_json.write_text(json.dumps(record,indent=2),encoding="utf-8")
            print(f"Completed {engine}: {item['performance']['simulation_elapsed_seconds']:.3f}s; "
                  f"{item['performance']['cell_updates_per_second']:,.0f} updates/s; "
                  f"external peak RSS {item['externally_sampled_peak_rss_bytes_including_load']/1024**2:.1f} MiB",flush=True)
        a,b=info["engines"]
        info["final_state_pixel_arrays_identical"]=a["final_state_pixel_sha256"]==b["final_state_pixel_sha256"]
        if not info["final_state_pixel_arrays_identical"]:
            raise RuntimeError(f"Final cell states differ at {n} cells")
        results.append(info)
        print(f"Final states match at {n:,} cells.",flush=True)
        out_json.write_text(json.dumps(record,indent=2),encoding="utf-8")


if __name__=="__main__": main()
