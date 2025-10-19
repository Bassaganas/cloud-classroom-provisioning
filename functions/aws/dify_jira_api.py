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
    """Model for Jira ingestion requests."""
    project: Optional[str] = None
    jql: Optional[str] = None
    max_results: Optional[int] = 100

class IngestJsonRequest(BaseModel):
    """Model for JSON file ingestion requests."""
    file_names: List[str]  # List of file names
    dataset_dir: Optional[str] = "data"

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
            'Content-Type': 'application/json'
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
            max_tokens, chunk_overlap = 2000, 400
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

    def create_dataset(self, name: str = None, permission: str = "only_me", search_method: str = "hybrid_search", advanced_ingestion: bool = False) -> str:
        if name is None:
            mode = "Advanced" if advanced_ingestion else "Basic"
            rand_num = random.randint(100000, 999999)
            name = f"Jira_API_{mode}_{rand_num}"
        url = f"{self.base_url}/datasets"
        data = {
            "name": name,
            "permission": permission,
            "indexing_technique": "high_quality",
            "embedding_model": "text-embedding-ada-002",
            "retrieval_model": {
                "search_method": search_method,
                "reranking_enable": False,
                "top_k": 8,
                "score_threshold_enabled": True,
                "score_threshold": 0.5
            }
        }
        try:
            logger.info(f"[DIFY] Creating dataset: POST {url} {data}")
            response = requests.post(url, headers=self.headers, json=data)
            logger.info(f"[DIFY] Response {response.status_code}: {response.text}")
            response.raise_for_status()
            dataset_info = response.json()
            logger.info(f"[DIFY] Dataset created: id={dataset_info['id']}, name={dataset_info['name']}")
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
            logger.info(f"[DIFY] Starting ingestion of {len(issues)} issues")
            
            for idx, issue in enumerate(issues, 1):
                try:
                    logger.info(f"[DIFY] Processing issue {idx}/{len(issues)}: {issue.get('key', 'unknown')}")
                    url = f"{self.base_url}/datasets/{self.dataset_id}/document/create-by-text"
                    data = self._format_issue_for_text(issue, advanced_ingestion=advanced_ingestion)
                    logger.debug(f"[DIFY] Formatted issue data: {json.dumps(data, indent=2)}")
                    
                    logger.info(f"[DIFY] Creating document: POST {url}")
                    response = requests.post(url, headers=self.headers, json=data)
                    logger.debug(f"[DIFY] Create document response: {response.text}")
                    response.raise_for_status()
                    responses.append(response.json())
                    
                except Exception as e:
                    error_msg = f"[DIFY] Error processing issue {idx}: {str(e)}"
                    logger.error(f"{error_msg}\n{traceback.format_exc()}")
                    continue
                    
            logger.info(f"[DIFY] Completed ingestion. Successfully processed {len(responses)} issues")
            return responses
        except Exception as e:
            error_msg = f"[DIFY] Error in ingest_issues: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            raise

# ===== FASTAPI APP =====
app = FastAPI(
    title="Classroom Jira-Dify Integration API",
    description="RESTful API for students to ingest Jira issues into their individual Dify instances",
    version="2.0.0"
)

@app.on_event("startup")
def startup_event():
    load_dotenv()
    logger.info("Environment variables loaded.")

@app.get("/health")
def get_health():
    """GET /health - Health check endpoint"""
    return {
        "status": "healthy",
        "service": "classroom-jira-dify-api",
        "version": "2.0.0"
    }

@app.get("/projects")
def get_projects():
    """GET /projects - Retrieve all available JSON project files for ingestion"""
    try:
        dataset_dir = Path("data")
        if not dataset_dir.exists():
            return {"error": "Dataset directory not found"}
        
        # Get all JSON files in the dataset directory
        json_files = list(dataset_dir.glob("*.json"))
        
        # Categorize files
        issue_files = []
        summary_files = []
        
        for file_path in json_files:
            file_info = {
                "filename": file_path.name,
                "size": file_path.stat().st_size,
                "modified": file_path.stat().st_mtime
            }
            
            if file_path.name.endswith('_SUMMARY.json'):
                summary_files.append(file_info)
            else:
                issue_files.append(file_info)
        
        return {
            "projects": {
                "issue_files": issue_files,
                "summary_files": summary_files,
                "total_files": len(json_files)
            },
            "dataset_directory": str(dataset_dir)
        }
    except Exception as e:
        logger.error(f"Error getting projects: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/jira/ingest")
