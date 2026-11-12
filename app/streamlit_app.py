"""Local demo: describe your practice, get ranked opportunities.

Run from the project folder:
    .venv\Scripts\streamlit.exe run app\streamlit_app.py
"""
import sys
from datetime import date
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from models.matching.bm25 import BM25Ranker
from models.matching.data import load_listings
from models.matching.embed import EmbeddingRanker
from models.matching.filters import apply_filters
from models.matching.profile import ALL_TYPES, ArtistProfile

st.set_page_config(page_title="Artist Opportunity Finder", layout="centered")


@st.cache_resource(show_spinner="Loading listings and building indexes...")
def get_listings_and_bm25():
    listings = load_listings()
    return listings, BM25Ranker(listings)


@st.cache_resource(show_spinner="Encoding listings (first run only)...")
def get_embedder():
    listings = load_listings()
    return EmbeddingRanker(listings)


listings, bm25 = get_listings_and_bm25()

st.title("Artist Opportunity Finder")
st.caption("Grants, open calls and residencies matched to your practice.")

about = st.text_area(
    "Describe your practice", height=150,
    placeholder="Emerging sculptor working with reclaimed wood and public installation...",
)

with st.sidebar:
    st.header("Filters")
    types = st.multiselect("Opportunity type", ALL_TYPES, default=ALL_TYPES)
    max_fee = st.number_input("Max entry fee ($)", 0, 500, 50, step=5)
    as_of = st.date_input("Show deadlines on/after", value=date.today())
    method = st.radio("Ranker", ["Embeddings", "BM25"])
    k = st.slider("Results", 3, 20, 10)

if st.button("Find opportunities", type="primary"):
    if not about.strip():
        st.warning("Describe your practice first.")
        st.stop()
    profile = ArtistProfile(profile_id="demo", about=about,
                            wanted_types=tuple(types), max_fee=max_fee)
    pool = apply_filters(listings, profile, as_of)
    st.caption(f"{len(pool)} of {len(listings)} listings passed the filters")
    if not pool:
        st.info("Nothing passed the filters. Try an earlier date or a higher fee cap.")
        st.stop()
    ranker = get_embedder() if method == "Embeddings" else bm25
    for l, score in ranker.rank(profile, candidates=pool, k=k):
        with st.container(border=True):
            st.subheader(l["title"])
            desc = l.get("description") or ""
            st.write(desc[:400] + ("..." if len(desc) > 400 else ""))
            fee = l.get("fee_min")
            st.caption(
                f'{l.get("type")} · deadline {l.get("deadline") or ("rolling" if l.get("is_rolling") else "n/a")}'
                f' · fee {"free/unknown" if fee in (None, 0) else f"${fee:g}"} · score {score:.2f}'
            )
            if l.get("website"):
                st.link_button("Open listing", l["website"])
