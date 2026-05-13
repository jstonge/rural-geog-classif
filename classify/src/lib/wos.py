"""WoS CSV loader."""
from pathlib import Path

import pandas as pd

WOS_CSV = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/extract/input/"
               "Full Dataset Rur Geog WoS 1986-2025 4-28-2026.csv")


def load_wos() -> pd.DataFrame:
    """Return DataFrame with [doi, title, abstract] for every paper with a non-empty abstract."""
    df = pd.read_csv(WOS_CSV, encoding="latin").rename(
        columns={"Abstract": "abstract", "Article Title": "title", "DOI": "doi"}
    )
    return (
        df[df["abstract"].notna() & df["abstract"].astype(str).str.strip().astype(bool)]
        [["doi", "title", "abstract"]]
        .copy()
        .reset_index(drop=True)
    )
