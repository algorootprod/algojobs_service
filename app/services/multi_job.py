# app/services/multi_job_ranking_service.py
from typing import List, Dict, Any, Optional, Tuple, Union
from collections import defaultdict
import logging
from app.services.mongoDB_service import MongoService
from app.schemas import Resume, RankedResumeOut, RecommendedJob, JobDescription, Job
from app.services.ranking_service import ResumeRanker  # or the actual import path of ResumeRanker
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class MultiJobRankingService:
    """
    For multiple Job (top-level) objects, rank resumes for each job,
    pick top_k_per_job resumes per job (per-job candidateCap applied), aggregate per-candidate
    recommended_jobs, and upsert.

    Behaviors:
      - Reads candidateFilters and candidateCap (camelCase) from each job.
      - If candidateCap not present, defaults to 10.
      - Uses candidateFilters when fetching resumes for that job.
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

    def _jobtemplate_to_text(self, job: Union[JobDescription, Dict[str, Any]]) -> str:
        if isinstance(job, dict):
            jd = job
            templateTitle = jd.get("templateTitle")
            templateDescription = jd.get("templateDescription")
            jobSummary = jd.get("jobSummary")
            skills = jd.get("skills", []) or []
        else:
            templateTitle = getattr(job, "templateTitle", None)
            templateDescription = getattr(job, "templateDescription", None)
            jobSummary = getattr(job, "jobSummary", None)
            skills = getattr(job, "skills", None) or []

        parts = []
        if templateTitle:
            parts.append(str(templateTitle))
        if templateDescription:
            parts.append(str(templateDescription))
        if jobSummary:
            parts.append(str(jobSummary))
        if isinstance(skills, (list, tuple)) and skills:
            parts.append("Skills: " + ", ".join(map(str, skills)))
        return "\n\n".join(parts).strip() or (templateTitle or jobSummary or "")

    def _load_and_validate_resumes(self, candidate_filter: Optional[Dict[str, Any]] = None) -> List[Resume]:
        raw_docs = self.mongo.get_all_resumes(filter_query=candidate_filter or {}, limit=0)
        resumes: List[Resume] = []
        for d in raw_docs:
            try:
                if isinstance(d, Resume):
                    resumes.append(d)
                else:
                    if hasattr(Resume, "model_validate"):
                        resumes.append(Resume.model_validate(d))
                    else:
                        resumes.append(Resume.parse_obj(d))
            except Exception:
                logger.exception("Skipping invalid candidate doc (id=%s)", d.get("_id") or d.get("candidate_id"))
        logger.info("Loaded %d valid resumes for ranking (filter=%r)", len(resumes), candidate_filter)
        return resumes

    def _extract_candidate_filters_and_cap(
        self, j_orig: Union[Job, Dict[str, Any], JobDescription]
    ) -> Tuple[Optional[Dict[str, Any]], int]:
        """
        Extract candidateFilters (dict) and candidateCap (int) from a job.
        Supports:
          - top-level camelCase candidateFilters / candidateCap
          - nested jobDescription.candidateFilters / jobDescription.candidateCap
          - pydantic model attributes or raw dicts

        Returns: (filters_dict_or_None, candidate_cap_int)
        """
        candidate_filter: Optional[Dict[str, Any]] = None
        candidate_cap: Optional[int] = None

        # helper to read from dict-like
        def read_from_dict(d: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[int]]:
            f = None
            c = None
            if "candidateFilters" in d and isinstance(d["candidateFilters"], dict):
                f = d["candidateFilters"]
            # candidateCap may be top-level int/str
            if "candidateCap" in d:
                try:
                    c = int(d["candidateCap"])
                except Exception:
                    c = None
            return f, c

        # dict-like object
        if isinstance(j_orig, dict):
            f, c = read_from_dict(j_orig)
            if f is not None:
                candidate_filter = f
            if c is not None:
                candidate_cap = c
            # try nested jobDescription
            jd = j_orig.get("jobDescription")
            if isinstance(jd, dict):
                f2, c2 = read_from_dict(jd)
                if candidate_filter is None and f2 is not None:
                    candidate_filter = f2
                if candidate_cap is None and c2 is not None:
                    candidate_cap = c2
            return candidate_filter, int(candidate_cap) if candidate_cap is not None else self.top_k_per_job

        # pydantic/model-like
        # try direct attributes (camelCase)
        for attr in ("candidateFilters",):
            val = getattr(j_orig, attr, None)
            if isinstance(val, dict):
                candidate_filter = val
        # candidateCap attr
        cap_val = getattr(j_orig, "candidateCap", None)
        if cap_val is not None:
            try:
                candidate_cap = int(cap_val)
            except Exception:
                candidate_cap = None

        # nested jobDescription (model or dict)
        jd = getattr(j_orig, "jobDescription", None)
        if jd:
            if isinstance(jd, dict):
                f2 = jd.get("candidateFilters") if isinstance(jd.get("candidateFilters"), dict) else None
                c2 = jd.get("candidateCap", None)
                if candidate_filter is None and f2 is not None:
                    candidate_filter = f2
                if candidate_cap is None and c2 is not None:
                    try:
                        candidate_cap = int(c2)
                    except Exception:
                        candidate_cap = None
            else:
                # model-like nested
                f2 = getattr(jd, "candidateFilters", None)
                if isinstance(f2, dict) and candidate_filter is None:
                    candidate_filter = f2
                c2 = getattr(jd, "candidateCap", None)
                if c2 is not None and candidate_cap is None:
                    try:
                        candidate_cap = int(c2)
                    except Exception:
                        candidate_cap = None

        # final fallback cap default
        final_cap = int(candidate_cap) if candidate_cap is not None else self.top_k_per_job
        return candidate_filter, final_cap

    def rank_all_jobs_and_upsert(
        self,
        jobs: List[Union[Job, Dict[str, Any], JobDescription]],
    ) -> Dict[str, int]:

        candidate_recs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        skipped_jobs = 0

        for j_orig in jobs:
            job_id = ""
            jd_raw = None

            # determine job id and nested jobDescription
            if isinstance(j_orig, dict):
                job_id = str(j_orig.get("_id") or j_orig.get("id") or "")
                jd_raw = j_orig.get("jobDescription") or j_orig
            else:
                job_id = str(getattr(j_orig, "_id", None) or getattr(j_orig, "id", None) or "")
                jd_candidate = getattr(j_orig, "jobDescription", None)
                if jd_candidate is not None:
                    jd_raw = jd_candidate
                elif isinstance(j_orig, JobDescription):
                    jd_raw = j_orig

            if not job_id:
                job_id = str(getattr(j_orig, "doc_id", "") or "")

            if jd_raw is None:
                logger.warning("Job entry missing jobDescription; skipping. job_repr=%r", j_orig)
                skipped_jobs += 1
                continue

            # normalize nested jobDescription
            if not isinstance(jd_raw, (JobDescription, dict)):
                try:
                    jd_model = JobDescription.model_validate(jd_raw) if hasattr(JobDescription, "model_validate") else JobDescription.parse_obj(jd_raw)
                    jd_normalized = jd_model
                except Exception:
                    try:
                        jd_normalized = dict(jd_raw.__dict__)
                    except Exception:
                        jd_normalized = jd_raw
            else:
                jd_normalized = jd_raw

            if not job_id:
                logger.warning("Missing parent job id for jobDescription; skipping. jd=%r", jd_normalized)
                skipped_jobs += 1
                continue

            # extract candidateFilters and candidateCap (cap used as per-job top_k)
            job_candidate_filter, job_cap = self._extract_candidate_filters_and_cap(j_orig)
            logger.info("Job %s: candidate_filter=%r candidateCap=%d", job_id, job_candidate_filter, job_cap)

            # fetch resumes applying job-specific filter
            resumes = self._load_and_validate_resumes(candidate_filter=job_candidate_filter)
            if not resumes:
                logger.warning("No resumes returned for job %s (filter=%r); skipping job", job_id, job_candidate_filter)
                skipped_jobs += 1
                continue

            # convert job_cap to int and ensure positive
            try:
                job_top_k = max(1, int(job_cap))
            except Exception:
                job_top_k = self.top_k_per_job

            # build job text
            job_text = self._jobtemplate_to_text(jd_normalized)

            try:
                ranked: List[RankedResumeOut] = self.ranker.rank_resumes_by_similarity(
                    job_description=job_text,
                    resumes=resumes,
                    job_id=job_id,
                    top_k=job_top_k,
                )
            except Exception:
                logger.exception("Ranker failed for job_id=%s; skipping", job_id)
                skipped_jobs += 1
                continue

            # collect recommendations
            for rec_idx, rr in enumerate(ranked, start=1):
                try:
                    cand_id = rr.candidate_id
                    if not cand_id:
                        continue

                    # defensive access to recommended_jobs
                    first_reco = None
                    if getattr(rr, "recommended_jobs", None):
                        first_reco = rr.recommended_jobs[0]
                    elif isinstance(rr, dict) and rr.get("recommended_jobs"):
                        first_reco = rr["recommended_jobs"][0]
                    else:
                        logger.warning("No recommended_jobs in RankedResumeOut for job %s, rr=%r", job_id, rr)
                        continue

                    # SAFE extraction of score and rank
                    if isinstance(first_reco, dict):
                        score = float(first_reco.get("score", 0.0))
                        rank_val = int(first_reco.get("rank", rec_idx))
                    else:
                        score = float(getattr(first_reco, "score", 0.0))
                        rank_val = int(getattr(first_reco, "rank", rec_idx))

                    rec_job = {"job_id": job_id, "score": score, "rank": rank_val}
                    candidate_recs.setdefault(str(cand_id), []).append(rec_job)
                except Exception:
                    logger.exception("Malformed RankedResumeOut for job %s: %s", job_id, repr(rr))
                    continue

        # upsert aggregated recommendations per candidate
        upserted = 0
        for cand_id, recs in candidate_recs.items():
            recs_sorted = sorted(recs, key=lambda x: (x["rank"], -x["score"]))
            cand_doc = self.mongo.get_resume_by_id(cand_id)
            cand_owner = (cand_doc.get("owner") if cand_doc else None)
            cand_name = None
            if cand_doc:
                cand_name = cand_doc.get("fullName") or ((cand_doc.get("firstName") or "") + " " + (cand_doc.get("lastName") or ""))

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

    mongo = MongoService(db_name="algojobs")

    jobs= mongo.get_all_jobs(limit=0)
    # print("Job descriptions fetched:", len(jobs))
    # print("First job description:", jobs[0])
    jobs= [Job.model_validate(j) for j in jobs]
    # print("Job templates:", jobs[0].jobDescription)


    service_ranker = MultiJobRankingService(mongo=mongo, ranker=ranker)
    summary = service_ranker.rank_all_jobs_and_upsert(jobs)
    print("Summary:", summary)
    mongo.close()