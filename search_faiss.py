import pandas as pd
import faiss
from sentence_transformers import SentenceTransformer

# Load CSV
df = pd.read_csv("kerala_tourism_chatbot_dataset.csv.xls")

# Load FAISS index
index = faiss.read_index("tourism_index.faiss")

# Load embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

while True:
    query = input("Ask a tourism question: ")

    if query.lower() == "exit":
        break

    query_embedding = model.encode([query])

    distances, indices = index.search(query_embedding, 1)

    result = df.iloc[indices[0][0]]

    print("\nAnswer:")
    print(result["bot_response"])