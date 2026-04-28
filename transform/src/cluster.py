"""Cluster SPECTER2 embeddings using EVoC and produce frontend-ready JSON."""

import argparse
import csv
import json
from pathlib import Path

from run_utils import init_run, finish_run, add_run_args, params_from_args

import numpy as np
import evoc
from sklearn.decomposition import PCA


def main():
    parser = argparse.ArgumentParser(description="Cluster embeddings with EVoC")
    parser.add_argument(
        "embeddings",
        type=Path,
        help="Path to embeddings.npy from embed.py",
    )
    parser.add_argument(
        "dois",
        type=Path,
        help="Path to dois.json from embed.py",
    )
    parser.add_argument(
        "titles_csv",
        type=Path,
        help="CSV with 'doi' and 'article title' columns",
    )
    parser.add_argument(
        "wos_csv",
        type=Path,
        help="Full Web of Science CSV with metadata",
    )
    parser.add_argument(
        "summaries",
        type=Path,
        help="Path to JSON file mapping DOI -> methodology abstract",
    )
    parser.add_argument(
        "-o", "--output", type=Path,
        default=Path(__file__).resolve().parent.parent / "output",
        help="Output directory (default: transform/output)",
    )
    add_run_args(parser)
    args = parser.parse_args()

    run_dir = init_run("cluster.py", params_from_args(args), run_id=args.run_id)

    embeddings = np.load(args.embeddings)
    with open(args.dois) as f:
        dois = json.load(f)
    with open(args.summaries) as f:
        summaries = json.load(f)

    doi_to_title = {}
    with open(args.titles_csv) as f:
        for row in csv.DictReader(f):
            key = row["doi"].replace("/", "_")
            doi_to_title[key] = row["article title"]

    # Load full WoS metadata
    doi_to_meta = {}
    with open(args.wos_csv, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            doi = row.get("DOI", "").strip()
            if doi:
                key = doi.replace("/", "_")
                doi_to_meta[key] = {
                    "authors": row.get("Authors", ""),
                    "pub_year": row.get("Pub Year", ""),
                    "source": row.get("Source Title", ""),
                    "keywords": row.get("Author Keywords", ""),
                }

    print(f"Loaded {embeddings.shape[0]} embeddings of dim {embeddings.shape[1]}")

    clusterer = evoc.EVoC()
    labels = clusterer.fit_predict(embeddings)

    n_clusters = len(set(labels) - {-1})
    n_noise = (labels == -1).sum()
    print(f"Found {n_clusters} clusters, {n_noise} noise points")

    # Project EVoC's internal node embedding down to 2D for visualization
    node_emb = clusterer.embedding_
    print(f"Node embedding shape: {node_emb.shape}")
    if node_emb.shape[1] > 2:
        coords_2d = PCA(n_components=2).fit_transform(node_emb)
    else:
        coords_2d = node_emb[:, :2]

    # Build frontend-ready JSON
    points = []
    for i, doi in enumerate(dois):
        meta = doi_to_meta.get(doi, {})
        points.append({
            "doi": doi,
            "title": doi_to_title.get(doi, ""),
            "abstract": summaries.get(doi, ""),
            "authors": meta.get("authors", ""),
            "pub_year": meta.get("pub_year", ""),
            "source": meta.get("source", ""),
            "keywords": meta.get("keywords", ""),
            "cluster": int(labels[i]),
            "x": float(coords_2d[i, 0]),
            "y": float(coords_2d[i, 1]),
        })

    with open(run_dir / "viz.json", "w") as f:
        json.dump(points, f)

    finish_run(run_dir, outputs=["viz.json"])


if __name__ == "__main__":
    main()
