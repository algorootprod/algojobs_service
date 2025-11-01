import os
from typing import Any, Dict, List, Optional
from pymongo import MongoClient
from bson import ObjectId
import logging
from dotenv import load_dotenv
from app.schemas import RankedResumeOut , CandidateResume
load_dotenv()
from datetime import datetime
from pymongo import ASCENDING, ReturnDocument
from typing import Union
# from app.core.config import config

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MongoService:
    """
    A simple MongoDB service wrapper.

    - Reads connection URI from environment variable MONOGO_DB_URL (fallback to MONGO_DB_URL).
    - Reuses a single MongoClient instance.
    - Provides collection-specific helpers for:
      - candidates (resumes)
      - jobdescriptiontemplates
      - questiontemplates
    """

    def __init__(self,
                 db_name: str = "algojobs",
                 connection_env_names: List[str] = None,
                 **kwargs):
        """
        :param db_name: database name to connect to
        :param connection_env_names: list of env var names to try for connection string
        :param kwargs: forwarded to MongoClient (optional)
        """
        # conn_uri = config.MONGO_DB_URL  # default from config
        conn_uri= os.getenv("MONGO_DB_URL", "mongodb://localhost:27017")
        if not conn_uri:
            raise EnvironmentError(
                f"No MongoDB connection string found in environment variables {connection_env_names}"
            )

        # Create single MongoClient instance (it is thread-safe and recommended to reuse)
        self._client = MongoClient(conn_uri, **kwargs)
        self._db = self._client[db_name]

        # standard collection names (change if needed)
        self.resumes_coll_name = "candidates"
        self.jobdesc_coll_name = "jobdescriptions"
        self.question_coll_name = "questionstemplates"
        self.agents = "agents"
        self.recommendations_coll_name = "recommendations"

        logger.info("MongoService connected to database '%s'", db_name)

    def close(self) -> None:
        """Close the underlying MongoClient."""
        try:
            self._client.close()
            logger.info("MongoClient closed")
        except Exception as e:
            logger.exception("Error closing MongoClient: %s", e)

    # -----------------------
    # Generic helpers
    # -----------------------
    def _to_datetime_safe(self, date_str: str) -> Optional[datetime]:
        """
        Safely convert a date string to a datetime object.
        Handles ISO formats (YYYY-MM-DD), "Month YYYY", and "Mon YYYY".
        """
        if not date_str or not isinstance(date_str, str):
            return None

        # Handle extra whitespace like 'Nov 2024   '
        date_str = date_str.strip()

        # List of formats to try.
        # %B = Full month name (April), %b = Abbr. month name (Sept)
        formats_to_try = [
            '%Y-%m-%d',    # 2025-04-01
            '%B %Y',       # April 2025
            '%b %Y',       # Apr 2025 (or Sept 2025)
        ]

        for fmt in formats_to_try:
            try:
                # If successful, return the datetime object
                # This will store "April 2025" as datetime(2025, 4, 1)
                return datetime.strptime(date_str, fmt)
            except ValueError:
                # If format fails, just try the next one
                continue
        
        # Try full ISO format as a last resort
        try:
            return datetime.fromisoformat(date_str)
        except Exception:
            pass # Ignore

        # If all formats fail, log the warning and return None
        logger.warning("Could not parse date string (all formats failed): %s", date_str)
        return None

    def _sync_candidate_fields(self, payload: Dict[str, Any]) -> None:
        """
        Applies the same pre-save sync logic from the Mongoose schema
        to ensure data consistency.
        """
        # Sync experienceEntries <-> experiences
        if 'experienceEntries' in payload:
            payload['experiences'] = payload['experienceEntries']
        
        # Sync languageProficiencies <-> languages
        if 'languageProficiencies' in payload:
            payload['languages'] = payload['languageProficiencies']
        
        # Sync educationEntries <-> education
        if 'educationEntries' in payload:
            payload['education'] = payload['educationEntries']

        # Sync fullName <-> firstName/lastName
        fullName = payload.get('fullName')
        firstName = payload.get('firstName')
        lastName = payload.get('lastName')
        if fullName and (not firstName or not lastName):
            parts = fullName.strip().split(None, 1)
            payload['firstName'] = parts[0]
            payload['lastName'] = parts[1] if len(parts) > 1 else ''
        elif not fullName and (firstName or lastName):
            payload['fullName'] = f"{firstName or ''} {lastName or ''}".strip()

        # Sync currentLocation <-> city/state
        if payload.get('currentLocation'):
            if payload['currentLocation'].get('city'):
                payload['city'] = payload['currentLocation']['city']
            if payload['currentLocation'].get('state'):
                payload['state'] = payload['currentLocation']['state']
        elif payload.get('city') or payload.get('state'):
            payload['currentLocation'] = {
                "city": payload.get('city'),
                "state": payload.get('state')
            }
        
        # Sync totalExperienceYears <-> totalExperience
        if 'totalExperienceYears' in payload:
            payload['totalExperience'] = payload['totalExperienceYears']
        elif 'totalExperience' in payload:
            payload['totalExperienceYears'] = payload['totalExperience']

    def _to_objectid(self, value: Any) -> Optional[ObjectId]:
        """
        Convert a value to ObjectId if possible, else return None.
        Accepts ObjectId, str, or None.
        """
        if isinstance(value, ObjectId):
            return value
        if isinstance(value, str):
            try:
                return ObjectId(value)
            except Exception:
                return None
        return None
    
    def _get_collection(self, collection_name: str):
        return self._db[collection_name]

    def _serialize_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert BSON types into JSON-friendly Python types.
        By default, convert ObjectId to str and leave other values as-is.
        """
        if doc is None:
            return None
        out = {}
        for k, v in doc.items():
            if isinstance(v, ObjectId):
                out[k] = str(v)
            else:
                # If there are nested ObjectIds, convert recursively
                if isinstance(v, dict):
                    out[k] = self._serialize_document(v)
                elif isinstance(v, list):
                    out_list = []
                    for item in v:
                        if isinstance(item, ObjectId):
                            out_list.append(str(item))
                        elif isinstance(item, dict):
                            out_list.append(self._serialize_document(item))
                        else:
                            out_list.append(item)
                    out[k] = out_list
                else:
                    out[k] = v
        return out

    def get_by_id(self, collection_name: str, object_id: str) -> Optional[Dict[str, Any]]:
        """
        Generic getter by ObjectId string.
        Returns serialized dict or None if not found/invalid id.
        """
        try:
            coll = self._get_collection(collection_name)
            oid = ObjectId(object_id)
            doc = coll.find_one({"_id": oid})
            return self._serialize_document(doc) if doc else None
        except Exception as e:
            logger.exception("Error in get_by_id for collection %s id=%s: %s", collection_name, object_id, e)
            return None

    def get_all(self, collection_name: str, filter_query: Dict[str, Any] = None, limit: int = 0, sort: list = None) -> List[Dict[str, Any]]:
        """
        Generic get-all (with optional filter and limit).
        Returns a list of serialized documents.
        :param collection_name: collection to query
        :param filter_query: pymongo filter dict (default: {})
        :param limit: 0 means no limit; otherwise maximum number of documents
        """
        try:
            coll = self._get_collection(collection_name)
            query = filter_query or {}
            cursor = coll.find(query)
            if sort:
                cursor = cursor.sort(sort)
            if limit and limit > 0:
                cursor = cursor.limit(limit)
            results = [self._serialize_document(doc) for doc in cursor]
            return results
        except Exception as e:
            logger.exception("Error in get_all for collection %s: %s", collection_name, e)
            return []

    # -----------------------
    # Resumes (candidates) specific
    # -----------------------
    def get_resume_by_id(self, object_id: str) -> Optional[Dict[str, Any]]:
        """
        Return a candidate resume document by ObjectId string.
        """
        return self.get_by_id(self.resumes_coll_name, object_id)

    def get_all_resumes(self, filter_query: Dict[str, Any] = None, limit: int = 0) -> List[Dict[str, Any]]:
        """
        Return all candidate resumes (optionally filtered).
        """
        sort=[("createdAt",-1)]
        return self.get_all(self.resumes_coll_name, filter_query, limit,sort)

    # -----------------------
    # Job description templates specific
    # -----------------------
    def get_job_by_id(self, object_id: str) -> Optional[Dict[str, Any]]:
        return self.get_by_id(self.jobdesc_coll_name, object_id)

    def get_all_jobs(self, filter_query: Dict[str, Any] = None, limit: int = 0) -> List[Dict[str, Any]]:
        sort=[("createdAt",-1)]
        return self.get_all(self.jobdesc_coll_name, filter_query, limit, sort)
    

    def get_agent_config_by_id(self, object_id: str) -> Optional[Dict[str, Any]]:
        return self.get_by_id(self.agents, object_id)

    # -----------------------
    # Question templates specific
    # -----------------------
    def get_questiontemplate_by_id(self, object_id: str) -> Optional[Dict[str, Any]]:
        return self.get_by_id(self.question_coll_name, object_id)

    def get_all_questiontemplates(self, filter_query: Dict[str, Any] = None, limit: int = 0) -> List[Dict[str, Any]]:
        return self.get_all(self.question_coll_name, filter_query, limit)

    def upsert_ranked_resume_out(
        self,
        ranked_resume: Union[RankedResumeOut, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Upsert a RankedResumeOut Pydantic model into MongoDB.

        - Converts candidate_id and owner to ObjectId
        - Converts nested job_id in recommended_jobs to ObjectId
        - Stores all fields as-is under same keys
        - Adds createdAt/updatedAt timestamps
        - Returns the updated (serialized) document

        Expected Pydantic model structure:
            {
              candidate_id: str,
              owner: str,
              name: str,
              recommended_jobs: [
                  {"job_id": str, "score": float, "rank": int}
              ]
            }
        """
        coll = self._get_collection(self.recommendations_coll_name)
        now = datetime.utcnow()

        # Convert Pydantic object to dict safely
        if hasattr(ranked_resume, "model_dump"):
            data = ranked_resume.model_dump()
        elif hasattr(ranked_resume, "dict"):
            data = ranked_resume.dict()
        elif isinstance(ranked_resume, dict):
            data = ranked_resume
        else:
            raise TypeError(f"Unsupported type for ranked_resume: {type(ranked_resume)}")

        # Extract and convert ObjectIds
        candidate_oid = self._to_objectid(data.get("candidate_id"))
        owner_oid = self._to_objectid(data.get("owner"))
        name = data.get("name")

        # Normalize recommended_jobs list
        rec_jobs = []
        for j in data.get("recommended_jobs", []):
            job_oid = self._to_objectid(j.get("job_id"))
            rec_jobs.append({
                "job_id": job_oid,
                "score": float(j.get("score", 0.0)),
                "rank": int(j.get("rank", 0)),
            })

        payload = {
            "candidate_id": candidate_oid,
            "owner": owner_oid,
            "name": name,
            "recommended_jobs": rec_jobs,
            "updatedAt": now
        }

        # Upsert operation
        result = coll.find_one_and_update(
            {"candidate_id": candidate_oid},
            {"$set": payload, "$setOnInsert": {"createdAt": now}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

        return self._serialize_document(result) if result else None

    def upsert_resume(
            self, 
            owner_id: str, 
            parsed_data: Union[Dict[str, Any], CandidateResume]
        ) -> Optional[Dict[str, Any]]:
            """
            Upserts a candidate resume based on parsed data.

            - Uses 'owner_id' and 'phone' from parsed_data as the unique key.
            - Applies Mongoose pre-save logic (syncing fields).
            - Converts simplified date strings (from parser) back to datetime objects
            for legacy fields (internships, projects, accomplishments).
            - Returns the serialized, upserted document.
            """
            coll = self._get_collection(self.resumes_coll_name)
            now = datetime.utcnow()

            if hasattr(parsed_data, "model_dump"):
                data = parsed_data.model_dump()
            elif isinstance(parsed_data, dict):
                data = parsed_data
            else:
                logger.error("Unsupported type for parsed_data: %s", type(parsed_data))
                return None

            phone = data.get("phone")
            if not phone:
                logger.error("Cannot upsert resume: 'phone' is missing or empty in parsed data.")
                return None
                
            owner_oid = self._to_objectid(owner_id)
            if not owner_oid:
                logger.error("Cannot upsert resume: 'owner_id' is invalid: %s", owner_id)
                return None

            filter_query = {
                "phone": phone,
                "owner": owner_oid
            }
            
            payload = data.copy()
            self._sync_candidate_fields(payload)
            
            for item in payload.get('internships') or []:
                item['startDate'] = self._to_datetime_safe(item.get('startDate'))
                item['endDate'] = self._to_datetime_safe(item.get('endDate'))
                
            for item in payload.get('projects') or []:
                item['startDate'] = self._to_datetime_safe(item.get('startDate'))
                item['endDate'] = self._to_datetime_safe(item.get('endDate'))

            for item in payload.get('accomplishments') or []:
                item['date'] = self._to_datetime_safe(item.get('date'))
            
            payload['updatedAt'] = now

            if 'phone' in payload:
                del payload['phone']
            if 'owner' in payload:
                del payload['owner'] # 'owner' isn't in parsed_data, but good to have

            update_op = {
                "$set": payload,  # 'payload' no longer contains 'phone'
                "$setOnInsert": {
                    "createdAt": now,
                    "phone": phone, # This is now the *only* operator touching 'phone'
                    "owner": owner_oid # This is the *only* operator touching 'owner'
                }
            }

            try:
                result = coll.find_one_and_update(
                    filter_query,
                    update_op,
                    upsert=True,
                    return_document=ReturnDocument.AFTER,
                )
                logger.info("Successfully upserted resume for phone: %s, owner: %s", phone, owner_id)
                return self._serialize_document(result)
            except Exception as e:
                logger.error("Error upserting resume for phone %s: %s", phone, e)
                raise e