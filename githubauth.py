
import requests
import base64
from collections import deque

def get_github_code_files(owner: str, repo: str, branch: str = 'main', path: str = '', pat: str = '') -> dict:
    """
    Fetches code files from a GitHub repository using an OAuth access token.
    It traverses directories recursively to find all files.

    Args:
        access_token: Your GitHub OAuth access token.
        owner: The owner of the repository (username or organization).
        repo: The name of the repository.
        branch: The branch to fetch files from (default: 'main').
        path: The starting path within the repository (default: root).

    Returns:
        A dictionary where keys are file paths (relative to repo root) and
        values are their decoded string contents. Returns an empty dictionary
        if the repository or path is not found, or on other errors.
    """
    base_url = "https://api.github.com"
    headers = {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github.v3+json" # Standard GitHub API JSON response
    }
    
    code_files = {}
    # Use a deque for efficient appends and pops from both ends (though only popleft is used here)
    # Strip leading/trailing slashes from the initial path to ensure correct URL construction
    queue = deque([path.strip('/')]) 

    session = requests.Session()

    while queue:
        current_path = queue.popleft()
        
        # Construct the API URL for contents of the current path
        # The 'ref' parameter specifies the branch
        contents_url = f"{base_url}/repos/{owner}/{repo}/contents/{current_path}?ref={branch}"
        
        try:
            response = session.get(contents_url, headers=headers, verify=False)
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
            
            items = response.json()

            # The GitHub API returns a list if `current_path` is a directory,
            # or a dictionary if `current_path` is a single file.
            if isinstance(items, dict): # If it's a single file, wrap it in a list for uniform processing
                items = [items]
            
            for item in items:
                if item['type'] == 'file':
                    file_path = item['path']
                    
                    # Prioritize download_url for raw content, as it's often simpler and more direct
                    if 'download_url' in item and item['download_url']:
                        try:
                            # For private repos, the download_url might also require authentication
                            file_content_response = session.get(item['download_url'], headers={"Authorization": f"token {pat}"}, verify=False)
                            file_content_response.raise_for_status()
                            code_files[file_path] = file_content_response.text
                        except requests.exceptions.RequestException as e:
                            print(f"Warning: Could not download file {file_path} from {item['download_url']}: {e}")
                    # Fallback to base64 content if download_url is not available or fails
                    elif 'content' in item and item['content'] and item['encoding'] == 'base64':
                        try:
                            decoded_content = base64.b64decode(item['content']).decode('utf-8')
                            code_files[file_path] = decoded_content
                        except (base64.binascii.Error, UnicodeDecodeError) as e:
                            print(f"Warning: Could not decode base64 content for {file_path}: {e}")
                    else:
                        print(f"Warning: Skipping file {file_path} as its content could not be retrieved or decoded.")

                elif item['type'] == 'dir':
                    # Add directory path to the queue for further traversal
                    queue.append(item['path'])
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"Error: Repository '{owner}/{repo}' or path '{current_path}' not found. Status code: {e.response.status_code}")
            elif e.response.status_code == 401 or e.response.status_code == 403:
                print(f"Error: Authentication failed or access denied. Check your token and permissions. Status code: {e.response.status_code}")
            else:
                print(f"Error fetching contents for '{current_path}': {e}. Status code: {e.response.status_code}")
            return {} # Return empty dict on critical errors
        except requests.exceptions.RequestException as e:
            print(f"Error connecting to GitHub API: {e}")
            return {} # Return empty dict on connection errors
        except ValueError as e: # JSON decoding error
            print(f"Error decoding JSON response for '{current_path}': {e}")
            return {}

    return code_files
 
