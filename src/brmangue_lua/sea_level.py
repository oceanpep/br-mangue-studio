"""Calendar-based sea-level trajectories, expressed as cumulative change in mm."""

from __future__ import annotations

from bisect import bisect_right
import csv
from dataclasses import dataclass
import hashlib
import io
import math
from pathlib import Path
from typing import Any


TRAJECTORY_CSV_EXAMPLE = """# SYNTHETIC EXAMPLE ONLY. Replace values with documented projections before research use.
year,sea_level_mm
2020,0
2030,40
2040,90
2050,150
2060,220
2070,300
2080,390
2090,490
2100,600
"""


@dataclass(frozen=True)
class SeaLevelTrajectory:
    """Samples relative to one common baseline; interpolation never extrapolates.

    The baseline may be the IPCC reference period or another documented period.
    The engine subtracts the level at its own initial calendar year, so that
    only changes after the initial raster date enter the simulation.
    """

    years: tuple[int, ...]
    sea_level_mm: tuple[float, ...]
    source_name: str = ""
    source_sha256: str = ""

    def __post_init__(self) -> None:
        try:
            years = tuple(int(year) for year in self.years)
            levels = tuple(float(level) for level in self.sea_level_mm)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("Trajectory years and sea levels must be numeric.") from exc
        if len(years) < 2 or len(years) != len(levels):
            raise ValueError("A trajectory requires at least two year/sea_level_mm pairs.")
        if any(float(original) != year for original, year in zip(self.years, years)):
            raise ValueError("Trajectory years must be whole calendar years.")
        if any(b <= a for a, b in zip(years, years[1:])):
            raise ValueError("Trajectory years must be unique and strictly increasing.")
        if not all(math.isfinite(value) for value in levels):
            raise ValueError("Trajectory sea levels must be finite numbers in millimetres.")
        object.__setattr__(self, "years", years)
        object.__setattr__(self, "sea_level_mm", levels)

    @classmethod
    def from_csv(cls, path: str | Path) -> "SeaLevelTrajectory":
        path = Path(path)
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        # Accept spreadsheet CSVs with either comma or semicolon delimiters.
        lines = [line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        if not lines:
            raise ValueError("The trajectory CSV is empty.")
        delimiter = ";" if ";" in lines[0] else ","
        reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delimiter)
        names = {str(name).strip(): name for name in reader.fieldnames or []}
        if not {"year", "sea_level_mm"}.issubset(names):
            raise ValueError("The trajectory CSV requires columns year and sea_level_mm.")
        years: list[int] = []
        levels: list[float] = []
        for row_number, row in enumerate(reader, 2):
            try:
                year_number = float(row[names["year"]])
                year = int(year_number)
                if year != year_number:
                    raise ValueError
                value = row[names["sea_level_mm"]]
                levels.append(float(value.replace(",", ".") if delimiter == ";" else value))
                years.append(year)
            except (ValueError, TypeError, AttributeError, OverflowError) as exc:
                raise ValueError(f"Invalid year or sea_level_mm at CSV row {row_number}.") from exc
        return cls(tuple(years), tuple(levels), path.name, hashlib.sha256(raw).hexdigest())

    def level_mm(self, year: int | float) -> float:
        if not math.isfinite(year) or year < self.years[0] or year > self.years[-1]:
            raise ValueError(
                f"Trajectory covers {self.years[0]}–{self.years[-1]}; year {year} is outside this range."
            )
        index = bisect_right(self.years, year) - 1
        if index == len(self.years) - 1 or year == self.years[index]:
            return self.sea_level_mm[index]
        fraction = (year - self.years[index]) / (self.years[index + 1] - self.years[index])
        return self.sea_level_mm[index] + fraction * (self.sea_level_mm[index + 1] - self.sea_level_mm[index])

    def validate_period(self, initial_year: int, final_year: int) -> None:
        if final_year < initial_year:
            raise ValueError("Final calendar year must be greater than or equal to initial year.")
        self.level_mm(initial_year)
        self.level_mm(final_year)

    def to_dict(self) -> dict[str, Any]:
        return {
            "years": list(self.years),
            "sea_level_mm": list(self.sea_level_mm),
            "source_name": self.source_name,
            "source_sha256": self.source_sha256,
            "interpolation": "linear",
            "units": "mm",
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SeaLevelTrajectory":
        if value.get("units", "mm") != "mm" or value.get("interpolation", "linear") != "linear":
            raise ValueError("Trajectories require millimetres and linear interpolation.")
        return cls(
            tuple(value.get("years", ())), tuple(value.get("sea_level_mm", ())),
            str(value.get("source_name", "")), str(value.get("source_sha256", "")),
        )


def trajectory_from_project(parameters: dict[str, Any], project_dir: Path) -> SeaLevelTrajectory | None:
    """Read embedded samples first, keeping saved projects independent of the CSV."""
    mode = parameters.get("sea_level_mode", "constant")
    if mode == "constant":
        return None
    if mode != "trajectory":
        raise ValueError(f"Unknown sea-level mode: {mode}.")
    embedded = parameters.get("sea_level_trajectory")
    if embedded:
        return SeaLevelTrajectory.from_dict(embedded)
    path = parameters.get("sea_level_trajectory_file", "")
    if not path:
        raise ValueError("Choose a trajectory CSV before running the simulation.")
    candidate = Path(path)
    return SeaLevelTrajectory.from_csv(candidate if candidate.is_absolute() else project_dir / candidate)
