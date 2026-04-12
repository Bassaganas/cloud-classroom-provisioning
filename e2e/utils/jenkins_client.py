"""Jenkins API client for test automation."""
import os
import logging
import requests
import time
from typing import Dict, Optional, Any, List
from urllib.parse import urljoin
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class JenkinsClient:
    """Client for interacting with Jenkins API."""
    
    def __init__(self, base_url: Optional[str] = None, username: Optional[str] = None, token: Optional[str] = None):
        """
        Initialize Jenkins client.
        
        Args:
            base_url: Jenkins instance URL (defaults to JENKINS_URL env var)
            username: Jenkins username (defaults to JENKINS_USER env var)
            token: Jenkins API token (defaults to JENKINS_TOKEN env var)
        """
        self.base_url = base_url or os.getenv('JENKINS_URL', '')
        if not self.base_url:
            self.base_url = os.getenv('JENKINS_LOCAL_URL', 'http://localhost:8080')
        
        # Ensure URL ends without trailing slash
        self.base_url = self.base_url.rstrip('/')
        
        self.username = username or os.getenv('JENKINS_USER', 'admin')
        self.token = token or os.getenv('JENKINS_TOKEN', '')
        
        self.session = requests.Session()
        if self.username and self.token:
            self.session.auth = HTTPBasicAuth(self.username, self.token)
        
        self.crumb_enabled = os.getenv('JENKINS_CRUMB_ENABLED', 'true').lower() == 'true'
        self._crumb = None
        
        logger.info(f"Initialized JenkinsClient for {self.base_url}")
    
    def _get_crumb(self) -> Optional[Dict[str, str]]:
        """Get CSRF crumb if Jenkins has it enabled."""
        if not self.crumb_enabled:
            return None
        
        try:
            response = self.session.get(
                f"{self.base_url}/crumbIssuer/api/json",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    'name': data.get('crumbRequestField'),
                    'value': data.get('crumb')
                }
        except Exception as e:
            logger.warning(f"Failed to get Jenkins crumb: {e}")
        
        return None
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make HTTP request to Jenkins API."""
        url = f"{self.base_url}/{endpoint}"
        
        # Add crumb to request headers if available
        crumb = self._get_crumb()
        if crumb:
            if 'headers' not in kwargs:
                kwargs['headers'] = {}
            kwargs['headers'][crumb['name']] = crumb['value']
        
        response = self.session.request(method, url, timeout=10, **kwargs)
        
        if response.status_code >= 400 and response.status_code != 404:
            logger.error(f"{method} {url} - Status: {response.status_code} - Response: {response.text[:500]}")
            response.raise_for_status()
        
        return response
    
    def health_check(self) -> bool:
        """Check if Jenkins is healthy."""
        try:
            response = self.session.get(f"{self.base_url}/api/json", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Jenkins health check failed: {e}")
            return False
    
    def get_job(self, job_name: str) -> Optional[Dict[str, Any]]:
        """
        Get job information.
        
        Args:
            job_name: Name of the job (supports nested paths like 'folder/job')
            
        Returns:
            Job data or None if not found
        """
        try:
            response = self._make_request('GET', f'job/{job_name}/api/json')
            if response.status_code == 200:
                return response.json()
        except requests.HTTPError:
            pass
        return None
    
    def job_exists(self, job_name: str) -> bool:
        """Check if a job exists."""
        return self.get_job(job_name) is not None
    
    def get_builds(self, job_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent builds for a job.
        
        Args:
            job_name: Name of the job
            limit: Number of builds to retrieve
            
        Returns:
            List of build information
        """
        data = self.get_job(job_name)
        if not data or 'builds' not in data:
            return []
        return data['builds'][:limit]
    
    def get_build(self, job_name: str, build_number: int) -> Optional[Dict[str, Any]]:
        """
        Get specific build information.
        
        Args:
            job_name: Name of the job
            build_number: Build number
            
        Returns:
            Build data or None if not found
        """
        try:
            response = self._make_request('GET', f'job/{job_name}/{build_number}/api/json')
            if response.status_code == 200:
                return response.json()
        except requests.HTTPError:
            pass
        return None
    
    def get_last_build(self, job_name: str) -> Optional[Dict[str, Any]]:
        """Get the last build of a job."""
        try:
            response = self._make_request('GET', f'job/{job_name}/lastBuild/api/json')
            if response.status_code == 200:
                return response.json()
        except requests.HTTPError:
            pass
        return None
    
    def get_last_successful_build(self, job_name: str) -> Optional[Dict[str, Any]]:
        """Get the last successful build of a job."""
        try:
            response = self._make_request('GET', f'job/{job_name}/lastSuccessfulBuild/api/json')
            if response.status_code == 200:
                return response.json()
        except requests.HTTPError:
            pass
        return None
    
    def trigger_job(self, job_name: str, parameters: Optional[Dict[str, str]] = None) -> bool:
        """
        Trigger a job build.
        
        Args:
            job_name: Name of the job
            parameters: Optional build parameters
            
        Returns:
            True if trigger was successful
        """
        try:
            if parameters:
                endpoint = f'job/{job_name}/buildWithParameters'
                response = self._make_request('POST', endpoint, data=parameters)
            else:
                endpoint = f'job/{job_name}/build'
                response = self._make_request('POST', endpoint)
            
            success = response.status_code in [200, 201]
            if success:
                logger.info(f"Triggered job: {job_name}")
            else:
                logger.error(f"Failed to trigger job {job_name}: {response.status_code}")
            return success
        except Exception as e:
            logger.error(f"Error triggering job {job_name}: {e}")
            return False
    
    def wait_for_build(self, job_name: str, timeout: int = 300, poll_interval: int = 5) -> Optional[Dict[str, Any]]:
        """
        Wait for a new build to start.
        
        Args:
            job_name: Name of the job
            timeout: Maximum seconds to wait
            poll_interval: Seconds between polls
            
        Returns:
            Build data when build is found, or None if timeout
        """
        start_time = time.time()
        last_build_number = None
        
        # Get current last build
        last_build = self.get_last_build(job_name)
        if last_build:
            last_build_number = last_build.get('number')
        
        while time.time() - start_time < timeout:
            current_build = self.get_last_build(job_name)
            if current_build and current_build.get('number') != last_build_number:
                logger.info(f"New build detected for {job_name}: #{current_build.get('number')}")
                return current_build
            
            time.sleep(poll_interval)
        
        logger.warning(f"Timeout waiting for build on {job_name}")
        return None
    
    def wait_for_build_completion(self, job_name: str, build_number: int, timeout: int = 600, poll_interval: int = 10) -> Optional[Dict[str, Any]]:
        """
        Wait for a build to complete.
        
        Args:
            job_name: Name of the job
            build_number: Build number to wait for
            timeout: Maximum seconds to wait
            poll_interval: Seconds between polls
            
        Returns:
            Build data when complete, or None if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            build = self.get_build(job_name, build_number)
            if build and build.get('result') is not None:
                status = build.get('result')
                logger.info(f"Build {job_name}#{build_number} completed with status: {status}")
                return build
            
            time.sleep(poll_interval)
        
        logger.warning(f"Timeout waiting for build completion: {job_name}#{build_number}")
        return None
    
    def get_build_log(self, job_name: str, build_number: int) -> Optional[str]:
        """
        Get the console output/log of a build.
        
        Args:
            job_name: Name of the job
            build_number: Build number
            
        Returns:
            Log text or None if not found
        """
        try:
            response = self._make_request('GET', f'job/{job_name}/{build_number}/consoleText')
            if response.status_code == 200:
                return response.text
        except requests.HTTPError:
            pass
        return None
    
    def is_build_successful(self, build: Dict[str, Any]) -> bool:
        """Check if a build was successful."""
        return build.get('result') == 'SUCCESS'
    
    def is_build_failed(self, build: Dict[str, Any]) -> bool:
        """Check if a build failed."""
        return build.get('result') == 'FAILURE'
    
    def is_build_unstable(self, build: Dict[str, Any]) -> bool:
        """Check if a build is unstable."""
        return build.get('result') == 'UNSTABLE'
    
    def is_build_running(self, build: Dict[str, Any]) -> bool:
        """Check if a build is currently running."""
        return build.get('result') is None
    
    def abort_build(self, job_name: str, build_number: int) -> bool:
        """
        Abort a running build.
        
        Args:
            job_name: Name of the job
            build_number: Build number
            
        Returns:
            True if abort was successful
        """
        try:
            response = self._make_request('POST', f'job/{job_name}/{build_number}/stop')
            success = response.status_code in [200, 302]
            if success:
                logger.info(f"Aborted build: {job_name}#{build_number}")
            return success
        except Exception as e:
            logger.error(f"Error aborting build {job_name}#{build_number}: {e}")
            return False
