import asyncio
import os
from uuid import UUID
from supabase import create_client
from dotenv import load_dotenv

load_dotenv("c:/Users/PC/Documents/connecthub/connecthub_be/.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

async def main():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # 1. Find Lizzy
    print("Searching for Lizzy...")
    lizzy = supabase.table("profiles").select("*").ilike("display_name", "%Lizzy%").execute()
    
    if not lizzy.data:
        print("Lizzy not found!")
        return
        
    for user in lizzy.data:
        print(f"User: {user['display_name']} ({user['id']})")
        user_id = user['id']
        
        # 2. Find matches
        print(f"  Checking matches for {user_id}...")
        matches_query = supabase.table("matches").select("*").or_(
            f"user1_id.eq.{user_id},user2_id.eq.{user_id}"
        ).execute()
        
        matches = matches_query.data or []
        print(f"  Found {len(matches)} matches.")
        
        for m in matches:
            print(f"    Match {m['id']}: Status={m['status']}, FirstMsg={m.get('first_message_at')}")
            
            # 3. Check messages
            msgs = supabase.table("messages").select("*").eq("match_id", m['id']).execute()
            print(f"      Messages: {len(msgs.data)} found.")
            for msg in msgs.data:
                print(f"        - {msg['content']} ({msg['sender_id']})")

if __name__ == "__main__":
    asyncio.run(main())
