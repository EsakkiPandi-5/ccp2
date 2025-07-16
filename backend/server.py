import os
import logging
import base64
import io
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from emergentintegrations.llm.chat import LlmChat, UserMessage, FileContentWithMimeType
import tempfile
import asyncio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Drowsiness Detection API", version="1.0.0")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(MONGO_URL)
db = client.drowsiness_detection

# Gemini API key
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY environment variable is not set")

# Pydantic models
class DrownsinessAnalysisRequest(BaseModel):
    image_data: str
    session_id: str

class DrownsinessAnalysisResponse(BaseModel):
    is_drowsy: bool
    confidence: float
    details: str
    warning_level: str
    recommendations: List[str]

class AnalysisHistory(BaseModel):
    session_id: str
    timestamp: datetime
    is_drowsy: bool
    confidence: float
    details: str

# Initialize Gemini chat
def get_gemini_chat(session_id: str):
    system_message = """You are an expert drowsiness detection system. Analyze the provided image/video frame and determine if the person shows signs of drowsiness while driving.

Look for these drowsiness indicators:
1. Eyes: Are they closed, half-closed, or blinking excessively?
2. Head position: Is the head tilting or nodding?
3. Facial expressions: Signs of yawning, drooping eyelids
4. Overall alertness: General appearance of fatigue

Respond with a JSON object containing:
- is_drowsy: boolean (true if drowsy signs detected)
- confidence: float (0.0 to 1.0 confidence score)
- details: string (specific observations)
- warning_level: string ("LOW", "MEDIUM", "HIGH", "CRITICAL")
- recommendations: array of strings (suggested actions)

Be accurate and prioritize safety."""

    return LlmChat(
        api_key=GEMINI_API_KEY,
        session_id=session_id,
        system_message=system_message
    ).with_model("gemini", "gemini-1.5-flash")

@app.get("/")
async def root():
    return {"message": "Drowsiness Detection API is running"}

@app.post("/api/analyze-drowsiness")
async def analyze_drowsiness(request: DrownsinessAnalysisRequest):
    """Analyze image for drowsiness detection"""
    try:
        # Decode base64 image
        image_data = base64.b64decode(request.image_data.split(',')[1] if ',' in request.image_data else request.image_data)
        
        # Create temporary file for image
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_file.write(image_data)
            temp_file_path = temp_file.name
        
        try:
            # Create file content for Gemini
            image_file = FileContentWithMimeType(
                file_path=temp_file_path,
                mime_type="image/jpeg"
            )
            
            # Initialize Gemini chat
            chat = get_gemini_chat(request.session_id)
            
            # Create message with image
            user_message = UserMessage(
                text="Analyze this image for drowsiness detection. Focus on eyes, head position, and facial expressions that indicate fatigue or sleepiness.",
                file_contents=[image_file]
            )
            
            # Get analysis from Gemini
            response = await chat.send_message(user_message)
            
            # Parse response (assuming JSON format)
            import json
            try:
                analysis_data = json.loads(response)
            except json.JSONDecodeError:
                # If not JSON, create structured response
                analysis_data = {
                    "is_drowsy": "drowsy" in response.lower() or "sleepy" in response.lower() or "tired" in response.lower(),
                    "confidence": 0.7,
                    "details": response,
                    "warning_level": "MEDIUM",
                    "recommendations": ["Take a break", "Rest your eyes", "Get some fresh air"]
                }
            
            # Save analysis to database
            analysis_record = {
                "session_id": request.session_id,
                "timestamp": datetime.utcnow(),
                "is_drowsy": analysis_data.get("is_drowsy", False),
                "confidence": analysis_data.get("confidence", 0.0),
                "details": analysis_data.get("details", ""),
                "warning_level": analysis_data.get("warning_level", "LOW")
            }
            
            await db.analysis_history.insert_one(analysis_record)
            
            return DrownsinessAnalysisResponse(**analysis_data)
            
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)
            
    except Exception as e:
        logger.error(f"Error analyzing drowsiness: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/api/analysis-history/{session_id}")
async def get_analysis_history(session_id: str, limit: int = 50):
    """Get analysis history for a session"""
    try:
        cursor = db.analysis_history.find(
            {"session_id": session_id}
        ).sort("timestamp", -1).limit(limit)
        
        history = await cursor.to_list(length=limit)
        
        # Convert ObjectIds to strings and format response
        for record in history:
            record["_id"] = str(record["_id"])
            record["timestamp"] = record["timestamp"].isoformat()
        
        return {"history": history}
        
    except Exception as e:
        logger.error(f"Error fetching history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch history: {str(e)}")

@app.get("/api/session-stats/{session_id}")
async def get_session_stats(session_id: str):
    """Get statistics for a session"""
    try:
        pipeline = [
            {"$match": {"session_id": session_id}},
            {"$group": {
                "_id": None,
                "total_analyses": {"$sum": 1},
                "drowsy_detections": {"$sum": {"$cond": ["$is_drowsy", 1, 0]}},
                "avg_confidence": {"$avg": "$confidence"},
                "last_analysis": {"$max": "$timestamp"}
            }}
        ]
        
        result = await db.analysis_history.aggregate(pipeline).to_list(length=1)
        
        if result:
            stats = result[0]
            stats["drowsy_percentage"] = (stats["drowsy_detections"] / stats["total_analyses"]) * 100 if stats["total_analyses"] > 0 else 0
            stats["last_analysis"] = stats["last_analysis"].isoformat() if stats["last_analysis"] else None
            del stats["_id"]
            return stats
        else:
            return {
                "total_analyses": 0,
                "drowsy_detections": 0,
                "avg_confidence": 0,
                "drowsy_percentage": 0,
                "last_analysis": None
            }
            
    except Exception as e:
        logger.error(f"Error fetching session stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")

@app.post("/api/start-session")
async def start_session():
    """Start a new monitoring session"""
    try:
        session_id = str(uuid.uuid4())
        
        # Create session record
        session_record = {
            "session_id": session_id,
            "started_at": datetime.utcnow(),
            "status": "active"
        }
        
        await db.sessions.insert_one(session_record)
        
        return {"session_id": session_id, "status": "started"}
        
    except Exception as e:
        logger.error(f"Error starting session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")

@app.post("/api/end-session/{session_id}")
async def end_session(session_id: str):
    """End a monitoring session"""
    try:
        # Update session status
        await db.sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "ended", "ended_at": datetime.utcnow()}}
        )
        
        return {"message": "Session ended successfully"}
        
    except Exception as e:
        logger.error(f"Error ending session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to end session: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)