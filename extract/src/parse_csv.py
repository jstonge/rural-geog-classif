import pandas as pd

def main():
    d=pd.read_csv("Coded Rural Geog All 1986-2025 WoS List 4-7-2026(savedrecs).csv")
    # getting rid of the abstracts
    d=d[~d.Abstract.isna()]
    # pre 2021 (inclusively)
    d[d["Pub Year"] <= 2021].doi.to_csv("doi_pre_2021.csv", index=False)
    # post 2021
    d[d["Pub Year"] > 2021].doi.to_csv("doi_post_2021.csv", index=False)