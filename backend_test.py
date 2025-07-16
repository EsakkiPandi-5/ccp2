#!/usr/bin/env python3
"""
Backend API Testing for Drowsiness Detection System
Tests all API endpoints with realistic data and full workflow
"""

import requests
import base64
import json
import time
import os
from PIL import Image, ImageDraw
import io

# Get backend URL from environment
BACKEND_URL = "https://62f358b9-26a6-4caf-9625-95957f8f3f46.preview.emergentagent.com"

def create_test_image():
    """Create a simple test image and return as base64"""
    # Create a simple test image (face-like)
    img = Image.new('RGB', (200, 200), color='lightblue')
    draw = ImageDraw.Draw(img)
    
    # Draw a simple face
    # Head circle
    draw.ellipse([50, 50, 150, 150], fill='#FFDBAC', outline='black')
    # Eyes
    draw.ellipse([70, 80, 85, 95], fill='white', outline='black')
    draw.ellipse([115, 80, 130, 95], fill='white', outline='black')
    # Eye pupils
    draw.ellipse([75, 85, 80, 90], fill='black')
    draw.ellipse([120, 85, 125, 90], fill='black')
    # Nose
    draw.line([100, 95, 100, 110], fill='black', width=2)
    # Mouth
    draw.arc([85, 115, 115, 135], 0, 180, fill='black', width=2)
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/jpeg;base64,{img_str}"

def test_health_check():
    """Test GET / endpoint"""
    print("🔍 Testing Health Check (GET /)...")
    try:
        response = requests.get(f"{BACKEND_URL}/")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            if "message" in data and "running" in data["message"].lower():
                print("✅ Health check passed")
                return True
            else:
                print("❌ Health check failed - unexpected response format")
                return False
        else:
            print(f"❌ Health check failed - status code {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Health check failed - error: {str(e)}")
        return False

def test_start_session():
    """Test POST /api/start-session endpoint"""
    print("\n🔍 Testing Start Session (POST /api/start-session)...")
    try:
        response = requests.post(f"{BACKEND_URL}/api/start-session")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            if "session_id" in data and "status" in data:
                session_id = data["session_id"]
                print(f"✅ Session started successfully with ID: {session_id}")
                return session_id
            else:
                print("❌ Start session failed - missing required fields")
                return None
        else:
            print(f"❌ Start session failed - status code {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Start session failed - error: {str(e)}")
        return None

def test_analyze_drowsiness(session_id, image_data):
    """Test POST /api/analyze-drowsiness endpoint"""
    print("\n🔍 Testing Analyze Drowsiness (POST /api/analyze-drowsiness)...")
    try:
        payload = {
            "image_data": image_data,
            "session_id": session_id
        }
        
        response = requests.post(f"{BACKEND_URL}/api/analyze-drowsiness", json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            required_fields = ["is_drowsy", "confidence", "details", "warning_level", "recommendations"]
            if all(field in data for field in required_fields):
                print("✅ Drowsiness analysis completed successfully")
                print(f"   - Is Drowsy: {data['is_drowsy']}")
                print(f"   - Confidence: {data['confidence']}")
                print(f"   - Warning Level: {data['warning_level']}")
                return True
            else:
                missing = [f for f in required_fields if f not in data]
                print(f"❌ Analysis failed - missing fields: {missing}")
                return False
        else:
            print(f"❌ Analysis failed - status code {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Analysis failed - error: {str(e)}")
        return False

def test_analysis_history(session_id):
    """Test GET /api/analysis-history/{session_id} endpoint"""
    print(f"\n🔍 Testing Analysis History (GET /api/analysis-history/{session_id})...")
    try:
        response = requests.get(f"{BACKEND_URL}/api/analysis-history/{session_id}")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            if "history" in data and isinstance(data["history"], list):
                print(f"✅ Analysis history retrieved successfully ({len(data['history'])} records)")
                if len(data["history"]) > 0:
                    record = data["history"][0]
                    print(f"   - Latest record timestamp: {record.get('timestamp', 'N/A')}")
                    print(f"   - Latest record drowsy: {record.get('is_drowsy', 'N/A')}")
                return True
            else:
                print("❌ History retrieval failed - invalid response format")
                return False
        else:
            print(f"❌ History retrieval failed - status code {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ History retrieval failed - error: {str(e)}")
        return False

def test_session_stats(session_id):
    """Test GET /api/session-stats/{session_id} endpoint"""
    print(f"\n🔍 Testing Session Stats (GET /api/session-stats/{session_id})...")
    try:
        response = requests.get(f"{BACKEND_URL}/api/session-stats/{session_id}")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            required_fields = ["total_analyses", "drowsy_detections", "avg_confidence", "drowsy_percentage"]
            if all(field in data for field in required_fields):
                print("✅ Session stats retrieved successfully")
                print(f"   - Total Analyses: {data['total_analyses']}")
                print(f"   - Drowsy Detections: {data['drowsy_detections']}")
                print(f"   - Average Confidence: {data['avg_confidence']}")
                print(f"   - Drowsy Percentage: {data['drowsy_percentage']}%")
                return True
            else:
                missing = [f for f in required_fields if f not in data]
                print(f"❌ Stats retrieval failed - missing fields: {missing}")
                return False
        else:
            print(f"❌ Stats retrieval failed - status code {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Stats retrieval failed - error: {str(e)}")
        return False

def test_end_session(session_id):
    """Test POST /api/end-session/{session_id} endpoint"""
    print(f"\n🔍 Testing End Session (POST /api/end-session/{session_id})...")
    try:
        response = requests.post(f"{BACKEND_URL}/api/end-session/{session_id}")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            if "message" in data and "success" in data["message"].lower():
                print("✅ Session ended successfully")
                return True
            else:
                print("❌ End session failed - unexpected response format")
                return False
        else:
            print(f"❌ End session failed - status code {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ End session failed - error: {str(e)}")
        return False

def run_full_test_suite():
    """Run complete test suite for drowsiness detection API"""
    print("=" * 60)
    print("🚀 DROWSINESS DETECTION API TEST SUITE")
    print("=" * 60)
    
    results = {
        "health_check": False,
        "start_session": False,
        "analyze_drowsiness": False,
        "analysis_history": False,
        "session_stats": False,
        "end_session": False
    }
    
    # Test 1: Health Check
    results["health_check"] = test_health_check()
    
    # Test 2: Start Session
    session_id = test_start_session()
    if session_id:
        results["start_session"] = True
        
        # Test 3: Analyze Drowsiness
        print("\n📸 Creating test image for drowsiness analysis...")
        test_image = create_test_image()
        print("✅ Test image created successfully")
        
        results["analyze_drowsiness"] = test_analyze_drowsiness(session_id, test_image)
        
        # Small delay to ensure data is saved
        time.sleep(1)
        
        # Test 4: Analysis History
        results["analysis_history"] = test_analysis_history(session_id)
        
        # Test 5: Session Stats
        results["session_stats"] = test_session_stats(session_id)
        
        # Test 6: End Session
        results["end_session"] = test_end_session(session_id)
    else:
        print("\n⚠️ Skipping remaining tests due to session creation failure")
    
    # Print Summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        print(f"{test_name.replace('_', ' ').title()}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    
    if passed == total:
        print("🎉 All tests passed! API is working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Check the details above.")
        return False

if __name__ == "__main__":
    success = run_full_test_suite()
    exit(0 if success else 1)