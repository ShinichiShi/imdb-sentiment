"""Build the movie library + streaming catalogue from the poster archive.

Poster files are named <imdb_score>_<imdb_numeric_id>.jpg. Titles/years/genres/votes
come from IMDb's public datasets (title.basics.tsv.gz, title.ratings.tsv.gz).

  python scripts/build_library.py archive/poster_downloads <dir with the two .tsv.gz>

Outputs:
  frontend/static/library.json   every poster (the Library tab)
  backend/common/library.json    same data, used by the API
  backend/common/catalog.json    the most-voted titles that receive the review stream
"""
import json
import os
import sys

import pandas as pd

posters_dir, imdb_dir = sys.argv[1], sys.argv[2]
STREAM_TITLES = 24

rows = []
for fn in os.listdir(posters_dir):
    if fn.endswith(".jpg"):
        score, imdb = fn[:-4].split("_")
        rows.append({"file": fn, "score": float(score), "id": "tt%07d" % int(imdb)})
lib = pd.DataFrame(rows)

basics = pd.read_csv(os.path.join(imdb_dir, "title.basics.tsv.gz"), sep="\t", na_values="\\N",
                     usecols=["tconst", "titleType", "primaryTitle", "startYear", "runtimeMinutes", "genres"])
basics = basics[basics.tconst.isin(lib.id)]
ratings = pd.read_csv(os.path.join(imdb_dir, "title.ratings.tsv.gz"), sep="\t")
df = (lib.merge(basics, left_on="id", right_on="tconst", how="left")
         .merge(ratings, left_on="id", right_on="tconst", how="left"))
df = df.dropna(subset=["primaryTitle"]).sort_values("numVotes", ascending=False)
print(f"{len(lib)} posters, {len(df)} resolved to titles")

def entry(r):
    return {"id": r.id, "file": r.file, "score": r.score, "title": r.primaryTitle,
            "year": None if pd.isna(r.startYear) else int(r.startYear),
            "genres": [] if pd.isna(r.genres) else r.genres.split(","),
            "runtime": None if pd.isna(r.runtimeMinutes) else int(r.runtimeMinutes),
            "votes": 0 if pd.isna(r.numVotes) else int(r.numVotes)}

library = [entry(r) for r in df.itertuples()]
with open("frontend/static/library.json", "w") as f:
    json.dump(library, f, separators=(",", ":"))

with open("backend/common/library.json", "w") as f:   # server-side copy (for user-written reviews of any title)
    json.dump(library, f, separators=(",", ":"))

# Streaming catalogue: audience positivity follows the IMDb score of the title.
cat = []
# 4 most-voted titles from each IMDb-score band, so live averages spread out visibly.
bands = [(0, 4.5), (4.5, 5.5), (5.5, 6.5), (6.5, 7.5), (7.5, 8.5), (8.5, 10)]
picked = []
for lo, hi in bands:
    picked += [m for m in library if lo <= m["score"] < hi][:STREAM_TITLES // len(bands)]
for m in picked:
    cat.append({**m, "positivity": round(min(0.95, max(0.08, (m["score"] - 3) / 6.5)), 2),
                "buzz": 1 + int(m["votes"] ** 0.5 // 400)})
with open("backend/common/catalog.json", "w") as f:
    json.dump(cat, f, indent=1)
print("stream titles:", ", ".join(f'{m["title"]} ({m["score"]})' for m in cat))
