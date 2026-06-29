import pandas as pd
import faiss
from sentence_transformers import SentenceTransformer

# Load CSV
df = pd.read_csv("C:\\Users\\SMERA T S\\OneDrive\\Desktop\\Python_Practice\\kerala_tourism_chatbot_dataset.csv.xls")

print("Dataset loaded")
print("Rows:", len(df))

# Load embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

# Create embeddings from user queries
texts = df["user_query"].astype(str).tolist()

print("Creating embeddings...")

embeddings = model.encode(texts)

print("Embeddings created")

# Create FAISS index
dimension = embeddings.shape[1]

index = faiss.IndexFlatL2(dimension)

# Store vectors in FAISS
index.add(embeddings)

print("Vectors stored:", index.ntotal)

# Save FAISS database
faiss.write_index(index, "tourism_index.faiss")

print("FAISS database saved successfully!")