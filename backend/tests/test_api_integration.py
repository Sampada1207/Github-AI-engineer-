import requests
import time
import uuid
import sys

BASE_URL = "http://localhost:8080/api"

def test_full_workflow():
    print("Starting integration test against local backend...")
    
    # 1. Register a new user
    email = f"test_user_{uuid.uuid4().hex[:6]}@example.com"
    password = "SecretPassword123"
    register_payload = {
        "email": email,
        "password": password,
        "full_name": "Integration Test User",
        "role": "user"
    }
    
    print(f"Registering user with email: {email}")
    r = requests.post(f"{BASE_URL}/auth/register", json=register_payload)
    if r.status_code != 201:
        print(f"Failed to register user: {r.status_code} - {r.text}")
        sys.exit(1)
    print("User registered successfully.")
    
    # 2. Log in
    login_payload = {
        "username": email,
        "password": password
    }
    print("Logging in...")
    r = requests.post(f"{BASE_URL}/auth/login", data=login_payload)
    if r.status_code != 200:
        print(f"Failed to log in: {r.status_code} - {r.text}")
        sys.exit(1)
    
    token_data = r.json()
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Logged in successfully. Token acquired.")
    
    # 3. Create a project
    project_payload = {
        "name": "Integration Test Project",
        "description": "A project created by the automated integration test script."
    }
    print("Creating project...")
    r = requests.post(f"{BASE_URL}/projects/", json=project_payload, headers=headers)
    if r.status_code not in (200, 201):
        print(f"Failed to create project: {r.status_code} - {r.text}")
        sys.exit(1)
    
    project = r.json()
    project_id = project["id"]
    print(f"Project created successfully with ID: {project_id}")
    
    # 4. Import a repository
    repo_payload = {
        "project_id": project_id,
        "url": "https://github.com/octocat/Spoon-Knife.git",
        "name": "Spoon-Knife",
        "branch": "main"
    }
    print(f"Importing repository: {repo_payload['url']} (branch: {repo_payload['branch']})")
    r = requests.post(f"{BASE_URL}/repositories", json=repo_payload, headers=headers)
    if r.status_code not in (200, 201):
        print(f"Failed to import repository: {r.status_code} - {r.text}")
        sys.exit(1)
        
    repo = r.json()
    repo_id = repo["id"]
    print(f"Repository import initiated. ID: {repo_id}")
    
    # 5. Poll repository status until complete
    status = "cloning"
    max_attempts = 45
    attempt = 0
    print("Polling repository analysis status...")
    while status not in ("completed", "failed") and attempt < max_attempts:
        time.sleep(1)
        attempt += 1
        r = requests.get(f"{BASE_URL}/repositories/{repo_id}", headers=headers)
        if r.status_code != 200:
            print(f"Failed to fetch repo status: {r.status_code} - {r.text}")
            sys.exit(1)
        repo_status = r.json()
        status = repo_status["status"]
        print(f"[{attempt}/{max_attempts}] Current status: {status}")
        
    if status == "failed":
        print(f"Repository analysis failed! Error message: {repo_status.get('error_message')}")
        sys.exit(1)
    elif status != "completed":
        print(f"Repository analysis timed out (still status: {status})")
        sys.exit(1)
        
    print("Repository analysis completed successfully!")
    print(f"Language Stats: {repo_status.get('language_stats')}")
    print(f"Health Score: {repo_status.get('health_score')}")
    
    # 5.5 Verify listing repositories for the project
    print("Testing GET /repositories list endpoint...")
    r = requests.get(f"{BASE_URL}/repositories?project_id={project_id}", headers=headers)
    if r.status_code != 200:
        print(f"Failed to list repositories: {r.status_code} - {r.text}")
        sys.exit(1)
    repos_list = r.json()
    assert len(repos_list) >= 1
    assert any(repo["id"] == repo_id for repo in repos_list)
    print("GET /repositories list endpoint works correctly and returned the repository.")

    # 6. Create a chat session
    chat_payload = {
        "repository_id": repo_id,
        "title": "Welcome Chat"
    }
    print("Creating chat session...")
    r = requests.post(f"{BASE_URL}/repositories/{repo_id}/chats", json=chat_payload, headers=headers)
    if r.status_code != 201:
        print(f"Failed to create chat: {r.status_code} - {r.text}")
        sys.exit(1)
        
    chat = r.json()
    chat_id = chat["id"]
    print(f"Chat session created successfully. ID: {chat_id}")
    
    # 7. Send message to AI assistant
    msg_payload = {
        "content": "Explain this repository and list its files."
    }
    print("Sending message to AI assistant (RAG Query)...")
    r = requests.post(f"{BASE_URL}/chats/{chat_id}/messages", json=msg_payload, headers=headers)
    if r.status_code != 201:
        print(f"Failed to send message: {r.status_code} - {r.text}")
        sys.exit(1)
        
    msg_response = r.json()
    print("\n--- AI Assistant Response ---")
    print(msg_response["content"])
    print("-----------------------------")
    print(f"Citations: {msg_response.get('citations')}")
    
    print("\nAPI Integration Test PASSED successfully!")

if __name__ == "__main__":
    test_full_workflow()
