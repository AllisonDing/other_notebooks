# Getting Started with Sirius-Accelerated DuckDB in Jupyter

This guide walks through building [Sirius](https://github.com/sirius-db/sirius) from source, running GPU-accelerated DuckDB queries from a Jupyter notebook, and benchmarking CPU vs. GPU performance.

> **Note:** This guide covers the **pre-release developer path**, where you build the extension from source and load it by its file path. When the extension is published, setup should reduce to `INSTALL sirius; LOAD sirius;`. Until then, the workarounds below are required.

**Tested on:** Ubuntu 24.04, NVIDIA RTX PRO 6000 Blackwell (96 GB) and RTX A6000 (48 GB).

---

## 1. Requirements

- Linux (x86_64 or aarch64) with `glibc >= 2.28`
- NVIDIA GPU, Turing or newer (compute capability 7.5+)
- CUDA 13.x (driver 580.65.06+) or CUDA 12.x (driver 525.60.13+)

```bash
nvidia-smi                                         # confirm the driver works
```

## 2. Build Sirius (one time)

```bash
git clone --no-recurse-submodules https://github.com/sirius-db/sirius.git ~/sirius
cd ~/sirius
git submodule update --init --depth=1 --jobs 3 duckdb substrait cucascade
pixi run make TEST_BUILD_TARGET=                   # builds the Sirius extension

git submodule update --init --depth=1 duckdb-python
pixi run -e duckdb-python build-duckdb-python      # builds the matching DuckDB Python package
```

| Output | Location |
|---|---|
| Sirius extension | `~/sirius/build/release/extension/sirius/sirius.duckdb_extension` |
| Python environment | `~/sirius/.pixi/envs/duckdb-python` |

**What the last command means:** `pixi run` runs a command inside a pixi environment, `-e duckdb-python` selects the environment, and `build-duckdb-python` is a task defined in `pixi.toml`. It builds DuckDB's Python package from the same DuckDB source as the extension. A stock `pip install duckdb` will not work with this build.

## 3. Register a Jupyter kernel (one time)

```bash
pixi run -e duckdb-python python -m pip install ipykernel
pixi run -e duckdb-python python -m ipykernel install --user --name sirius-duckdb
```

In Jupyter, select the **`sirius-duckdb`** kernel. It's a regular Python kernel that uses the pixi environment's DuckDB.

To verify the kernel is correct:

```python
import sys, duckdb
print(sys.executable)      # should be ~/sirius/.pixi/envs/duckdb-python/bin/python
print(duckdb.__file__)
```

## 4. Minimal notebook setup

```python
import ctypes, os
from pathlib import Path

EXT = Path.home() / "sirius/build/release/extension/sirius/sirius.duckdb_extension"
os.environ["SIRIUS_PROTOTYPE_BACKEND"] = str(EXT)        # set before importing duckdb

import _duckdb, duckdb
ctypes.CDLL(_duckdb.__file__, mode=ctypes.RTLD_GLOBAL)   # share DuckDB symbols with the extension

con = duckdb.connect("trips.duckdb", config={
    "allow_unsigned_extensions": "true",                 # locally built extension is unsigned
    "allow_extensions_metadata_mismatch": "true",        # Sirius's DuckDB fork reports v0.0.1
})
con.execute(f"LOAD '{EXT}'")                             # GPU execution is on from here
```

- **Supported queries run on the GPU automatically,** with no rewrites needed.
- **To switch engines,** use `SET gpu_execution = false` for CPU and `SET gpu_execution = true` for GPU.
- **Unsupported operators** (such as window functions or nested types) silently fall back to CPU.

## 5. Load data

Download a sample dataset (NYC Yellow Taxi, about 48 MB and 3 million rows):

```python
!wget -P ~/sirius/data https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet
```

Query Parquet directly:

```python
con.sql("""
    SELECT tpep_pickup_datetime, passenger_count, trip_distance, total_amount
    FROM './data/yellow_tripdata_2024-01.parquet' LIMIT 5
""").show()
```

### Scale up and pin to GPU memory

Small queries won't show a GPU speedup, because fixed GPU overhead dominates. This step creates about 59 million rows by repeating the data 20 times, then pins the table in GPU memory so that queries skip loading it each time:

```python
con.execute("""
    CREATE TABLE IF NOT EXISTS trips AS
    SELECT passenger_count, trip_distance, payment_type,
           tip_amount, PULocationID, total_amount
    FROM './data/yellow_tripdata_2024-01.parquet', range(20)
""")
con.execute("CHECKPOINT")                                         # required before pinning
con.execute("CALL pin_table(format='duckdb', name='trips', tier='gpu')")
```

- **Pinning needs a file-backed database.** Connect with `duckdb.connect("trips.duckdb")`, not in-memory, because pinning requires checkpointed data.
- **Parquet files can be pinned directly:** `CALL pin_table('/path/file.parquet', name='t', tier='gpu')`.
- **To change the data size,** delete `trips.duckdb` before changing `range(20)`.

## 6. Benchmark CPU vs. GPU

```python
import time

queries = {
    "Filter + average": """
        SELECT payment_type, AVG(tip_amount)
        FROM trips WHERE trip_distance > 5 GROUP BY payment_type""",
    "Many groups": """
        SELECT PULocationID, passenger_count, payment_type, ROUND(trip_distance) AS miles,
               COUNT(*) AS n, AVG(total_amount) AS avg_total
        FROM trips GROUP BY PULocationID, passenger_count, payment_type, miles
        ORDER BY n DESC LIMIT 10""",
    "Join": """
        SELECT t.PULocationID, COUNT(*) AS above_avg_trips
        FROM trips t
        JOIN (SELECT PULocationID, AVG(total_amount) AS avg_total
              FROM trips GROUP BY PULocationID) z
          ON t.PULocationID = z.PULocationID
        WHERE t.total_amount > z.avg_total
        GROUP BY t.PULocationID ORDER BY above_avg_trips DESC LIMIT 10""",
}

def run(sql):
    con.execute(sql).fetchall()                 # warm-up
    times = []
    for _ in range(3):
        start = time.time()
        con.execute(sql).fetchall()
        times.append(time.time() - start)
    return min(times)

for name, sql in queries.items():
    con.execute("SET gpu_execution = false"); cpu = run(sql)
    con.execute("SET gpu_execution = true");  gpu = run(sql)
    print(f"{name}: CPU {cpu:.3f}s | GPU {gpu:.3f}s | {cpu/gpu:.1f}x faster")
```

## 7. Confirm a query ran on the GPU

Because unsupported queries fall back to CPU silently, check the logs:

```python
con.execute("CALL enable_logging(level='info', storage='memory')")
# ... run your query ...
print(con.sql("""
    SELECT count(*) FROM duckdb_logs
    WHERE message LIKE '%Transparent GPU execution: query completed%'
""").fetchone())
```

A count of 1 or more means the query ran on the GPU.

## References

- [Sirius on GitHub](https://github.com/sirius-db/sirius)
- [Sirius configuration reference](https://github.com/sirius-db/sirius/blob/dev/docs/super-sirius/configuration.md)
- [NYC TLC trip record data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
