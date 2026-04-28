"""Embed methodology abstracts using SPECTER2 with classification adapter."""

import argparse
import csv
import json
import sys
from pathlib import Path

from run_utils import init_run, finish_run, add_run_args, params_from_args

import numpy as np
import torch
from transformers import AutoTokenizer
from adapters import AutoAdapterModel


def load_model(device: str = "cpu"):
    """Load SPECTER2 base model with classification adapter."""
    tokenizer = AutoTokenizer.from_pretrained("allenai/specter2_base")
    model = AutoAdapterModel.from_pretrained("allenai/specter2_base")
    model.load_adapter(
        "allenai/specter2_classification", source="hf",
        load_as="classification", set_active=True,
    )
    model.to(device)
    model.eval()
    return tokenizer, model


def embed_texts(tokenizer, model, texts: list[str], batch_size: int = 16, device: str = "cpu"):
    """Embed a list of texts, returning (n_texts, hidden_dim) array."""
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        inputs = tokenizer(
            batch, padding=True, truncation=True,
            return_tensors="pt", return_token_type_ids=False, max_length=512,
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            output = model(**inputs)
        # CLS token embedding
        embeddings = output.last_hidden_state[:, 0, :].cpu().numpy()
        all_embeddings.append(embeddings)
    return np.concatenate(all_embeddings, axis=0)


def main():
    parser = argparse.ArgumentParser(description="Embed methodology abstracts with SPECTER2")
    parser.add_argument(
        "summaries",
        type=Path,
        help="Path to JSON file mapping DOI -> methodology abstract",
    )
    parser.add_argument(
        "titles_csv",
        type=Path,
        help="CSV with 'doi' and 'article title' columns",
    )
    parser.add_argument(
        "-o", "--output", type=Path,
        default=Path(__file__).resolve().parent.parent / "output",
        help="Output directory (default: transform/output)",
    )
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    add_run_args(parser)
    args = parser.parse_args()

    run_dir = init_run("embed.py", params_from_args(args), run_id=args.run_id)

    with open(args.summaries) as f:
        summaries: dict[str, str] = json.load(f)

    # Build DOI -> title lookup from CSV
    # CSV DOIs use "/" but summary keys use "_", so normalize
    doi_to_title = {}
    with open(args.titles_csv) as f:
        for row in csv.DictReader(f):
            key = row["doi"].replace("/", "_")
            doi_to_title[key] = row["article title"]

    print(f"Loaded {len(summaries)} abstracts, {len(doi_to_title)} titles")

    device = args.device
    if device == "cuda" and not torch.cuda.is_available():
        print("CUDA not available, falling back to CPU")
        device = "cpu"

    print("Loading SPECTER2 + classification adapter...")
    tokenizer, model = load_model(device)

    dois = list(summaries.keys())
    # SPECTER2 expects: title [SEP] abstract
    texts = [
        doi_to_title.get(doi, "") + tokenizer.sep_token + summaries[doi]
        for doi in dois
    ]

    matched = sum(1 for doi in dois if doi in doi_to_title)
    print(f"Matched {matched}/{len(dois)} titles")
    print(f"Embedding {len(texts)} abstracts (batch_size={args.batch_size})...")
    embeddings = embed_texts(tokenizer, model, texts, args.batch_size, device)
    print(f"Embeddings shape: {embeddings.shape}")

    np.save(run_dir / "embeddings.npy", embeddings)
    with open(run_dir / "dois.json", "w") as f:
        json.dump(dois, f)

    finish_run(run_dir, outputs=["embeddings.npy", "dois.json"])


if __name__ == "__main__":
    main()
