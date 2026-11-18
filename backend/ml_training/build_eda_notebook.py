"""Build and execute ml_training/eda.ipynb (charts for the EDA in ml_training/eda.py).

Run from backend/ with the notebook extras installed:
    pip install -r requirements-notebook.txt
    python -m ml_training.build_eda_notebook
The notebook reuses eda.analyse(), so its numbers always match reports/eda_report.md.
"""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbclient import NotebookClient

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent

CELLS: list[tuple[str, str]] = [
    ("md", "# EDA: Final_Marks_Data.csv\n\nCharts for the analysis in `ml_training/eda.py`. "
           "Tables and conclusions are in `reports/eda_report.md`. Provenance of the dataset is unknown."),
    ("code", "import sys, pathlib\nsys.path.insert(0, str(pathlib.Path.cwd()))  # backend/\n"
             "import matplotlib.pyplot as plt\nimport pandas as pd\n"
             "from app.ml.features import ATTENDANCE, INTERNAL1, INTERNAL2, ASSIGNMENT, TARGET, FEATURE_LABELS\n"
             "from ml_training.dataset import load_raw, prepare\nfrom ml_training.eda import analyse\n"
             "raw = load_raw(); data = prepare(raw); summary = analyse()\n"
             "FEATURES = [ATTENDANCE, INTERNAL1, INTERNAL2, ASSIGNMENT]\nraw.head()"),
    ("md", "## Data quality"),
    ("code", "pd.Series(summary['quality']).to_frame('value')"),
    ("md", "## Feature and target distributions (percent scale)"),
    ("code", "fig, axes = plt.subplots(1, 5, figsize=(18, 3.2))\n"
             "for ax, col in zip(axes, FEATURES + [TARGET]):\n"
             "    ax.hist(data[col], bins=25, color='#4C78A8')\n"
             "    ax.set_title(FEATURE_LABELS.get(col, 'Final exam'))\n"
             "plt.tight_layout(); plt.show()"),
    ("md", "## Each feature against the final exam mark"),
    ("code", "fig, axes = plt.subplots(1, 4, figsize=(18, 3.6), sharey=True)\n"
             "for ax, col in zip(axes, FEATURES):\n"
             "    ax.scatter(data[col], data[TARGET], s=6, alpha=0.35, color='#4C78A8')\n"
             "    ax.set_xlabel(FEATURE_LABELS[col] + ' (%)')\n"
             "axes[0].set_ylabel('Final exam (%)'); plt.tight_layout(); plt.show()"),
    ("md", "## Correlations"),
    ("code", "corr = data[FEATURES + [TARGET]].corr()\n"
             "fig, ax = plt.subplots(figsize=(5.5, 4.5))\n"
             "im = ax.imshow(corr, vmin=-1, vmax=1, cmap='RdBu_r')\n"
             "labels = [FEATURE_LABELS.get(c, 'Final') for c in corr.columns]\n"
             "ax.set_xticks(range(len(labels)), labels, rotation=45, ha='right'); ax.set_yticks(range(len(labels)), labels)\n"
             "for i in range(len(labels)):\n"
             "    for j in range(len(labels)):\n"
             "        ax.text(j, i, f'{corr.iloc[i, j]:.2f}', ha='center', va='center', fontsize=8)\n"
             "fig.colorbar(im); plt.tight_layout(); plt.show()"),
    ("md", "## Mean final mark by attendance band"),
    ("code", "bands = pd.DataFrame(summary['target_mean_by_attendance_band']).T\n"
             "ax = bands['mean_final'].plot.bar(color='#4C78A8', figsize=(7, 3.2), rot=0)\n"
             "ax.set_ylabel('Mean final exam (%)'); plt.tight_layout(); plt.show(); bands"),
    ("md", "Associations only: these charts do not show that attendance or marks *cause* final results."),
]


def main() -> None:
    notebook = nbformat.v4.new_notebook()
    notebook.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    notebook.cells = [
        nbformat.v4.new_markdown_cell(src) if kind == "md" else nbformat.v4.new_code_cell(src)
        for kind, src in CELLS
    ]
    NotebookClient(notebook, timeout=120, kernel_name="python3", resources={"metadata": {"path": str(BACKEND)}}).execute()
    out = HERE / "eda.ipynb"
    nbformat.write(notebook, out)
    print(f"Wrote and executed {out}")


if __name__ == "__main__":
    main()
