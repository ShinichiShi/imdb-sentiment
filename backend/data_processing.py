import io
import os
import pandas as pd
import re
import joblib
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy import sparse
from tqdm import tqdm

# Enable tqdm for pandas
tqdm.pandas()

def load_data(file_path):
    """
    Load data from CSV file (local path, or from HDFS when STORAGE=hdfs).
    """
    print("Loading data...")
    if os.environ.get("STORAGE") == "hdfs":
        from common import settings, storage
        print("Reading dataset from HDFS...")
        df = pd.read_csv(io.BytesIO(storage.get_storage().read(settings.HDFS_BASE + "/dataset/IMDB Dataset.csv")))
    else:
        df = pd.read_csv(file_path)
    print(f"Data loaded: {df.shape[0]} rows, {df.shape[1]} columns")
    return df

def clean_text(text):
    """
    Clean text: remove URLs, special characters, and convert to lowercase.
    """
    text = re.sub(r"http\S+|www\S+|https\S+", '', text)  # Remove links
    text = re.sub(r'[^A-Za-z ]+', '', text)  # Remove special characters
    text = text.lower()  # Convert to lowercase
    return text

def preprocess_data(df):
    """
    Clean text data with progress bar.
    """
    print("Cleaning and preprocessing data...")
    df['cleaned_review'] = df['review'].progress_apply(clean_text)
    print("Data preprocessing complete!")
    return df

def tfidf_with_progress(texts, max_features=5000):
    """
    Apply TF-IDF vectorization with progress bar.
    """
    print("Applying TF-IDF vectorization...")
    vectorizer = TfidfVectorizer(max_features=max_features)
    
    # Добавляем tqdm для процесса под капотом
    with tqdm(total=len(texts), desc="Vectorizing TF-IDF") as pbar:
        X = vectorizer.fit_transform(tqdm(texts, total=len(texts), desc="Processing Texts"))
        pbar.update(len(texts))
    
    return X, vectorizer

def vectorize_and_save(df, output_path="data/processed/"):
    """
    Vectorize with TF-IDF, split, and save data.
    """
    X, vectorizer = tfidf_with_progress(df['cleaned_review'])
    
    # Convert sentiment labels to binary
    y = df['sentiment'].apply(lambda x: 1 if x == "positive" else 0)

    print("Splitting and saving data...")
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Save sparse matrices and labels
    sparse.save_npz(f"{output_path}X_train_tfidf.npz", X_train)
    sparse.save_npz(f"{output_path}X_test_tfidf.npz", X_test)
    pd.DataFrame(y_train).to_csv(f"{output_path}y_train.csv", index=False)
    pd.DataFrame(y_test).to_csv(f"{output_path}y_test.csv", index=False)

    # Save the TF-IDF vectorizer
    joblib.dump(vectorizer, f"{output_path}tfidf_vectorizer.pkl")
    print("TF-IDF data and vectorizer successfully saved!")

if __name__ == "__main__":
    # Path to raw data
    input_file = "data/raw/IMDB Dataset.csv"

    # Load, preprocess, and vectorize data
    df = load_data(input_file)
    df = preprocess_data(df)
    vectorize_and_save(df)
