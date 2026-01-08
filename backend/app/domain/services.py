"""
RecruitAI-Core Domain Services
Business logic for scoring and matching.
"""
from typing import List, Tuple

from .models import Candidate, JobProfile, MatchResult, ScoreBreakdown


class ScoringService:
    """
    Implements the scoring logic for candidate-job matching.
    Uses Reciprocal Rank Fusion (RRF) for combining multiple ranking signals.
    """
    
    RRF_K = 60  # Standard RRF constant
    
    @staticmethod
    def calculate_skills_overlap(
        candidate_skills: List[str],
        required_skills: List[str],
        preferred_skills: List[str]
    ) -> Tuple[float, List[str], List[str]]:
        """
        Calculate skills match score and identify gaps/bonuses.
        
        Returns:
            Tuple of (score, missing_skills, bonus_skills)
        """
        candidate_skills_lower = {s.lower() for s in candidate_skills}
        required_lower = {s.lower() for s in required_skills}
        preferred_lower = {s.lower() for s in preferred_skills}
        
        # Find matches
        required_matches = candidate_skills_lower & required_lower
        preferred_matches = candidate_skills_lower & preferred_lower
        
        # Calculate missing and bonus
        missing_skills = [s for s in required_skills if s.lower() not in candidate_skills_lower]
        bonus_skills = [s for s in candidate_skills if s.lower() in preferred_lower]
        
        # Score calculation
        if not required_skills:
            base_score = 100.0
        else:
            base_score = (len(required_matches) / len(required_skills)) * 100
        
        # Add bonus for preferred skills (up to 20% boost)
        if preferred_skills:
            bonus = (len(preferred_matches) / len(preferred_skills)) * 20
            base_score = min(100, base_score + bonus)
        
        return base_score, missing_skills, bonus_skills
    
    @staticmethod
    def calculate_experience_score(
        candidate_years: float,
        required_years: int
    ) -> float:
        """
        Calculate experience match score.
        100% if meets or exceeds requirement, proportional otherwise.
        """
        if required_years == 0:
            return 100.0
        
        if candidate_years >= required_years:
            # Slight bonus for exceeding, capped at 100
            bonus = min((candidate_years - required_years) * 5, 10)
            return min(100, 90 + bonus)
        
        # Proportional score
        return (candidate_years / required_years) * 100
    
    @staticmethod
    def calculate_education_score(
        candidate_education: str,
        required_level: str
    ) -> float:
        """
        Calculate education match score.
        Simple level comparison.
        """
        if not required_level:
            return 100.0
        
        education_levels = {
            "high_school": 1,
            "associate": 2,
            "bachelor": 3,
            "master": 4,
            "phd": 5
        }
        
        candidate_level = 3  # Default to bachelor
        for level, value in education_levels.items():
            if level in (candidate_education or "").lower():
                candidate_level = value
                break
        
        required_value = education_levels.get(required_level.lower(), 3)
        
        if candidate_level >= required_value:
            return 100.0
        
        # Proportional score
        return (candidate_level / required_value) * 100
    
    @classmethod
    def calculate_match(
        cls,
        candidate: Candidate,
        job: JobProfile
    ) -> MatchResult:
        """
        Calculate comprehensive match result between candidate and job.
        """
        # Skills analysis
        skills_score, missing, bonus = cls.calculate_skills_overlap(
            candidate.skills,
            job.required_skills,
            job.preferred_skills
        )
        
        # Experience score
        exp_score = cls.calculate_experience_score(
            candidate.total_experience_years,
            job.min_experience_years
        )
        
        # Education score
        edu_score = cls.calculate_education_score(
            candidate.highest_education,
            job.education_level.value if job.education_level else None
        )
        
        scores = ScoreBreakdown(
            experience_score=exp_score,
            education_score=edu_score,
            skills_score=skills_score
        )
        
        # Generate explanation
        explanation = cls._generate_explanation(candidate, job, scores, missing, bonus)
        
        return MatchResult(
            candidate_id=candidate.id,
            job_id=job.id,
            scores=scores,
            explanation=explanation,
            missing_skills=missing,
            bonus_skills=bonus
        )
    
    @staticmethod
    def _generate_explanation(
        candidate: Candidate,
        job: JobProfile,
        scores: ScoreBreakdown,
        missing: List[str],
        bonus: List[str]
    ) -> str:
        """Generate human-readable match explanation."""
        parts = []
        
        overall = scores.overall_score
        
        if overall >= 80:
            parts.append(f"Strong match for {job.title}.")
        elif overall >= 60:
            parts.append(f"Good potential fit for {job.title}.")
        else:
            parts.append(f"Partial match for {job.title}.")
        
        # Skills commentary
        if scores.skills_score >= 90:
            parts.append("Excellent skills alignment.")
        elif missing:
            parts.append(f"Missing {len(missing)} required skill(s): {', '.join(missing[:3])}.")
        
        # Experience commentary
        if scores.experience_score >= 100:
            parts.append(f"Exceeds experience requirement with {candidate.total_experience_years} years.")
        elif scores.experience_score < 70:
            parts.append(f"Below experience requirement ({candidate.total_experience_years}/{job.min_experience_years} years).")
        
        # Bonus skills
        if bonus:
            parts.append(f"Bonus: Has preferred skills {', '.join(bonus[:3])}.")
        
        return " ".join(parts)
    
    @classmethod
    def rrf_fusion(
        cls,
        *ranked_lists: List[Tuple[str, float]]
    ) -> List[Tuple[str, float]]:
        """
        Reciprocal Rank Fusion to combine multiple ranking signals.
        
        Args:
            ranked_lists: Multiple lists of (doc_id, score) tuples, sorted by score desc
            
        Returns:
            Fused list of (doc_id, rrf_score) sorted by RRF score desc
        """
        rrf_scores = {}
        
        for ranked_list in ranked_lists:
            for rank, (doc_id, _) in enumerate(ranked_list, start=1):
                if doc_id not in rrf_scores:
                    rrf_scores[doc_id] = 0.0
                rrf_scores[doc_id] += 1.0 / (cls.RRF_K + rank)
        
        # Sort by RRF score descending
        sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_results


class ExplanationService:
    """
    Service for generating detailed explanations for match decisions.
    Implements Glass Box AI principles.
    """
    
    @staticmethod
    def generate_radar_data(scores: ScoreBreakdown) -> dict:
        """
        Generate data structure for radar chart visualization.
        """
        return {
            "axes": [
                {"axis": "Technical Skills", "value": scores.skills_score},
                {"axis": "Experience", "value": scores.experience_score},
                {"axis": "Education", "value": scores.education_score},
                {"axis": "Leadership", "value": 0},  # To be extracted from CV
                {"axis": "Communication", "value": 0},  # To be extracted from CV
            ]
        }
    
    @staticmethod
    def format_gap_analysis(missing: List[str], bonus: List[str]) -> dict:
        """
        Format gap analysis for UI display.
        """
        return {
            "critical_gaps": [{"skill": s, "severity": "high"} for s in missing],
            "bonus_skills": [{"skill": s, "impact": "positive"} for s in bonus],
            "recommendations": [
                f"Consider if {skill} can be learned on the job" 
                for skill in missing[:2]
            ] if missing else []
        }
