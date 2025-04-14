# =======================================
# National Parks Query Matching Script
# =======================================
# This script takes a user input query (e.g., 'hot springs') and compares it to
# both Google Reviews and Wikipedia article content for US national parks to:
# - Recommend parks based on textual similarity
# - Return top relevant reviews and Wikipedia sentences
# =======================================

import os
import pandas as pd
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ------------------------------
# Text cleaning helper function
# ------------------------------
def clean_text(text):
    """Lowercase and remove URLs, non-letter characters, and extra spaces."""
    if pd.isna(text):
        return ""
    text = text.lower()
    text = re.sub(r"http\S+|www\S+|https\S+", "", text)
    text = re.sub(r"[^a-z\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

# ---------------------------------------------------
# Load and clean Google Review CSVs (1 per park code)
# ---------------------------------------------------
def load_review_texts(folder):
    """Aggregate reviews and metadata from all CSVs in folder."""
    park_reviews = {}
    code_to_name = {}
    raw_reviews = {}
    for file in os.listdir(folder):
        if file.endswith(".csv"):
            code = file.replace(".csv", "")
            df = pd.read_csv(os.path.join(folder, file))
            df["cleaned"] = df["review_text"].apply(clean_text)
            text = " ".join(df["cleaned"].dropna().tolist())
            name = df["place_name"].iloc[0]
            park_reviews[code] = text
            code_to_name[code] = name
            raw_reviews[code] = df
    return park_reviews, code_to_name, raw_reviews

# -------------------------------------------------
# Load and clean Wikipedia article text files by ID
# -------------------------------------------------
def load_wikipedia_texts(folder):
    """Load cleaned Wikipedia articles by park code from .txt files."""
    park_articles = {}
    for file in os.listdir(folder):
        if file.endswith(".txt"):
            code = file.replace(".txt", "")
            with open(os.path.join(folder, file), "r", encoding="utf-8") as f:
                text = f.read()
                park_articles[code] = clean_text(text)
    return park_articles

# --------------------------------------------
# Compute similarity between query and content
# --------------------------------------------
def compute_query_similarity(user_query, park_dict):
    """
    Return a DataFrame of similarity scores between query and full park texts.
    Uses TF-IDF vectorizer with ngram_range=(1, 2) to capture both individual words
    and short phrases (bigrams) for improved context-aware matching.
    """
    results = []
    query_cleaned = clean_text(user_query)
    for code, text in park_dict.items():
        # Use both unigrams and bigrams (phrases) to improve contextual match
        tfidf = TfidfVectorizer(stop_words='english', ngram_range=(1, 2))
        vectors = tfidf.fit_transform([text, query_cleaned])
        sim = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
        results.append({"Code": code, "similarity_raw": sim})
    df = pd.DataFrame(results)
    # Scale Similarity score from 0-1
    df['Similarity'] = (df['similarity_raw'] - df['similarity_raw'].min()) / (df['similarity_raw'].max() - df['similarity_raw'].min())
    df.drop('similarity_raw', axis=1, inplace=True)
    df.sort_values("Similarity", ascending=False, inplace=True)
    return df

# -------------------------------------------------------------------------
# For each top park from reviews, return top 5 most similar individual reviews
# -------------------------------------------------------------------------
def extract_top_reviews(user_query, top_parks, raw_reviews, code_to_name):
    rows = []
    query_cleaned = clean_text(user_query)
    tfidf = TfidfVectorizer(stop_words='english', ngram_range=(1, 2))  # n-gram enhancement
    for i, row in top_parks.iterrows():
        code = row['code']
        name = row['name']
        df = raw_reviews[code].dropna(subset=["review_text"])
        df["cleaned"] = df["review_text"].apply(clean_text)
        if df.empty:
            continue
        tfidf_matrix = tfidf.fit_transform(df["cleaned"].tolist() + [query_cleaned])
        query_vec = tfidf_matrix[-1]
        review_vecs = tfidf_matrix[:-1]
        sim_scores = cosine_similarity(query_vec, review_vecs).flatten()
        top_idxs = sim_scores.argsort()[-5:][::-1]
        for idx in top_idxs:
            rows.append({
                "code": code,
                "name": name,
                "review": df.iloc[idx]["review_text"],
                "similarity": sim_scores[idx]
            })
    return pd.DataFrame(rows)

# -----------------------------------------------------------------------------------
# For each top park from Wikipedia, return up to 5 relevant sentences above threshold
# -----------------------------------------------------------------------------------
def extract_top_wiki_sentences(user_query, top_wiki_df, wiki_folder, code_to_name, similarity_threshold=0.2):
    rows = []
    query_cleaned = clean_text(user_query)
    tfidf = TfidfVectorizer(stop_words='english', ngram_range=(1, 2))  # n-gram enhancement
    for _, row in top_wiki_df.iterrows():
        code = row['code']
        name = row['name']
        file_path = os.path.join(wiki_folder, f"{code}.txt")
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()

        # Split into sentences (min 5 words), deduplicate
        sentences = [s.strip() for s in re.split(r'[.!?]', text) if len(s.strip().split()) >= 5]
        seen = set()
        unique_sentences = []
        for s in sentences:
            if s not in seen:
                seen.add(s)
                unique_sentences.append(s)

        if not unique_sentences:
            continue

        # Score each sentence vs. query using unigram + bigram TF-IDF features
        cleaned_sentences = [clean_text(s) for s in unique_sentences]
        tfidf_matrix = tfidf.fit_transform(cleaned_sentences + [query_cleaned])
        query_vec = tfidf_matrix[-1]
        sentence_vecs = tfidf_matrix[:-1]
        sim_scores = cosine_similarity(query_vec, sentence_vecs).flatten()
        top_idxs = sim_scores.argsort()[::-1]

        row_count = 0
        for idx in top_idxs:
            if sim_scores[idx] >= similarity_threshold:
                rows.append({
                    "code": code,
                    "name": name,
                    "sentence": unique_sentences[idx],
                    "similarity": sim_scores[idx]
                })
                row_count += 1
            if row_count >= 5:
                break

    return pd.DataFrame(rows)