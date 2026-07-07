import os
import time
from google import genai
from google.genai import types

# init gemini client
def get_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY env variable!")
    return genai.Client(api_key=api_key)

# get old file search store or create new
def get_or_create_file_search_store(client, store_name="OptiBot Store"):
    try:
        response = client.file_search_stores.list()
        for store in response:
            if store.display_name == store_name:
                print(f"found store: {store.name}")
                return store
    except Exception as e:
        print(f"error list store: {e}")

    print(f"create new store: {store_name}")
    config = types.CreateFileSearchStoreConfig(display_name=store_name)
    store = client.file_search_stores.create(config=config)
    print(f"create store success: {store.name}")
    return store

# wait for upload operation done
def wait_for_operation(client, operation, timeout=120):
    start_time = time.time()
    while not operation.done:
        if time.time() - start_time > timeout:
            raise TimeoutError("operation timeout!")
        print("waiting operation...")
        time.sleep(2)
        operation = client.operations.get(operation=operation)
    
    if getattr(operation, "error", None):
        raise RuntimeError(f"operation error: {operation.error}")
        
    return operation

# upload markdown file to gemini store
def upload_file_to_gemini_store(client, store_name, filepath):
    print(f"uploading {filepath} to store {store_name}")
    operation = client.file_search_stores.upload_to_file_search_store(
        file_search_store_name=store_name,
        file=filepath,
        config={"mime_type": "text/markdown"}
    )
    
    completed_op = wait_for_operation(client, operation)
    response_data = completed_op.response
    document_name = getattr(response_data, "document_name", None)
    if not document_name:
        raise RuntimeError("cannot get document name!")
        
    print(f"upload success: {document_name}")
    return document_name

# delete old document from store
def delete_document_from_gemini_store(client, document_name):
    print(f"deleting {document_name}")
    try:
        client.file_search_stores.documents.delete(name=document_name)
        print("deleted success")
    except Exception as e:
        print(f"error delete: {e}")
