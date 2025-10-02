# test_direct_auth.py
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

print(f"Testing with:")
print(f"URL: {url}")
print(f"Key: {key[:50]}..." if key else "No key found")

try:
    client = create_client(url, key)
    print("✅ Client created successfully")
    
    # Test auth directly
    response = client.auth.sign_in_with_password({
        "email": "biriyani@gmail.com",
        "password": "A4alen123"
    })
    print("✅ Authentication successful!")
    print(f"User ID: {response.user.id}")
    
except Exception as e:
    print(f"❌ Error: {e}")