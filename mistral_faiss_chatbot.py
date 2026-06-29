import pandas as pd
import faiss
from sentence_transformers import SentenceTransformer
from mistralai.client import Mistral

# Mistral API Key
api_key = "wb87pSIrDSjKeGZCnZ48ba7D0USHSPHZ"

client = Mistral(api_key="wb87pSIrDSjKeGZCnZ48ba7D0USHSPHZ")

# Load dataset
df = pd.read_csv("kerala_tourism_chatbot_dataset.csv.xls")

# Load FAISS index
index = faiss.read_index("tourism_index.faiss")

# Load embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

while True:

    query = input("\nAsk a tourism question: ")

    if query.lower() == "exit":
        break

    # Convert question to embedding
    query_embedding = model.encode([query])

    # Search FAISS
    distances, indices = index.search(query_embedding, 3)

    context = ""

    for idx in indices[0]:
        context += (
            str(df.iloc[idx]["bot_response"])
            + "\n"
        )

    prompt = f"""
You are a Kerala tourism assistant.

Context:
{context}

User Question:
{query}

Answer only using the context above.
"""

    response = client.chat.complete(
        model="mistral-small-latest",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    print("\nBot:")
    print(response.choices[0].message.content)