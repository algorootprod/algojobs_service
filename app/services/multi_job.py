# app/services/multi_job_ranking_service.py
from typing import List, Dict, Any, Optional
from collections import defaultdict
import logging

from app.services.mongoDB_service import MongoService
from app.schemas import Resume, RankedResumeOut, RecommendedJob, JobDescriptionTemplate
from app.services.ranking_service import ResumeRanker  # or the actual import path of ResumeRanker

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class MultiJobRankingService:
    """
    For multiple JobDescriptionTemplate (pydantic) objects, rank all resumes for each job,
    pick top_k_per_job resumes per job, aggregate per-candidate recommended_jobs, and upsert.
    """

    def __init__(
        self,
        mongo: MongoService,
        ranker: ResumeRanker,
        top_k_per_job: int = 10,
    ):
        self.mongo = mongo
        self.ranker = ranker
        self.top_k_per_job = int(top_k_per_job)

    def _jobtemplate_to_text(self, job: JobDescriptionTemplate) -> str:
        """
        Convert a JobDescriptionTemplate model into a plain text string suitable for embedding.
        Prioritizes templateDescription, jobSummary, title and skills.
        """
        parts = []
        if getattr(job, "templateTitle", None):
            parts.append(str(job.templateTitle))
        if getattr(job, "templateDescription", None):
            parts.append(str(job.templateDescription))
        if getattr(job, "jobSummary", None):
            parts.append(str(job.jobSummary))
        # include a skills line if available
        skills = getattr(job, "skills", None) or []
        if isinstance(skills, (list, tuple)) and skills:
            parts.append("Skills: " + ", ".join(map(str, skills)))
        return "\n\n".join(parts).strip() or (job.templateTitle or job.jobSummary or "")

    def _load_and_validate_resumes(self, candidate_filter: Optional[Dict[str, Any]] = None) -> List[Resume]:
        """
        Fetch candidate docs from Mongo, and validate/convert to Pydantic Resume models.
        Skips invalid docs with a warning.
        """
        raw_docs = self.mongo.get_all_resumes(filter_query=candidate_filter or {}, limit=0)
        resumes: List[Resume] = []
        for d in raw_docs:
            try:
                # If d is already a Resume instance, keep it
                if isinstance(d, Resume):
                    resumes.append(d)
                else:
                    # Use Resume.model_validate (pydantic v2) or Resume.parse_obj (v1)
                    # prefer model_validate if available
                    if hasattr(Resume, "model_validate"):
                        resumes.append(Resume.model_validate(d))
                    else:
                        resumes.append(Resume.parse_obj(d))
            except Exception:
                logger.exception("Skipping invalid candidate doc (id=%s)", d.get("_id") or d.get("candidate_id"))
        logger.info("Loaded %d valid resumes for ranking", len(resumes))
        return resumes

    def rank_all_jobs_and_upsert(
        self,
        job_templates: List[JobDescriptionTemplate],
        candidate_filter: Optional[Dict[str, Any]] = None,
        top_k_per_job: Optional[int] = None,
    ) -> Dict[str, int]:
        """
        Main entrypoint:
          - job_templates: list of JobDescriptionTemplate pydantic models
          - candidate_filter: optional filter passed to get_all_resumes
          - owner_id: optional owner id to attach to upserted docs
          - top_k_per_job: override default top_k_per_job for this run

        Returns: summary dict: {"upserted": n, "skipped_jobs": x, "processed_candidates": y}
        """
        if top_k_per_job is None:
            top_k_per_job = self.top_k_per_job
        else:
            top_k_per_job = int(top_k_per_job)

        # 1) load resumes once
        resumes = self._load_and_validate_resumes(candidate_filter=candidate_filter)
        if not resumes:
            logger.warning("No resumes available -- exiting")
            return {"upserted": 0, "skipped_jobs": 0, "processed_candidates": 0}

        # candidate_id -> list of RecommendedJob dicts
        candidate_recs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        skipped_jobs = 0

        # 2) for each job template, create text and rank
        for job in job_templates:
            try:
                job_text = self._jobtemplate_to_text(job)
                job_id = str(getattr(job, "_id", None) or getattr(job, "id", None) or "")
                # job_id=self.mongo.get_job_id_by_jobdescription_id(job_desc_id)  # validate job_id existence

                if not job_id:
                    logger.warning("Job template missing _id; skipping")
                    skipped_jobs += 1
                    continue

                # call the existing ranker (it expects Resume objects and returns RankedResumeOut)
                ranked: List[RankedResumeOut] = self.ranker.rank_resumes_by_similarity(
                    job_description=job_text,
                    resumes=resumes,
                    job_id=job_id,
                    top_k=top_k_per_job,
                )

                # collect top_k_per_job recommendations
                for rec_idx, rr in enumerate(ranked, start=1):
                    # rr is RankedResumeOut (pydantic) or a simple object — normalize access
                    try:
                        cand_id = rr.candidate_id
                        # If candidate_id missing, try to get from candidate Resume object
                        if not cand_id:
                            # fallback: try resume at same rank: ranked list aligns with resumes order returned by ranker
                            continue
                        # recommended job structure (job_id, score, rank)
                        rec_job = {"job_id": job_id, "score": float(rr.recommended_jobs[0].score), "rank": int(rr.recommended_jobs[0].rank)}
                        candidate_recs.setdefault(str(cand_id), []).append(rec_job)
                    except Exception:
                        logger.exception("Malformed RankedResumeOut for job %s: %s", job_id, repr(rr))
                        continue

            except Exception:
                logger.exception("Failed ranking for job template (id=%s); skipping", getattr(job, "_id", None))
                skipped_jobs += 1
                continue

        # 3) Upsert aggregated recommendations per candidate
        upserted = 0
        for cand_id, recs in candidate_recs.items():
            # sort recs by rank (asc) then by score desc
            recs_sorted = sorted(recs, key=lambda x: (x["rank"], -x["score"]))
            # Build RankedResumeOut-like payload for upsert
            # name & owner: try to fetch from candidate doc
            cand_doc = self.mongo.get_resume_by_id(cand_id)
            cand_owner = (cand_doc.get("owner") if cand_doc else None)
            cand_name = None
            if cand_doc:
                cand_name = cand_doc.get("fullName") or (cand_doc.get("firstName") or "") + " " + (cand_doc.get("lastName") or "")

            payload = {
                "candidate_id": cand_id,
                "owner": str(cand_owner) if cand_owner else None,
                "name": cand_name,
                "recommended_jobs": recs_sorted,
            }

            try:
                res = self.mongo.upsert_ranked_resume_out(payload)
                if res:
                    upserted += 1
            except Exception:
                logger.exception("Failed to upsert recommendations for candidate %s", cand_id)

        return {"upserted": upserted, "skipped_jobs": skipped_jobs, "processed_candidates": len(candidate_recs)}

if __name__ == "__main__":
    # Simple test
    ranker = ResumeRanker()

    service = MongoService(db_name="algojobs")

    resumes = service.get_all_resumes(limit=0)
    resumes = [Resume.model_validate(r) for r in resumes]

    service = MongoService(db_name="algo-hr")
    job_desc= service.get_all_jobdescriptions(limit=0)
    job_templates= [JobDescriptionTemplate.model_validate(j) for j in job_desc]
    print("Job templates:", job_templates[0])

    service_ranker = MultiJobRankingService(mongo=service, ranker=ranker, top_k_per_job=10)
    summary = service_ranker.rank_all_jobs_and_upsert(job_templates, candidate_filter=None, top_k_per_job=10)
    print("Summary:", summary)
    service.close()