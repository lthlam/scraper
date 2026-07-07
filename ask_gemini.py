import os
import json
import sys
from google import genai
from google.genai import types
from dotenv import load_dotenv

# load env keys
load_dotenv()

# ask question to optibot
def ask_optibot(question):
    meta_path = "data/metadata.json"
    if not os.path.exists(meta_path):
        print("error: metadata file not found, please run main.py first!")
        return
        
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
        
    store_name = meta.get("gemini_store_name")
    if not store_name:
        print("error: gemini_store_name is empty!")
        return

    print("connecting gemini using store: " + store_name)
    
    # init client
    client = genai.Client()
    
    # ask question to model with file search store
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=question,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are OptiBot, the customer-support bot for OptiSigns.com.\n"
                    "Tone: helpful, factual, concise.\n"
                    "Only answer using the uploaded docs.\n"
                    "Max 5 bullet points; else link to the doc.\n"
                    "Cite up to 3 'Article URL:' lines per reply."
                ),
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[store_name]
                        )
                    )
                ]
            )
        )
        print("\n=== OptiBot Response ===")
        print(response.text)
        print("========================\n")
    except Exception as e:
        print("error ask gemini: " + str(e))

if __name__ == "__main__":
    # default question
    query = "How do I add a YouTube video?"
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        
    print(f"asking question: '{query}'")
    ask_optibot(query)
