from typing import List
import torch
import torch.nn.functional as F
import numpy as np
from sentence_transformers import SentenceTransformer
from app.schemas import Resume, RankedResume

def _serialize_resume(r:Resume) -> str:
    """Converts a structured Resume object into a single string."""
    parts = []
    if r.summary:
        parts.append(f"Summary: {r.summary}")

    if r.experience:
        exp_strs = []
        for e in r.experience:
            exp_parts = [e.title, e.company]
            if e.description:
                exp_parts.append(e.description)
            exp_strs.append(" | ".join(p.strip() for p in exp_parts if p))
        parts.append("Experience: " + " || ".join(exp_strs))

    if r.skills:
        skill_strs = [s.name for s in r.skills]
        parts.append("Skills: " + ", ".join(skill_strs))
    
    # You can add more fields like projects, education etc. for a more comprehensive text.

    return "\n".join(parts)

def _batch_encode(model: SentenceTransformer, texts: List[str], batch_size: int):
    """Encodes a list of texts in batches."""
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i: i + batch_size]
        embeddings = model.encode(batch, convert_to_tensor=True, show_progress_bar=False)
        all_embeddings.append(embeddings)
    return torch.cat(all_embeddings, dim=0)

def _cosine_similarity_matrix(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    """Calculates cosine similarity between two tensors."""
    a_norm = F.normalize(a, p=2, dim=1)
    b_norm = F.normalize(b, p=2, dim=1)
    return a_norm @ b_norm.T

def rank_resumes_by_similarity(
    model: SentenceTransformer,
    job_description: str,
    resumes: List[Resume],
    batch_size: int
) -> List[RankedResume]:
    """
    Calculates similarity scores and returns a ranked list of resumes.
    """
    # Serialize resume objects to plain text
    resume_texts = [_serialize_resume(r) for r in resumes]

    # Generate embeddings
    job_emb = model.encode([job_description], convert_to_tensor=True, show_progress_bar=False)
    resume_embs = _batch_encode(model, resume_texts, batch_size)

    # Calculate cosine similarity
    similarities = _cosine_similarity_matrix(job_emb, resume_embs).squeeze(0).cpu().numpy()

    # Sort resumes by similarity score
    sorted_indices = np.argsort(-similarities)

    # Create the ranked list of results
    ranked_results = []
    for i in sorted_indices:
        candidate_resume = resumes[i]
        score = float(similarities[i])
        ranked_results.append(
            RankedResume(
                candidate_id=candidate_resume.candidate_id,
                name=candidate_resume.name,
                score=score,
                resume=candidate_resume
            )
        )
        
    return ranked_results

