from typing import List, Optional
import torch
from sentence_transformers import SentenceTransformer, util
from app.schemas import Resume,RankedResumeOut, RecommendedJob, JobDescription
from app.services.mongoDB_service import MongoService

class ResumeRanker:
    def __init__(
        self,
        model_name: Optional[str] = None,
        batch_size: int = 32,
        device: Optional[str] = None,
    ):
        if model_name is None:
            model_name = "Qwen/Qwen3-Embedding-0.6B"
        else:
            model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.batch_size = batch_size
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        # try to move model (some wrappers ignore .to())
        try:
            self.model.to(self.device)
        except Exception:
            pass

    @staticmethod
    def _serialize_resume(r: Resume) -> str:
        parts = []
        if getattr(r, "summary", None):
            parts.append(f"Summary: {r.summary}")

        if getattr(r, "experience", None):
            exp_strs = []
            for e in r.experience:
                exp_parts = [getattr(e, "title", ""), getattr(e, "company", "")]
                if getattr(e, "description", None):
                    exp_parts.append(e.description)
                exp_strs.append(" | ".join(p.strip() for p in exp_parts if p))
            if exp_strs:
                parts.append("Experience: " + " || ".join(exp_strs))

        if getattr(r, "skills", None):
            skill_strs = [s.name for s in r.skills if getattr(s, "name", None)]
            if skill_strs:
                parts.append("Skills: " + ", ".join(skill_strs))

        return "\n".join(parts)

    def encode_texts(self, texts: List[str]):
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            convert_to_tensor=True,
            show_progress_bar=False,
            device=self.device,
        )
        # ensure tensor on desired device
        try:
            if embeddings.device.type != torch.device(self.device).type:
                embeddings = embeddings.to(self.device)
        except Exception:
            pass
        return embeddings

    def rank_resumes_by_similarity(
        self,
        job_description: str,
        resumes: List[Resume],
        job_id: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> List[RankedResumeOut]:
        """
        Rank resumes by cosine similarity to the job_description and return
        a list of RankedResumeOut objects matching your requested schema.

        - job_id: optional id of the job (string). If provided, it will be used
                  in recommended_jobs.job_id for each returned resume.
        - top_k: optional limit on number of resumes to return.
        """
        # Serialize resumes
        resume_texts = [self._serialize_resume(r) for r in resumes]

        # Encode
        job_emb = self.encode_texts([job_description])           # (1, dim)
        resume_embs = self.encode_texts(resume_texts)            # (N, dim)

        # Cosine similarities (1, N) -> squeeze -> (N,)
        cos_scores = util.cos_sim(job_emb, resume_embs).squeeze(0)
        scores_cpu = cos_scores.cpu()

        # Sort indices by descending score
        sorted_indices = torch.argsort(scores_cpu, descending=True).tolist()
        if top_k is not None:
            sorted_indices = sorted_indices[:top_k]

        out: List[RankedResumeOut] = []
        for rank_position, i in enumerate(sorted_indices, start=1):
            r = resumes[i]
            score = float(scores_cpu[i].item())

            # best-effort extraction of ids and name fields
            candidate_id = getattr(r, "id", None) 
            owner = getattr(r, "owner", None)

            # name resolution: prefer fullName, otherwise join firstName + lastName
            name = getattr(r, "fullName", None)
            if not name:
                fn = getattr(r, "firstName", None) or ""
                ln = getattr(r, "lastName", None) or ""
                name = (fn + " " + ln).strip() or None

            # Build recommended_jobs list — currently single job (rank=1)
            jid = job_id if job_id is not None else "unknown"
            recommended_jobs = [RecommendedJob(job_id=str(jid), score=score, rank=1)]

            out.append(
                RankedResumeOut(
                    candidate_id=str(candidate_id) if candidate_id is not None else None,
                    owner=str(owner) if owner is not None else None,
                    name=name,
                    recommended_jobs=recommended_jobs,
                )
            )

        return out
