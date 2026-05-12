"""Realign Label Studio annotations (project 100) to WoS metadata.

LS task DOIs are unreliable, but Article Title + Authors are. The WoS CSV
has correctly aligned DOI ↔ metadata, so we join on (title, authors) and
attach the WoS DOI to each annotation.
"""
import os
from pathlib import Path

import httpx
import pandas as pd
from dotenv import load_dotenv
from label_studio_sdk import LabelStudio

CSV_PATH = "/gpfs1/home/j/s/jstonge1/rural-geog-classif/extract/input/Full Dataset Rur Geog WoS 1986-2025 4-28-2026.csv"
PROJECT_ID = 100
OUTPUT_PATH = Path("/gpfs1/home/j/s/jstonge1/rural-geog-classif/transform/output/annotations.parquet")


def norm(s):
    return str(s).strip().lower() if pd.notna(s) else ""


def main():
    load_dotenv()

    df = pd.read_csv(
        CSV_PATH,
        usecols=["Article Title", "Authors", "Abstract", "DOI", "Pub Year"],
        encoding="latin"
    ).rename(columns={
        "Article Title": "title",
        "Authors": "authors",
        "Abstract": "abstract",
        "DOI": "doi",
        "Pub Year": "year",
    })
    df["_key"] = df["title"].map(norm) + "||" + df["authors"].map(norm)
    print(f"WoS: {len(df)} rows")

    dup = df["_key"].duplicated(keep=False).sum()
    if dup:
        print(f"  WARNING: {dup} duplicate (title, authors) keys in WoS")

    client = LabelStudio(
        base_url=os.getenv("LABEL_STUDIO_URL"),
        api_key=os.getenv("LABEL_STUDIO_API_KEY"),
        httpx_client=httpx.Client(verify=False),
    )
    tasks = list(client.tasks.list(project=PROJECT_ID))
    print(f"Label Studio: {len(tasks)} tasks in project {PROJECT_ID}")

    rows = []
    for t in tasks:
        if not t.annotations:
            continue
        # Union choices across ALL annotators, per control
        controls = {}  # name -> set of choices
        for ann in t.annotations:
            for r in ann["result"]:
                if r.get("type") == "choices":
                    controls.setdefault(r["from_name"], set()).update(r["value"]["choices"])
        if not controls:
            continue
        rows.append({
            "task_id": t.id,
            "n_annotations": len(t.annotations),
            "ls_title": t.data.get("Article Title"),
            "ls_authors": t.data.get("Authors"),
            "ls_doi": t.data.get("DOI"),
            **{f"label_{k}": sorted(v) for k, v in controls.items()},
        })

    ann = pd.DataFrame(rows)
    ann["_key"] = ann["ls_title"].map(norm) + "||" + ann["ls_authors"].map(norm)
    multi = (ann["n_annotations"] > 1).sum()
    print(f"Annotated tasks: {len(ann)}  ({multi} had >1 annotator — choices unioned)")

    merged = ann.merge(df, on="_key", how="left", indicator=True)
    matched = merged[merged["_merge"] == "both"].drop(columns=["_merge", "_key"])
    unmatched = merged[merged["_merge"] == "left_only"]
    print(f"Matched on (title, authors): {len(matched)}/{len(ann)}")

    if len(unmatched):
        print(f"\nUnmatched ({len(unmatched)}) — first 5:")
        for _, r in unmatched.head(5).iterrows():
            print(f"  - {r['ls_title']!r}")
            print(f"    LS authors: {r['ls_authors']!r}")
            print(f"    LS DOI: {r['ls_doi']}")

    if len(matched):
        doi_drift = (matched["ls_doi"].fillna("") != matched["doi"].fillna("")).sum()
        print(f"\nDOI drift among matched: {doi_drift}/{len(matched)} have ls_doi != WoS doi")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    matched.to_parquet(OUTPUT_PATH, index=False)
    print(f"\nWrote {len(matched)} rows → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
