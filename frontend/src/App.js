import React, { useState, useRef, useEffect, useCallback } from 'react';
import './App.css';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

function App() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [currentAnalysis, setCurrentAnalysis] = useState(null);
  const [analysisHistory, setAnalysisHistory] = useState([]);
  const [sessionStats, setSessionStats] = useState(null);
  const [cameraError, setCameraError] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [alertSound, setAlertSound] = useState(null);

  // Initialize alert sound
  useEffect(() => {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    setAlertSound(audioContext);
  }, []);

  // Play alert sound
  const playAlertSound = useCallback((frequency = 800, duration = 500) => {
    if (!alertSound) return;
    
    const oscillator = alertSound.createOscillator();
    const gainNode = alertSound.createGain();
    
    oscillator.connect(gainNode);
    gainNode.connect(alertSound.destination);
    
    oscillator.frequency.value = frequency;
    oscillator.type = 'sine';
    
    gainNode.gain.setValueAtTime(0.3, alertSound.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, alertSound.currentTime + duration / 1000);
    
    oscillator.start(alertSound.currentTime);
    oscillator.stop(alertSound.currentTime + duration / 1000);
  }, [alertSound]);

  // Start camera
  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        video: { 
          width: 640, 
          height: 480,
          facingMode: 'user'
        } 
      });
      
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
        setCameraError(null);
      }
    } catch (error) {
      console.error('Error accessing camera:', error);
      setCameraError('Unable to access camera. Please ensure camera permissions are granted.');
    }
  };

  // Stop camera
  const stopCamera = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const tracks = videoRef.current.srcObject.getTracks();
      tracks.forEach(track => track.stop());
      videoRef.current.srcObject = null;
    }
  };

  // Start monitoring session
  const startMonitoring = async () => {
    try {
      // Start new session
      const response = await fetch(`${BACKEND_URL}/api/start-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const data = await response.json();
      setSessionId(data.session_id);
      setIsMonitoring(true);
      
      // Start camera
      await startCamera();
      
    } catch (error) {
      console.error('Error starting monitoring:', error);
    }
  };

  // Stop monitoring session
  const stopMonitoring = async () => {
    try {
      if (sessionId) {
        await fetch(`${BACKEND_URL}/api/end-session/${sessionId}`, {
          method: 'POST'
        });
      }
      
      setIsMonitoring(false);
      setSessionId(null);
      setCurrentAnalysis(null);
      stopCamera();
      
    } catch (error) {
      console.error('Error stopping monitoring:', error);
    }
  };

  // Capture frame and analyze
  const captureAndAnalyze = async () => {
    if (!videoRef.current || !canvasRef.current || !sessionId || isAnalyzing) return;
    
    setIsAnalyzing(true);
    
    try {
      const canvas = canvasRef.current;
      const video = videoRef.current;
      const context = canvas.getContext('2d');
      
      // Set canvas size to match video
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      
      // Draw current frame
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      
      // Convert to base64
      const imageData = canvas.toDataURL('image/jpeg', 0.8);
      
      // Send to backend for analysis
      const response = await fetch(`${BACKEND_URL}/api/analyze-drowsiness`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_data: imageData,
          session_id: sessionId
        })
      });
      
      const analysis = await response.json();
      setCurrentAnalysis(analysis);
      
      // Play alert if drowsy
      if (analysis.is_drowsy) {
        playAlertSound();
        
        // Show browser notification
        if (Notification.permission === 'granted') {
          new Notification('Drowsiness Detected!', {
            body: 'Please take a break and rest.',
            icon: '/favicon.ico'
          });
        }
      }
      
    } catch (error) {
      console.error('Error analyzing frame:', error);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Auto-analyze every 3 seconds when monitoring
  useEffect(() => {
    let interval;
    if (isMonitoring && sessionId) {
      interval = setInterval(captureAndAnalyze, 3000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isMonitoring, sessionId, isAnalyzing]);

  // Fetch session stats
  const fetchSessionStats = async () => {
    if (!sessionId) return;
    
    try {
      const response = await fetch(`${BACKEND_URL}/api/session-stats/${sessionId}`);
      const stats = await response.json();
      setSessionStats(stats);
    } catch (error) {
      console.error('Error fetching session stats:', error);
    }
  };

  // Fetch stats every 10 seconds
  useEffect(() => {
    let interval;
    if (isMonitoring && sessionId) {
      fetchSessionStats();
      interval = setInterval(fetchSessionStats, 10000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isMonitoring, sessionId]);

  // Request notification permission
  useEffect(() => {
    if (Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  // Get alert style based on warning level
  const getAlertStyle = (warningLevel) => {
    switch (warningLevel) {
      case 'LOW':
        return 'bg-green-100 border-green-400 text-green-700';
      case 'MEDIUM':
        return 'bg-yellow-100 border-yellow-400 text-yellow-700';
      case 'HIGH':
        return 'bg-orange-100 border-orange-400 text-orange-700';
      case 'CRITICAL':
        return 'bg-red-100 border-red-400 text-red-700';
      default:
        return 'bg-gray-100 border-gray-400 text-gray-700';
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-5xl font-bold text-white mb-4">
            🚗 Drowsiness Detection System
          </h1>
          <p className="text-xl text-blue-200 mb-6">
            AI-powered driver safety monitoring to prevent accidents
          </p>
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Video Feed Section */}
          <div className="bg-white rounded-2xl shadow-2xl p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-800">Camera Feed</h2>
              <div className="flex items-center space-x-2">
                <div className={`w-3 h-3 rounded-full ${isMonitoring ? 'bg-green-500' : 'bg-gray-400'}`}></div>
                <span className="text-sm font-medium text-gray-600">
                  {isMonitoring ? 'MONITORING' : 'STOPPED'}
                </span>
              </div>
            </div>

            {/* Video Container */}
            <div className="relative bg-gray-900 rounded-xl overflow-hidden mb-6">
              <video
                ref={videoRef}
                className="w-full h-64 object-cover"
                autoPlay
                muted
                playsInline
              />
              <canvas
                ref={canvasRef}
                className="hidden"
              />
              
              {/* Camera Error */}
              {cameraError && (
                <div className="absolute inset-0 flex items-center justify-center bg-gray-800 bg-opacity-90">
                  <div className="text-center text-white">
                    <p className="text-lg mb-2">📷 Camera Error</p>
                    <p className="text-sm">{cameraError}</p>
                  </div>
                </div>
              )}
              
              {/* Analyzing Indicator */}
              {isAnalyzing && (
                <div className="absolute top-4 right-4 bg-blue-600 text-white px-3 py-1 rounded-full text-sm">
                  🔍 Analyzing...
                </div>
              )}
            </div>

            {/* Control Buttons */}
            <div className="flex justify-center space-x-4">
              {!isMonitoring ? (
                <button
                  onClick={startMonitoring}
                  className="bg-green-600 hover:bg-green-700 text-white px-8 py-3 rounded-xl font-semibold transition-colors duration-200 shadow-lg"
                >
                  🚀 Start Monitoring
                </button>
              ) : (
                <button
                  onClick={stopMonitoring}
                  className="bg-red-600 hover:bg-red-700 text-white px-8 py-3 rounded-xl font-semibold transition-colors duration-200 shadow-lg"
                >
                  ⏹️ Stop Monitoring
                </button>
              )}
            </div>
          </div>

          {/* Analysis Results Section */}
          <div className="bg-white rounded-2xl shadow-2xl p-6">
            <h2 className="text-2xl font-bold text-gray-800 mb-6">Analysis Results</h2>
            
            {/* Current Analysis */}
            {currentAnalysis ? (
              <div className={`border-l-4 p-4 mb-6 rounded-r-lg ${getAlertStyle(currentAnalysis.warning_level)}`}>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-lg font-semibold">
                    {currentAnalysis.is_drowsy ? '⚠️ Drowsiness Detected' : '✅ Alert'}
                  </h3>
                  <span className="text-sm font-medium">
                    {Math.round(currentAnalysis.confidence * 100)}% confidence
                  </span>
                </div>
                <p className="text-sm mb-3">{currentAnalysis.details}</p>
                
                {/* Recommendations */}
                {currentAnalysis.recommendations && currentAnalysis.recommendations.length > 0 && (
                  <div>
                    <h4 className="font-medium mb-1">Recommendations:</h4>
                    <ul className="text-sm space-y-1">
                      {currentAnalysis.recommendations.map((rec, index) => (
                        <li key={index} className="flex items-center">
                          <span className="w-2 h-2 bg-current rounded-full mr-2"></span>
                          {rec}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <p className="text-lg">🔍 No analysis yet</p>
                <p className="text-sm">Start monitoring to begin drowsiness detection</p>
              </div>
            )}

            {/* Session Stats */}
            {sessionStats && (
              <div className="bg-gray-50 rounded-xl p-4">
                <h3 className="text-lg font-semibold text-gray-800 mb-3">Session Statistics</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-blue-600">{sessionStats.total_analyses}</p>
                    <p className="text-sm text-gray-600">Total Analyses</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-red-600">{sessionStats.drowsy_detections}</p>
                    <p className="text-sm text-gray-600">Drowsy Detections</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-green-600">{Math.round(sessionStats.avg_confidence * 100)}%</p>
                    <p className="text-sm text-gray-600">Avg Confidence</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-purple-600">{Math.round(sessionStats.drowsy_percentage)}%</p>
                    <p className="text-sm text-gray-600">Drowsy Rate</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Safety Tips */}
        <div className="mt-8 bg-white rounded-2xl shadow-2xl p-6">
          <h2 className="text-2xl font-bold text-gray-800 mb-4">🛡️ Safety Tips</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="text-center p-4 bg-blue-50 rounded-xl">
              <div className="text-3xl mb-2">😴</div>
              <h3 className="font-semibold text-blue-800">Get Adequate Sleep</h3>
              <p className="text-sm text-blue-600">7-9 hours before driving</p>
            </div>
            <div className="text-center p-4 bg-green-50 rounded-xl">
              <div className="text-3xl mb-2">☕</div>
              <h3 className="font-semibold text-green-800">Take Regular Breaks</h3>
              <p className="text-sm text-green-600">Every 2 hours or 100 miles</p>
            </div>
            <div className="text-center p-4 bg-purple-50 rounded-xl">
              <div className="text-3xl mb-2">🚫</div>
              <h3 className="font-semibold text-purple-800">Avoid Driving When Tired</h3>
              <p className="text-sm text-purple-600">Pull over safely if drowsy</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;