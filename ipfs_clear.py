import requests
import time
from config import Config

class IPFSCleaner:
    def __init__(self):
        self.ipfs_api_url = f'http://{Config.EC2_PUBLIC_IP}:5001/api/v0'
        self.max_retries = 3

    def connect_to_ipfs(self):
        for attempt in range(self.max_retries):
            try:
                response = requests.post(f"{self.ipfs_api_url}/version")
                response.raise_for_status()
                print("Successfully connected to IPFS")
                return
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    print("Failed to connect to IPFS after multiple attempts")
                    raise

    def remove_content(self, ipfs_hash):
        try:
            response = requests.post(f'{self.ipfs_api_url}/pin/rm?arg={ipfs_hash}')
            if response.status_code == 200:
                print(f"Successfully unpinned content with hash: {ipfs_hash}")
            else:
                print(f"Failed to unpin content with hash: {ipfs_hash}. Status code: {response.status_code}")
        except Exception as e:
            print(f"Error removing content from IPFS: {str(e)}")

    def clear_all_content(self):
        try:
            # List all pinned items
            response = requests.post(f'{self.ipfs_api_url}/pin/ls')
            if response.status_code == 200:
                pinned_items = response.json()
                for ipfs_hash in pinned_items.get('Keys', {}):
                    self.remove_content(ipfs_hash)
                print("All pinned content has been removed.")
            else:
                print(f"Failed to list pinned items. Status code: {response.status_code}")
        except Exception as e:
            print(f"Error clearing all content from IPFS: {str(e)}")

def main():
    cleaner = IPFSCleaner()
    try:
        cleaner.connect_to_ipfs()
        cleaner.clear_all_content()
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()