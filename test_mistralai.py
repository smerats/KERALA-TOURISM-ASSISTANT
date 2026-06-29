from mistralai.client import Mistral

api_key = "wb87pSIrDSjKeGZCnZ48ba7D0USHSPHZ"

client = Mistral(api_key= "wb87pSIrDSjKeGZCnZ48ba7D0USHSPHZ")

response = client.chat.complete(
    model="mistral-small-latest",
    messages=[
        {
            "role": "user",
            "content": "Tell me about Kerala tourism"
        }
    ]
)

print(response.choices[0].message.content)




