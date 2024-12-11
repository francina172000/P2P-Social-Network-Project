import json
import os
from typing import Dict, Optional
import time

class BucketManager:
    def __init__(self):
        self.buckets_file = "data/user_buckets.json"
        self.buckets_data = {}  # user_id -> {hash, sent_requests_hash, received_requests_hash, created_at} mapping
        self._init_buckets_file()
        
    def _init_buckets_file(self):
        """Initialize or load buckets file"""
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(self.buckets_file), exist_ok=True)
        
        # Load existing bucket data if available
        try:
            if os.path.exists(self.buckets_file):
                with open(self.buckets_file, 'r') as f:
                    self.buckets_data = json.load(f)
        except Exception as e:
            print(f"Error loading buckets file: {e}")
            self.buckets_data = {}

    def _save_buckets_data(self):
        """Save buckets data to file"""
        try:
            with open(self.buckets_file, 'w') as f:
                json.dump(self.buckets_data, f, indent=4)
        except Exception as e:
            print(f"Error saving buckets data: {e}")
            raise

    def get_bucket_hash(self, user_id: str) -> Optional[str]:
        """Get bucket hash for user"""
        bucket_info = self.buckets_data.get(str(user_id))
        return bucket_info['hash'] if bucket_info else None

    def update_bucket_hash(self, user_id: str, bucket_hash: str):
        """Update bucket hash for user"""
        self.buckets_data[str(user_id)] = {
            'hash': bucket_hash,
            'created_at': time.time()
        }
        self._save_buckets_data()

    def get_bucket_creation_time(self, user_id: str) -> Optional[float]:
        """Get bucket creation timestamp"""
        bucket_info = self.buckets_data.get(str(user_id))
        return bucket_info['created_at'] if bucket_info else None

    def user_has_bucket(self, user_id: str) -> bool:
        """Check if user has a bucket"""
        return str(user_id) in self.buckets_data

    def update_sent_requests_hash(self, user_id: str, hash: str):
        """Update sent requests hash for user"""
        if str(user_id) not in self.buckets_data:
            self.buckets_data[str(user_id)] = {}
        self.buckets_data[str(user_id)]['sent_requests_hash'] = hash
        self._save_buckets_data()

    def update_received_requests_hash(self, user_id: str, hash: str):
        """Update received requests hash for user"""
        if str(user_id) not in self.buckets_data:
            self.buckets_data[str(user_id)] = {}
        self.buckets_data[str(user_id)]['received_requests_hash'] = hash
        self._save_buckets_data()

    def get_sent_requests_hash(self, user_id: str) -> Optional[str]:
        """Get sent requests hash for user"""
        bucket_info = self.buckets_data.get(str(user_id), {})
        return bucket_info.get('sent_requests_hash')

    def get_received_requests_hash(self, user_id: str) -> Optional[str]:
        """Get received requests hash for user"""
        bucket_info = self.buckets_data.get(str(user_id), {})
        return bucket_info.get('received_requests_hash')