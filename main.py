from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from api.recommendations import get_recommendations
from api.batch_recommendations import get_batch_recommendations
from models.schemas import RecommendationRequest, RecommendationResponse
from models.batch_models import BatchRecommendationRequest, BatchRecommendationResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Skillevate Recommendation API",
    description="Personalized learning content recommendation system",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "Skillevate Recommendation API",
        "version": "2.0.0",
        "endpoints": {
            "recommendations": "/api/recommendations",
            "batch_recommendations": "/api/batch-recommendations"
        }
    }

@app.post("/api/recommendations", response_model=RecommendationResponse)
async def recommend_courses(request: RecommendationRequest):
    """
    Get personalized course recommendations based on user skills and preferences.
    
    **Note:** This endpoint is maintained for backward compatibility.
    For new integrations, use /api/batch-recommendations which supports multiple skills.
    """
    try:
        logger.info(f"Received recommendation request for skill: {request.skill}")
        recommendations = await get_recommendations(request)
        return recommendations
    except Exception as e:
        logger.error(f"Error processing recommendation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/batch-recommendations", response_model=BatchRecommendationResponse)
async def batch_recommend_courses(request: BatchRecommendationRequest):
    """
    Get personalized course recommendations for multiple skills in a single request.
    
    This endpoint supports:
    - Multiple skills with per-skill preferences
    - Language filtering across all skills
    - Shared max_results parameter
    - Enhanced preferences (career goals, learning styles, time commitments, technologies)
    
    Example request:
    ```json
    {
        "skills": [
            {
                "skill": "python",
                "preferences": ["Backend Developer", "FastAPI"]
            },
            {
                "skill": "docker",
                "preferences": ["Backend Developer", "microservices"]
            }
        ],
        "max_results": 10,
        "language": "en"
    }
    ```
    """
    try:
        logger.info(f"Received batch recommendation request for {len(request.skills)} skills")
        recommendations = await get_batch_recommendations(request)
        return recommendations
    except Exception as e:
        logger.error(f"Error processing batch recommendation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
