from google import genai

client = genai.Client()  

response = client.models.generate_content(
    model="gemini-3-flash-preview", 
    contents="Balas dengan satu kalimat: apakah koneksi ini berhasil?"
)

print(response.text)