def create_jira_ingestion(
    request: IngestJiraRequest, 
    dify_config: StudentDifyConfig,
    advanced_ingestion: bool = Query(False, description="Enable advanced ingestion (aliases and queries)?")
):
    """POST /jira/ingest - Ingest issues from Jira into student's Dify instance"""
    try:
        logger.info(f"Processing Jira ingestion for Dify instance: {dify_config.dify_base_url}")
        
        # Use student's specific Dify configuration
        dify = DifyIntegration(
            api_key=dify_config.dify_api_key,
            base_url=dify_config.dify_base_url,
            dataset_id=dify_config.dataset_id,
            advanced_ingestion=advanced_ingestion
        )
        
        # For now, return a mock response since we don't have Jira client integration
        return {
            "success": True, 
            "dify_instance": dify_config.dify_base_url,
            "issues_ingested": 0,
            "message": "Jira ingestion endpoint ready (Jira client integration pending)"
        }
    except Exception as e:
        logger.error(f"Error ingesting from Jira: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/json/ingest")
def create_json_ingestion(
    request: IngestJsonRequest, 
    dify_config: StudentDifyConfig,
    advanced_ingestion: bool = Query(False, description="Enable advanced ingestion (aliases and queries)?")
):
    """POST /json/ingest - Ingest issues from JSON files into student's Dify instance"""
    results = []
    errors = []
    try:
        logger.info(f"Processing JSON ingestion for Dify instance: {dify_config.dify_base_url}")
        
        # Use student's specific Dify configuration
        dify = DifyIntegration(
            api_key=dify_config.dify_api_key,
            base_url=dify_config.dify_base_url,
            dataset_id=dify_config.dataset_id,
            advanced_ingestion=advanced_ingestion
        )
        
        dataset_dir = Path(request.dataset_dir)
        for file_name in request.file_names:
            try:
                logger.info(f"Starting JSON ingestion for file: {file_name}")
                file_path = dataset_dir / file_name

                if not file_path.exists():
                    error_msg = f"File not found: {file_path}"
                    logger.error(error_msg)
                    errors.append({"file": file_name, "error": error_msg})
                    continue

                logger.info(f"File found. Attempting to ingest JSON file: {file_path}")
                try:
                    result = dify.ingest_json_file(str(file_path), advanced_ingestion=advanced_ingestion)
                    logger.info(f"Successfully ingested JSON file. Result: {result}")
                    results.append({"file": file_name, "result": result})
                except json.JSONDecodeError as e:
                    error_msg = f"Invalid JSON format in file {file_path}: {str(e)}"
                    logger.error(error_msg)
                    errors.append({"file": file_name, "error": error_msg})
                except Exception as e:
                    error_msg = f"Error during Dify ingestion: {str(e)}"
                    logger.error(f"{error_msg}\n{traceback.format_exc()}")
                    errors.append({"file": file_name, "error": error_msg})
            except Exception as e:
                error_msg = f"Unexpected error during JSON ingestion for file {file_name}: {str(e)}"
                logger.error(f"{error_msg}\n{traceback.format_exc()}")
                errors.append({"file": file_name, "error": error_msg})
        
        return {
            "success": len(errors) == 0, 
            "dify_instance": dify_config.dify_base_url,
            "files_processed": len(results),
            "files_failed": len(errors),
            "results": results, 
            "errors": errors
        }
    except Exception as e:
        logger.error(f"Error ingesting from JSON: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/connections")
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

@app.get("/dify/status")
def get_dify_status(dify_config: StudentDifyConfig):
    """GET /dify/status - Get the status of the student's Dify instance"""
    try:
        dify = DifyIntegration(
            api_key=dify_config.dify_api_key,
            base_url=dify_config.dify_base_url,
            dataset_id=dify_config.dataset_id
        )
        
        # Test connection to student's Dify instance
        url = f"{dify.base_url}/datasets"
        r = requests.get(url, headers=dify.headers)
        r.raise_for_status()
        
        return {
            "status": "connected",
            "dify_base_url": dify_config.dify_base_url,
            "dataset_id": dify_config.dataset_id
        }
    except Exception as e:
        return {
            "status": "error",
            "dify_base_url": dify_config.dify_base_url,
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
