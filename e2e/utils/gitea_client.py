"""Gitea API client for test automation."""
import os
import logging
import requests
import base64
from typing import Dict, Optional, Any
from urllib.parse import urljoin
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class GiteaClient:
    """Client for interacting with Gitea API."""
    
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize Gitea client.
        
        Args:
            base_url: Gitea instance URL (defaults to GITEA_URL env var)
            token: Gitea API token (defaults to GITEA_API_TOKEN env var)
            username: Gitea username (can be admin or student)
            password: Gitea password (for basic auth when token not available)
        """
        self.base_url = base_url or os.getenv('GITEA_URL', '')
        if not self.base_url:
            self.base_url = os.getenv('GITEA_LOCAL_URL', 'http://localhost:3000')
        
        self.token = token or os.getenv('GITEA_API_TOKEN', '')
        self.username = username or os.getenv('GITEA_ADMIN_USER', 'gitea_admin')
        self.password = password or os.getenv('GITEA_ADMIN_PASSWORD', '')
        
        self.session = requests.Session()
        
        # Set up authentication: prefer token, fallback to basic auth
        if self.token:
            self.session.headers.update({
                'Authorization': f'token {self.token}',
                'Content-Type': 'application/json'
            })
        elif self.username and self.password:
            # Use basic auth for username/password
            self.session.auth = HTTPBasicAuth(self.username, self.password)
            self.session.headers.update({'Content-Type': 'application/json'})
        
        logger.info(f"Initialized GiteaClient for {self.base_url} with user {self.username}")
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make HTTP request to Gitea API."""
        url = urljoin(self.base_url, f'/api/v1/{endpoint}')
        response = self.session.request(method, url, **kwargs)
        
        if response.status_code >= 400 and response.status_code != 404:
            logger.error(f"{method} {url} - Status: {response.status_code} - Response: {response.text}")
            response.raise_for_status()
        
        return response
    
    def get_user(self, username: str) -> Dict[str, Any]:
        """
        Get user information by username.
        
        Args:
            username: Username to look up
            
        Returns:
            User data from Gitea
        """
        response = self._make_request('GET', f'users/{username}')
        if response.status_code == 404:
            raise ValueError(f"User '{username}' not found")
        return response.json()
    
    def create_user(self, username: str, email: str, password: str, full_name: str = "") -> Dict[str, Any]:
        """
        Create a new user in Gitea.
        
        Args:
            username: Username for new account
            email: Email address
            password: Password for account
            full_name: Full name (optional)
            
        Returns:
            User data from Gitea
        """
        payload = {
            "login_name": username,
            "username": username,
            "email": email,
            "password": password,
            "full_name": full_name or username,
            "must_change_password": False
        }
        response = self._make_request('POST', 'admin/users', json=payload)
        logger.info(f"Created user: {username}")
        return response.json()
    
    def user_exists(self, username: str) -> bool:
        """Check if user exists in Gitea."""
        try:
            response = self._make_request('GET', f'users/{username}')
            return response.status_code == 200
        except requests.HTTPError:
            return False
    
    def get_or_create_user(self, username: str, email: str, password: str) -> Dict[str, Any]:
        """Get user if exists, otherwise create."""
        if self.user_exists(username):
            logger.info(f"User {username} already exists")
            response = self._make_request('GET', f'users/{username}')
            return response.json()
        return self.create_user(username, email, password)
    
    def create_repository(self, owner: str, repo_name: str, description: str = "", is_private: bool = False) -> Dict[str, Any]:
        """
        Create a new repository.
        
        Args:
            owner: Repository owner (username)
            repo_name: Repository name
            description: Repository description
            is_private: Whether repository should be private
            
        Returns:
            Repository data from Gitea
        """
        payload = {
            "name": repo_name,
            "description": description,
            "private": is_private,
            "auto_init": True,  # Create with README
            "default_branch": "main"
        }
        response = self._make_request('POST', f'user/repos', json=payload)
        logger.info(f"Created repository: {owner}/{repo_name}")
        return response.json()
    
    def user_create_repository(self, username: str, repo_name: str, description: str = "", is_private: bool = False) -> Dict[str, Any]:
        """
        Create a repository as a specific user.
        
        Args:
            username: Username who will own the repo
            repo_name: Repository name
            description: Repository description
            is_private: Whether repository should be private
            
        Returns:
            Repository data from Gitea
        """
        # This uses the authenticated token's user, not the specified username
        # In real scenarios, you'd create repo with the user's own token
        return self.create_repository(username, repo_name, description, is_private)
    
    def repository_exists(self, owner: str, repo_name: str) -> bool:
        """Check if repository exists."""
        try:
            response = self._make_request('GET', f'repos/{owner}/{repo_name}')
            return response.status_code == 200
        except requests.HTTPError:
            return False
    
    def push_file(self, owner: str, repo_name: str, file_path: str, content: str, message: str = "Add file via test", branch: str = "main") -> Dict[str, Any]:
        """
        Push a file to repository using API.
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            file_path: Path within repo (e.g., 'src/main.py')
            content: File content (base64 encoded if binary)
            message: Commit message
            branch: Branch to push to
            
        Returns:
            Commit data from Gitea
        """
        import base64
        
        # Encode content to base64
        encoded_content = base64.b64encode(content.encode()).decode()
        
        payload = {
            "content": encoded_content,
            "message": message,
            "branch": branch
        }
        
        response = self._make_request('POST', f'repos/{owner}/{repo_name}/contents/{file_path}', json=payload)
        logger.info(f"Pushed file {file_path} to {owner}/{repo_name}")
        return response.json()
    
    def create_webhook(self, owner: str, repo_name: str, webhook_url: str, events: Optional[list] = None, active: bool = True) -> Dict[str, Any]:
        """
        Create a webhook on repository.
        
        Args:
            owner: Repository owner
            repo_name: Repository name
            webhook_url: URL where webhook events will be sent
            events: List of events to trigger webhook (default: push)
            active: Whether webhook is active
            
        Returns:
            Webhook data from Gitea
        """
        if events is None:
            events = ['push']
        
        payload = {
            "type": "gitea",
            "config": {
                "url": webhook_url,
                "http_method": "POST",
                "content_type": "json"
            },
            "events": events,
            "active": active
        }
        
        response = self._make_request('POST', f'repos/{owner}/{repo_name}/hooks', json=payload)
        logger.info(f"Created webhook on {owner}/{repo_name} -> {webhook_url}")
        return response.json()
    
    def list_webhooks(self, owner: str, repo_name: str) -> list:
        """List all webhooks on a repository."""
        response = self._make_request('GET', f'repos/{owner}/{repo_name}/hooks')
        return response.json()
    
    def delete_webhook(self, owner: str, repo_name: str, webhook_id: int) -> bool:
        """Delete a webhook."""
        try:
            self._make_request('DELETE', f'repos/{owner}/{repo_name}/hooks/{webhook_id}')
            logger.info(f"Deleted webhook {webhook_id} from {owner}/{repo_name}")
            return True
        except requests.HTTPError:
            return False
    
    def get_webhook_deliveries(self, owner: str, repo_name: str, webhook_id: int) -> list:
        """Get delivery history for a webhook."""
        response = self._make_request('GET', f'repos/{owner}/{repo_name}/hooks/{webhook_id}/deliveries')
        return response.json()
    
    def get_latest_webhook_delivery(self, owner: str, repo_name: str, webhook_id: int) -> Optional[Dict[str, Any]]:
        """Get the latest webhook delivery."""
        deliveries = self.get_webhook_deliveries(owner, repo_name, webhook_id)
        return deliveries[0] if deliveries else None
    
    def get_branch(self, owner: str, repo_name: str, branch: str = "main") -> Dict[str, Any]:
        """Get branch information."""
        response = self._make_request('GET', f'repos/{owner}/{repo_name}/branches/{branch}')
        return response.json()
    
    def delete_repository(self, owner: str, repo_name: str) -> bool:
        """Delete a repository."""
        try:
            self._make_request('DELETE', f'repos/{owner}/{repo_name}')
            logger.info(f"Deleted repository {owner}/{repo_name}")
            return True
        except requests.HTTPError as e:
            logger.error(f"Failed to delete repository {owner}/{repo_name}: {e}")
            return False
    
    def health_check(self) -> bool:
        """Check if Gitea instance is healthy."""
        try:
            response = self.session.get(urljoin(self.base_url, '/api/v1/version'), timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Gitea health check failed: {e}")
            return False
