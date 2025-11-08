import json
import logging
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
import os
from dotenv import load_dotenv
from pathlib import Path
import requests
import traceback
from requests.exceptions import HTTPError
import time
#import tiktoken
import re
import random
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== MODELS =====
class StudentDifyConfig(BaseModel):
    """Student's Dify configuration"""
    dify_base_url: str  # e.g., "http://10.0.1.100/v1"
    dify_api_key: str   # Student's specific API key
    dataset_id: Optional[str] = None  # Optional, will be created if not provided

class IngestJiraRequest(BaseModel):
    """Model for JSON file ingestion requests."""
    project: str  # Required: the project name (e.g., "TOC_JiraEcosystem_issues")


# ===== DIFY INTEGRATION CLASS =====
class DifyIntegration:
    def __init__(self, api_key: str = None, base_url: str = None, dataset_id: str = None, advanced_ingestion: bool = False):
        self.dataset_api_key = api_key
        self.base_url = base_url
        self.dataset_id = dataset_id
        self.advanced_ingestion = advanced_ingestion
        
        if not self.dataset_api_key:
            raise ValueError("Missing Dify API key.")
        
        self.headers = {
            'Authorization': f'Bearer {self.dataset_api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        try:
            if not self.dataset_id or self.dataset_id == "your-dataset-id":
                self.dataset_id = self.create_dataset(name=None, advanced_ingestion=self.advanced_ingestion)
                logger.info(f"[DIFY] Created new dataset with id: {self.dataset_id}")
            else:
                logger.info(f"[DIFY] Using existing dataset with id: {self.dataset_id}")
        except Exception as e:
            logger.error(f"[DIFY] Error initializing dataset: {e}")
            raise

    def _get_token_count(self, text: str, model: str = "text-embedding-ada-002") -> int:
        """Simple token counting approximation"""
        # Rough approximation: 1 token ≈ 4 characters for most text
        return len(text) // 4

    def _get_chunk_params(self, text: str, default_max=2000, overlap_ratio=0.25):
        token_count = self._get_token_count(text)
        logger.info(f"[DIFY] Token count: {token_count}")
        if token_count <= default_max:
            logger.info(f"[DIFY] Token count is less than default max: {token_count} <= {default_max}")
            return default_max, 0
        else:
            logger.info(f"[DIFY] Token count is greater than default max: {token_count} > {default_max}")
            overlap = int(default_max * overlap_ratio)
            return default_max, overlap

    def _format_issue_for_text(self, issue: dict, advanced_ingestion: bool = False) -> dict:
        """Format a Jira issue into a document suitable for Dify ingestion by text"""
        logger.debug(f"[DIFY] Raw issue data: {json.dumps(issue, indent=2)}")
        
        try:
            # Extract values using helper method
            key = self._get_nested_value(issue, ['key', 'fields.key'], 'Unknown')
            project = self._get_nested_value(issue, ['project.key', 'fields.project.key'], 'Unknown Project')
            issue_type = self._get_nested_value(issue, ['issuetype.name', 'fields.issuetype.name'], 'Unknown Type')
            status = self._get_nested_value(issue, ['status.name', 'fields.status.name'], 'Unknown Status')
            assignee = self._get_nested_value(issue, ['assignee.name', 'fields.assignee.name'], 'Unassigned')
            created = self._get_nested_value(issue, ['created', 'fields.created'], 'Unknown')
            updated = self._get_nested_value(issue, ['updated', 'fields.updated'], 'Unknown')
            summary = self._get_nested_value(issue, ['summary', 'fields.summary'], 'No summary provided')
            description = self._get_nested_value(issue, ['description', 'fields.description'], 'No description provided')

            # Extract issue number from key (e.g., REST-271 -> 271)
            match = re.search(r"(\d+)$", key)
            issue_number = match.group(1) if match else None

            text_parts = []
            if advanced_ingestion:
                # Build aliases list
                aliases = [key, f"Issue {key}", f"Jira {key}"]
                if issue_number:
                    aliases.append(issue_number)
                    aliases.append(f"Issue {issue_number}")
                    aliases.append(f"Jira {issue_number}")
                aliases_line = "Aliases: " + ", ".join(aliases) + "\n"
                # Build example queries
                example_queries = [
                    f"What is {key} about?",
                    f"How to test {key}?",
                    f"What does {key} fix?",
                    f"How was {key} resolved?",
                    f"Who reported {key}?",
                    f"Who is assigned to {key}?",
                    f"What is the status of {key}?",
                    f"What project is {key} part of?",
                    f"What is the summary of {key}?",
                    f"Give a test plan for {key}",
                    f"What is the acceptance criteria for {key}?",
                    f"What is the impact of {key}?",
                    f"What is the root cause of {key}?",
                    f"What is the fix for {key}?",
                    f"What is the priority of {key}?",
                    f"What is the type of {key}?",
                    f"When was {key} created?",
                    f"When was {key} updated?",
                    f"What is the description of {key}?",
                    f"What is the context for {key}?",
                    f"How does {key} relate to the product/company/project?"
                ]
                if issue_number:
                    example_queries += [
                        f"What is issue {issue_number} about?",
                        f"How to test issue {issue_number}?",
                        f"Who reported issue {issue_number}?",
                        f"Who is assigned to issue {issue_number}?",
                        f"What is the status of issue {issue_number}?",
                        f"What project is issue {issue_number} part of?",
                        f"What is the summary of issue {issue_number}?",
                        f"Give a test plan for issue {issue_number}",
                        f"What is the acceptance criteria for issue {issue_number}?",
                        f"What is the impact of issue {issue_number}?",
                        f"What is the root cause of issue {issue_number}?",
                        f"What is the fix for issue {issue_number}?",
                        f"What is the priority of issue {issue_number}?",
                        f"What is the type of issue {issue_number}?",
                        f"When was issue {issue_number} created?",
                        f"When was issue {issue_number} updated?",
                        f"What is the description of issue {issue_number}?",
                        f"What is the context of issue {issue_number}?",
                        f"How does issue {issue_number} relate to the product/company/project?"
                    ]
                example_queries_line = "Example queries:\n- " + "\n- ".join(example_queries) + "\n"
                text_parts.append(aliases_line)
                text_parts.append(example_queries_line)
            text_parts.append(f"Summary: {summary}\n\nJira Issue: {key}\nProject: {project}\nType: {issue_type}\nStatus: {status}\nAssignee: {assignee}\nCreated: {created}\nUpdated: {updated}\n\nDescription:\n{description}\n")
            text = "".join(text_parts)
            
            # Set your desired chunking config
            # Use "###CHUNK###" as separator - this string doesn't exist in the text,
            # so Dify won't find it and will keep the entire issue as a single chunk
            # Dify requires max_tokens to be between 50 and 4000
            # Since the separator doesn't exist, Dify will treat the entire text as one chunk
            # even if it exceeds max_tokens (because it can't find the separator to split on)
            max_tokens = 4000  # Maximum allowed by Dify API
            chunk_overlap = 800  # Overlap to share context if splitting occurs
            process_rule = {
                "mode": "custom",
                "rules": {
                    "pre_processing_rules": [
                        {"id": "remove_extra_spaces", "enabled": True},
                        {"id": "remove_urls_emails", "enabled": False}
                    ],
                    "segmentation": {
                        "separator": "###CHUNK###",
                        "max_tokens": max_tokens,
                        "chunk_overlap": chunk_overlap
                    }
                }
            }
            logger.info(f"[DIFY] Document '{key}': process_rule sent to Dify: {json.dumps(process_rule)}")
            
            # Create the document - keep it simple like the original to ensure single chunk per issue
            doc = {
                "name": f"Jira Issue {key}",
                "text": text,
                "indexing_technique": "high_quality",
                "process_rule": process_rule
            }
            
            logger.info(f"[DIFY] Full request body: {json.dumps(doc)}")
            return doc
        except Exception as e:
            logger.error(f"[DIFY] Error formatting issue: {str(e)}\n{traceback.format_exc()}")
            raise

    def _get_nested_value(self, data: dict, possible_paths: List[str], default: str = "Unknown") -> str:
        """Safely get a value from a nested dictionary using multiple possible paths"""
        for path in possible_paths:
            try:
                value = data
                for key in path.split('.'):
                    value = value.get(key, {})
                if value and value != {}:
                    return str(value)
            except (AttributeError, KeyError, TypeError):
                continue
        return default

    def _format_issue_metadata(self, issue: dict, document_id: str, metadata_id: str):
        """Format metadata payload to attach issue_key to documents"""
        # Handle both dictionary issues and objects with 'key' attribute
        issue_key = issue.get('key') if isinstance(issue, dict) else (issue.key if hasattr(issue, 'key') else 'Unknown')
        return {
            "operation_data": [{
                "document_id": document_id,
                "metadata_list": [{
                    "id": metadata_id,
                    "value": issue_key,
                    "name": "issue_key"
                }]
            }]
        }
    
    def _enable_builtin_metadata(self):
        """Enable built-in metadata (creation date, update date, document type) in Dify dataset"""
        url = f"{self.base_url}/datasets/{self.dataset_id}/metadata/built-in/enable"
        try:
            logger.info(f"[DIFY] Enabling built-in metadata: POST {url}")
            response = requests.post(url, headers=self.headers)
            logger.info(f"[DIFY] Response {response.status_code}: {response.text}")
            response.raise_for_status()
            return response
        except Exception as e:
            logger.error(f"[DIFY] Error enabling built-in metadata: {e}\n{traceback.format_exc()}")
            raise
    
    def _create_knowledge_metadata(self):
        """Create custom metadata field named 'issue_key' in the dataset"""
        url = f"{self.base_url}/datasets/{self.dataset_id}/metadata"
        metadata = {"type": "string", "name": "issue_key"}
        try:
            logger.info(f"[DIFY] Creating knowledge metadata: POST {url} {metadata}")
            response = requests.post(url, headers=self.headers, json=metadata)
            logger.info(f"[DIFY] Response {response.status_code}: {response.text}")
            response.raise_for_status()
            return response
        except Exception as e:
            logger.error(f"[DIFY] Error creating knowledge metadata: {e}\n{traceback.format_exc()}")
            raise

    def create_dataset(self, name: str = None, permission: str = "only_me", search_method: str = "hybrid_search", advanced_ingestion: bool = False) -> str:
        if name is None:
            mode = "Advanced" if advanced_ingestion else "Basic"
            rand_num = random.randint(100000, 999999)
            name = f"Jira_API_{mode}_{rand_num}"
        url = f"{self.base_url}/datasets"
        
        # Simplified dataset creation payload - let Dify use default embedding model
        data = {
            "name": name,
            "permission": permission,
            "indexing_technique": "high_quality"
        }
        
        try:
            logger.info(f"[DIFY] Creating dataset: POST {url}")
            logger.info(f"[DIFY] Request payload: {json.dumps(data, indent=2)}")
            response = requests.post(url, headers=self.headers, json=data)
            logger.info(f"[DIFY] Response {response.status_code}: {response.text}")
            
            if response.status_code != 200:
                logger.error(f"[DIFY] Dataset creation failed with status {response.status_code}")
                logger.error(f"[DIFY] Response headers: {dict(response.headers)}")
                logger.error(f"[DIFY] Response body: {response.text}")
                raise HTTPError(f"Dataset creation failed: {response.status_code} - {response.text}")
            
            dataset_info = response.json()
            logger.info(f"[DIFY] Dataset created successfully: id={dataset_info.get('id')}, name={dataset_info.get('name')}")
            return dataset_info["id"] 
        except Exception as e:
            logger.error(f"[DIFY] Error creating dataset: {e}\n{traceback.format_exc()}")
            raise

    def ingest_json_file(self, json_file_path: str, advanced_ingestion: bool = False) -> List[dict]:
        """Ingest issues from a JSON file into Dify Knowledge Base"""
        try:
            logger.info(f"[DIFY] Reading JSON file: {json_file_path}")
            with open(json_file_path, 'r') as f:
                content = f.read()
                logger.debug(f"[DIFY] Raw JSON content: {content[:500]}...")
                data = json.loads(content)
            
            # Check if this is a summary file
            if json_file_path.endswith('_SUMMARY.json'):
                logger.info("[DIFY] Detected summary file, processing as multiple documents")
                # If it's a list, use the first item as the summary dict
                if isinstance(data, list):
                    if len(data) == 0:
                        raise ValueError("Summary file is an empty list!")
                    summary_data = data[0]
                else:
                    summary_data = data
                return self._ingest_summary_file(summary_data, json_file_path)
            
            # Handle different data structures
            if isinstance(data, list):
                logger.info(f"[DIFY] Processing list of {len(data)} items")
                return self.ingest_issues(data, advanced_ingestion=advanced_ingestion)
            elif isinstance(data, dict):
                if 'issues' in data:
                    logger.info(f"[DIFY] Processing issues from 'issues' field")
                    return self.ingest_issues(data['issues'], advanced_ingestion=advanced_ingestion)
                else:
                    logger.info("[DIFY] Processing single issue document")
                    return self.ingest_issues([data], advanced_ingestion=advanced_ingestion)
            else:
                error_msg = f"Unexpected data type in JSON file: {type(data)}"
                logger.error(f"[DIFY] {error_msg}")
                raise ValueError(error_msg)
                
        except json.JSONDecodeError as e:
            error_msg = f"[DIFY] Invalid JSON format in file {json_file_path}: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            raise
        except Exception as e:
            error_msg = f"[DIFY] Error ingesting JSON file {json_file_path}: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            raise

    def ingest_issues(self, issues: List[dict], advanced_ingestion: bool = False) -> List[dict]:
        """Ingest Jira issues into Dify Knowledge Base (Dataset) as documents"""
        responses = []
        try:
            logger.info(f"[DIFY] ===== STARTING DIFY INGESTION =====")
            logger.info(f"[DIFY] Total issues to process: {len(issues)}")
            logger.info(f"[DIFY] Advanced ingestion: {advanced_ingestion}")
            logger.info(f"[DIFY] Dataset ID: {self.dataset_id}")
            logger.info(f"[DIFY] Base URL: {self.base_url}")
            logger.info(f"[DIFY] Headers: {json.dumps(self.headers, indent=2)}")
            logger.info(f"[DIFY] ===== INGESTION CONFIG =====")
            
            # Enable built-in metadata and create custom metadata field
            try:
                self._enable_builtin_metadata()
                metadata_response = self._create_knowledge_metadata()
                metadata_id = metadata_response.json()["id"]
                logger.info(f"[DIFY] Created metadata with ID: {metadata_id}")
            except Exception as metadata_error:
                logger.warning(f"[DIFY] Could not set up metadata (may already exist): {str(metadata_error)}")
                # Try to continue without metadata - it might already be set up
                metadata_id = None
            
            for idx, issue in enumerate(issues, 1):
                try:
                    issue_key = issue.get('key', f'issue-{idx}')
                    logger.info(f"[DIFY] Processing issue {idx}/{len(issues)}: {issue_key}")
                    
                    # Debug: Log the raw issue structure
                    logger.info(f"[DIFY] Raw issue structure: {json.dumps(issue, indent=2)[:1000]}...")
                    
                    url = f"{self.base_url}/datasets/{self.dataset_id}/document/create-by-text"
                    logger.info(f"[DIFY] Dify URL: {url}")
                    logger.info(f"[DIFY] Dataset ID: {self.dataset_id}")
                    logger.info(f"[DIFY] Headers: {self.headers}")
                    
                    data = self._format_issue_for_text(issue, advanced_ingestion=advanced_ingestion)
                    logger.info(f"[DIFY] Formatted document name: {data.get('name', 'Unknown')}")
                    logger.info(f"[DIFY] Formatted document text length: {len(data.get('text', ''))}")
                    logger.info(f"[DIFY] Formatted document keys: {list(data.keys())}")
                    logger.debug(f"[DIFY] Formatted issue data: {json.dumps(data, indent=2)}")
                    
                    # Log the exact call being made to Dify
                    logger.info(f"[DIFY] ===== EXACT DIFY API CALL =====")
                    logger.info(f"[DIFY] Method: POST")
                    logger.info(f"[DIFY] URL: {url}")
                    logger.info(f"[DIFY] Headers: {json.dumps(self.headers, indent=2)}")
                    logger.info(f"[DIFY] Request Body: {json.dumps(data, indent=2)}")
                    logger.info(f"[DIFY] ===== END DIFY API CALL =====")
                    
                    logger.info(f"[DIFY] Creating document: POST {url}")
                    response = requests.post(url, headers=self.headers, json=data)
                    
                    # Log the complete response details
                    logger.info(f"[DIFY] ===== DIFY API RESPONSE =====")
                    logger.info(f"[DIFY] Status Code: {response.status_code}")
                    logger.info(f"[DIFY] Response Headers: {json.dumps(dict(response.headers), indent=2)}")
                    logger.info(f"[DIFY] Response Text: {response.text}")
                    logger.info(f"[DIFY] ===== END DIFY API RESPONSE =====")
                    
                    if response.status_code != 200:
                        logger.error(f"[DIFY] Non-200 response: {response.status_code} - {response.text}")
                        
                        # Handle specific error cases
                        if response.status_code == 500:
                            logger.error(f"[DIFY] Internal Server Error from Dify - this indicates a problem with the Dify instance itself")
                            logger.error(f"[DIFY] Possible causes: Dataset corrupted, Dify overloaded, or API key permissions issue")
                        elif response.status_code == 404:
                            logger.error(f"[DIFY] Dataset not found - check if dataset ID exists")
                        elif response.status_code == 401:
                            logger.error(f"[DIFY] Unauthorized - check API key")
                        elif response.status_code == 403:
                            logger.error(f"[DIFY] Forbidden - API key lacks permissions")
                        
                        # Don't raise here, just log and continue
                        continue
                    
                    response.raise_for_status()
                    response_data = response.json()
                    responses.append(response_data)
                    logger.info(f"[DIFY] Successfully created document for issue {idx}")
                    
                    # Extract document_id and attach metadata
                    if metadata_id:
                        try:
                            document_id = response_data.get("document", {}).get("id")
                            if not document_id:
                                logger.warning(f"[DIFY] Could not extract document_id from response for issue {idx}")
                            else:
                                logger.info(f"[DIFY] Document created with ID: {document_id}")
                                
                                # Format and attach metadata
                                metadata = self._format_issue_metadata(issue=issue, document_id=document_id, metadata_id=metadata_id)
                                url_metadata = f"{self.base_url}/datasets/{self.dataset_id}/documents/metadata"
                                logger.info(f"[DIFY] Attaching metadata: POST {url_metadata}")
                                metadata_response = requests.post(url_metadata, headers=self.headers, json=metadata)
                                logger.info(f"[DIFY] Metadata response {metadata_response.status_code}: {metadata_response.text}")
                                metadata_response.raise_for_status()
                                responses.append(metadata_response.json())
                                logger.info(f"[DIFY] Successfully attached metadata for issue {idx}")
                        except Exception as metadata_error:
                            logger.warning(f"[DIFY] Could not attach metadata for issue {idx}: {str(metadata_error)}")
                            # Continue processing even if metadata attachment fails
                    
                except requests.exceptions.RequestException as e:
                    error_msg = f"[DIFY] Request error processing issue {idx}: {str(e)}"
                    logger.error(f"{error_msg}")
                    if hasattr(e, 'response') and e.response is not None:
                        logger.error(f"[DIFY] Response content: {e.response.text}")
                    continue
                    
                except Exception as e:
                    error_msg = f"[DIFY] Error processing issue {idx}: {str(e)}"
                    logger.error(f"{error_msg}\n{traceback.format_exc()}")
                    continue
                    
            logger.info(f"[DIFY] ===== INGESTION COMPLETE =====")
            logger.info(f"[DIFY] Total issues processed: {len(issues)}")
            # If metadata is attached, each issue creates 2 responses (document + metadata)
            # Otherwise, each issue creates 1 response
            if metadata_id:
                issues_processed = len(responses) // 2
                logger.info(f"[DIFY] Successfully created documents: {issues_processed}")
                logger.info(f"[DIFY] Failed documents: {len(issues) - issues_processed}")
            else:
                logger.info(f"[DIFY] Successfully created documents: {len(responses)}")
                logger.info(f"[DIFY] Failed documents: {len(issues) - len(responses)}")
            logger.info(f"[DIFY] ===== END INGESTION =====")
            return responses
        except Exception as e:
            error_msg = f"[DIFY] Error in ingest_issues: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            raise

    def _ingest_summary_file(self, data: dict, file_path: str) -> List[dict]:
        """
        Process a summary file as multiple documents, one for each major field
        Uses the current Dify API contract (process_rule structure)
        """
        try:
            logger.info("[DIFY] Formatting summary fields as separate documents")
            project_name = Path(file_path).stem.replace('_SUMMARY', '')
            fields = data.get('fields', {})
            responses = []
            url = f"{self.base_url}/datasets/{self.dataset_id}/document/create-by-text"
            
            # Define the fields to ingest and their descriptions
            field_map = [
                ("summary", f"Summary of the project {project_name} is:", fields.get("summary")),
                ("contributors", f"Contributors of the project {project_name} are:", ", ".join(fields.get("contributors", []))),
                ("assignees", f"Assignees of the project {project_name} are:", ", ".join(fields.get("assignees", []))),
                ("reporters", f"Reporters of the project {project_name} are:", ", ".join(fields.get("reporters", []))),
                ("issue_count", f"Issue count of the project {project_name} is:", str(fields.get("issue_count")) if fields.get("issue_count") is not None else None),
                ("type", f"Type of the project {project_name} is:", str(fields.get("type")) if fields.get("type") else None),
            ]
            
            for field, label, value in field_map:
                if value and value.strip():
                    text = f"{label}\n{value}"
                    max_tokens, chunk_overlap = self._get_chunk_params(text)
                    
                    # Use the current Dify API contract (same structure as _format_issue_for_text)
                    process_rule = {
                        "mode": "automatic",
                        "rules": {
                            "pre_processing_rules": [
                                {
                                    "id": "remove_extra_spaces",
                                    "enabled": True
                                }
                            ],
                            "segmentation": {
                                "separator": "\n\n",
                                "max_tokens": max_tokens
                            },
                            "parent_mode": "full-doc",
                            "subchunk_segmentation": {
                                "separator": "\n\n",
                                "max_tokens": max_tokens,
                                "chunk_overlap": chunk_overlap
                            }
                        }
                    }
                    
                    doc = {
                        "name": f"{label[:60]}",
                        "text": text,
                        "indexing_technique": "high_quality",
                        "doc_form": "text_model",
                        "doc_language": "English",
                        "process_rule": process_rule,
                        "retrieval_model": {
                            "search_method": "hybrid_search",
                            "reranking_enable": False,
                            "top_k": 8,
                            "score_threshold_enabled": True,
                            "score_threshold": 0.5
                        }
                    }
                    logger.info(f"[DIFY] Creating document for field '{field}': POST {url}")
                    logger.info(f"[DIFY] Full request body: {json.dumps(doc)}")
                    response = requests.post(url, headers=self.headers, json=doc)
                    logger.info(f"[DIFY] Create document response {response.status_code}: {response.text}")
                    response.raise_for_status()
                    responses.append(response.json())
            return responses
        except Exception as e:
            error_msg = f"[DIFY] Error processing summary file: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            raise

# ===== FASTAPI APP =====
app = FastAPI(
    title="Classroom Jira-Dify Integration API",
    description="RESTful API for students to ingest Jira issues into their individual Dify instances. Supports project-based ingestion from JSON files.",
    version="2.1.0",
    tags_metadata=[
        {
            "name": "System",
            "description": "System health and connection testing endpoints"
        },
        {
            "name": "Projects", 
            "description": "Project management and listing endpoints"
        },
        {
            "name": "Ingestion",
            "description": "Jira issues ingestion into Dify datasets"
        },
        {
            "name": "Dify Management",
            "description": "Dify instance status and dataset management"
        }
    ]
)

@app.on_event("startup")
def startup_event():
    load_dotenv()
    logger.info("Environment variables loaded.")

@app.get("/health", tags=["System"])
def get_health():
    """GET /health - Health check endpoint"""
    return {
        "status": "healthy",
        "service": "classroom-jira-dify-api",
        "version": "2.1.0",
        "endpoints": [
            "GET /health",
            "GET /projects", 
            "POST /jira/ingest",
            "GET /connections",
            "GET /dify/status",
            "GET /dify/datasets"
        ]
    }

@app.get("/projects", tags=["Projects"])
def get_projects():
    """GET /projects - Retrieve all available project names for ingestion"""
    try:
        dataset_dir = Path("data")
        if not dataset_dir.exists():
            return {"error": "Dataset directory not found"}
        
        # Get all JSON files in the dataset directory
        json_files = list(dataset_dir.glob("*.json"))
        
        # Extract project names from filenames
        project_names = []
        
        for file_path in json_files:
            filename = file_path.name
            
            # Skip summary files
            if filename.endswith('_SUMMARY.json'):
                continue
                
            # Extract project name from filename
            # e.g., "TOC_JiraEcosystem_issues.json" -> "TOC_JiraEcosystem_issues"
            if filename.endswith('.json'):
                project_name = filename[:-5]  # Remove .json extension
                project_names.append(project_name)
        
        return {
            "projects": project_names,
            "total_projects": len(project_names),
            "dataset_directory": str(dataset_dir)
        }
    except Exception as e:
        logger.error(f"Error getting projects: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/jira/ingest", tags=["Ingestion"])
def create_jira_ingestion(
    request: IngestJiraRequest, 
    dify_config: StudentDifyConfig,
    advanced_ingestion: bool = Query(False, description="Enable advanced ingestion (aliases and queries)?")
):
    """POST /jira/ingest - Ingest issues from JSON file into student's Dify instance"""
    results = []
    errors = []
    try:
        logger.info(f"Processing JSON file ingestion for Dify instance: {dify_config.dify_base_url}")
        
        # Use student's specific Dify configuration
        dify = DifyIntegration(
            api_key=dify_config.dify_api_key,
            base_url=dify_config.dify_base_url,
            dataset_id=dify_config.dataset_id,
            advanced_ingestion=advanced_ingestion
        )
        
        # Construct the JSON file path
        dataset_dir = Path("data")
        json_file_path = dataset_dir / f"{request.project}.json"
        
        if not json_file_path.exists():
            error_msg = f"Project file not found: {request.project}.json"
            logger.error(error_msg)
            errors.append({"file": request.project, "error": error_msg})
            return {
                "success": False,
                "dify_instance": dify_config.dify_base_url,
                "files_processed": len(results),
                "files_failed": len(errors),
                "results": results,
                "errors": errors
            }
        
        logger.info(f"Starting JSON ingestion for file: {json_file_path}")
        
        try:
            # Ingest the JSON file
            result = dify.ingest_json_file(str(json_file_path), advanced_ingestion=advanced_ingestion)
            
            # Count the number of issues ingested
            # If metadata is attached, each issue creates 2 responses (document + metadata)
            # Otherwise, each issue creates 1 response
            if result:
                # Try to determine if metadata was attached by checking response count
                # For now, we'll use a simple heuristic: if responses are even and > 0, assume metadata
                issues_ingested = len(result) // 2 if len(result) % 2 == 0 and len(result) > 0 else len(result)
            else:
                issues_ingested = 0
            
            results.append({
                "file": request.project,
                "result": result,
                "issues_ingested": issues_ingested
            })
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON format in file {json_file_path}: {str(e)}"
            logger.error(error_msg)
            errors.append({"file": request.project, "error": error_msg})
        except Exception as e:
            error_msg = f"Error during Dify ingestion: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            errors.append({"file": request.project, "error": error_msg})
        
        return {
            "success": len(errors) == 0,
            "dify_instance": dify_config.dify_base_url,
            "files_processed": len(results),
            "files_failed": len(errors),
            "results": results,
            "errors": errors
        }
    except Exception as e:
        logger.error(f"Error ingesting from JSON file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/connections", tags=["System"])
def get_connections(dify_config: StudentDifyConfig):
    """GET /connections - Test connections to Jira and student's Dify instance"""
    results = {"jira": False, "dify": False, "errors": {}}
    
    try:
        # Test student's specific Dify instance
        dify = DifyIntegration(
            api_key=dify_config.dify_api_key,
            base_url=dify_config.dify_base_url,
            dataset_id=dify_config.dataset_id
        )
        url = f"{dify.base_url}/datasets"
        r = requests.get(url, headers=dify.headers)
        r.raise_for_status()
        results["dify"] = True
        results["dify_info"] = {
            "base_url": dify_config.dify_base_url,
            "dataset_id": dify_config.dataset_id
        }
    except Exception as e:
        results["errors"]["dify"] = str(e)
    
    return results

@app.get("/dify/status", tags=["Dify Management"])
def get_dify_status(
    dify_base_url: str = Query(..., description="Dify base URL"),
    dify_api_key: str = Query(..., description="Dify API key"),
    dataset_id: str = Query(None, description="Optional dataset ID to check")
):
    """GET /dify/status - Get the status of the student's Dify instance"""
    try:
        dify = DifyIntegration(
            api_key=dify_api_key,
            base_url=dify_base_url,
            dataset_id=dataset_id
        )
        
        # Test connection to student's Dify instance
        url = f"{dify.base_url}/datasets"
        r = requests.get(url, headers=dify.headers)
        r.raise_for_status()
        
        # Get list of datasets to verify the dataset ID exists
        datasets = r.json()
        logger.info(f"[DIFY] Available datasets: {json.dumps(datasets, indent=2)}")
        
        # Check if the specified dataset ID exists (if provided)
        dataset_exists = None
        if dataset_id and 'data' in datasets:
            for dataset in datasets['data']:
                if dataset.get('id') == dataset_id:
                    dataset_exists = True
                    logger.info(f"[DIFY] Found dataset: {dataset}")
                    break
            if dataset_exists is None:
                dataset_exists = False
        
        return {
            "status": "connected",
            "dify_base_url": dify_base_url,
            "dataset_id": dataset_id,
            "dataset_exists": dataset_exists,
            "available_datasets": datasets.get('data', []) if 'data' in datasets else []
        }
    except Exception as e:
        logger.error(f"[DIFY] Error checking Dify status: {str(e)}")
        return {
            "status": "error",
            "dify_base_url": dify_base_url,
            "error": str(e)
        }

@app.get("/dify/datasets", tags=["Dify Management"])
def get_dify_datasets(
    dify_base_url: str = Query(..., description="Dify base URL"),
    dify_api_key: str = Query(..., description="Dify API key")
):
    """GET /dify/datasets - Get all available datasets in the student's Dify instance"""
    try:
        dify = DifyIntegration(
            api_key=dify_api_key,
            base_url=dify_base_url,
            dataset_id=None  # Not needed for listing datasets
        )
        
        # Get list of datasets
        url = f"{dify.base_url}/datasets"
        r = requests.get(url, headers=dify.headers)
        r.raise_for_status()
        
        datasets = r.json()
        logger.info(f"[DIFY] Retrieved {len(datasets.get('data', []))} datasets")
        
        # Format the response with useful information
        formatted_datasets = []
        if 'data' in datasets:
            for dataset in datasets['data']:
                formatted_dataset = {
                    "id": dataset.get('id'),
                    "name": dataset.get('name'),
                    "description": dataset.get('description'),
                    "permission": dataset.get('permission'),
                    "indexing_technique": dataset.get('indexing_technique'),
                    "document_count": dataset.get('document_count', 0),
                    "word_count": dataset.get('word_count', 0),
                    "created_at": dataset.get('created_at'),
                    "embedding_model": dataset.get('embedding_model'),
                    "embedding_model_provider": dataset.get('embedding_model_provider')
                }
                formatted_datasets.append(formatted_dataset)
        
        return {
            "status": "success",
            "dify_base_url": dify_base_url,
            "total_datasets": len(formatted_datasets),
            "datasets": formatted_datasets,
            "raw_response": datasets
        }
    except Exception as e:
        logger.error(f"[DIFY] Error getting datasets: {str(e)}")
        return {
            "status": "error",
            "dify_base_url": dify_base_url,
            "error": str(e)
        }

# ===== LAMBDA HANDLER =====
from mangum import Mangum
handler = Mangum(app, lifespan="off")

def lambda_handler(event, context):
    """AWS Lambda handler for the dify_jira API."""
    try:
        logger.info(f"Processing request: {event.get('httpMethod', 'UNKNOWN')} {event.get('path', 'UNKNOWN')}")
        
        response = handler(event, context)
        
        # Add CORS headers
        if 'headers' not in response:
            response['headers'] = {}
        
        response['headers'].update({
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        })
        
        return response
        
    except Exception as e:
        logger.error(f"Lambda error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }
