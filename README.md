aircraft-state-estimation/

data/

├── raw/

└── processed/

notebooks/

├── 01_explore_opensky.ipynb

└── 02_trajectory_analysis.ipynb

src/

├── data/

│   ├── fetch.py

│   ├── preprocess.py

│   └── trajectories.py

├── models/

│   ├── dead_reckoning.py

│   ├── ekf.py

│   └── rnn.py

└── simulation/

    └── telemetry_delay.py

tests/

requirements.txt

## Data normalization

OpenSky public archives and future Trino query results are normalized into one
canonical state-vector schema before trajectory processing. See
[the normalization documentation](docs/data-normalization.md) for the schema,
edge-case policy, quality flags, and command-line usage.

The complete trajectory, windowing, split, dead-reckoning, and evaluation
workflow is documented in
[Data pipeline and baseline construction](docs/data-pipeline-and-baseline.md).

README.md
