import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import Webcam from 'react-webcam';
import {
  Sparkles, Heart, Search, Camera, Sliders, X, Menu, Trash2, Send,
  RefreshCw, Upload, Image as ImageIcon, CheckCircle, ChevronLeft, ChevronRight, HelpCircle
} from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

export default function App() {
  // Session & User
  const [sessionId, setSessionId] = useState('');
  
  // Navigation & UI States
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [activeTab, setActiveTab] = useState('chat'); // 'chat' or 'catalog'
  const [mlStatus, setMlStatus] = useState('connecting'); // 'healthy' | 'fallback' | 'connecting'
  const [activeOverlay, setActiveOverlay] = useState(null); // Design item currently in AR
  
  // Catalog / Designs State
  const [designs, setDesigns] = useState([]);
  const [catalogFilters, setCatalogFilters] = useState({
    category: '',
    complexity: '',
    occasion: '',
    search: '',
    page: 1,
    limit: 12
  });
  const [catalogTotalPages, setCatalogTotalPages] = useState(1);
  const [catalogTotalCount, setCatalogTotalCount] = useState(0);
  
  // Chat Feed State
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isClassifying, setIsClassifying] = useState(false);
  const [isRecommending, setIsRecommending] = useState(false);
  
  // Likes & History States
  const [likedDesigns, setLikedDesigns] = useState([]);
  const [filterHistory, setFilterHistory] = useState([]);
  const [recHistory, setRecHistory] = useState([]);
  
  // Drag and Drop Upload State
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  // AR Overlay Control Panel States
  const [arConfig, setArConfig] = useState({
    rotate: 0,      // in degrees (-180 to 180)
    scale: 1.0,     // multiplier (0.1 to 3.0)
    translateX: 0,  // offset in pixels (-500 to 500)
    translateY: 0,  // offset in pixels (-500 to 500)
    opacity: 0.85,  // transparency
    blendMode: 'multiply', // 'multiply' | 'normal' | 'difference'
    enableTracking: true,
    facingMode: 'user' // 'user' | 'environment'
  });
  
  // MediaPipe / Webcam Refs
  const webcamRef = useRef(null);
  const arContainerRef = useRef(null);
  const [handTracked, setHandTracked] = useState(false);
  const [trackingOffset, setTrackingOffset] = useState({ x: 0, y: 0, angle: 0, scale: 1.0 });

  // 1. Initialize session and fetch user preferences
  useEffect(() => {
    let storedSession = localStorage.getItem('mehndi_session_id');
    if (!storedSession) {
      storedSession = 'sess_' + Math.random().toString(36).substring(2, 15);
      localStorage.setItem('mehndi_session_id', storedSession);
    }
    setSessionId(storedSession);
    
    // Check ML backend health
    checkBackendHealth();
    
    // Initialize welcome chat message
    setMessages([
      {
        id: 'welcome',
        sender: 'assistant',
        text: "✨ Welcome to MehndiAI! I'm your virtual designer. I can recommend traditional, minimalist, and intricate bridal designs, or analyze any photo you upload. Try asking for a specific style (e.g., 'simple Arabic designs' or 'intricate bridal patterns for wedding')!"
      }
    ]);
  }, []);

  // Fetch likes & history when session is ready
  useEffect(() => {
    if (sessionId) {
      fetchUserPreferences();
    }
  }, [sessionId]);

  // Load catalog on filter changes
  useEffect(() => {
    fetchCatalog();
  }, [catalogFilters]);

  // 2. Network Requests
  const checkBackendHealth = async () => {
    try {
      const res = await axios.get(`${API_URL}/health`);
      setMlStatus(res.data.design_count > 0 ? 'healthy' : 'fallback');
    } catch (e) {
      console.error("Failed health check:", e);
      setMlStatus('connecting');
    }
  };

  const fetchUserPreferences = async () => {
    try {
      const res = await axios.get(`${API_URL}/api/preferences/${sessionId}`);
      setLikedDesigns(res.data.liked_designs || []);
      setFilterHistory(res.data.filter_history || []);
      setRecHistory(res.data.recommendation_history || []);
    } catch (e) {
      console.error("Failed fetching user preferences:", e);
    }
  };

  const fetchCatalog = async () => {
    try {
      const { category, complexity, occasion, search, page, limit } = catalogFilters;
      const res = await axios.get(`${API_URL}/api/designs`, {
        params: { category, complexity, occasion, search, page, limit }
      });
      setDesigns(res.data.designs);
      setCatalogTotalPages(res.data.total_pages);
      setCatalogTotalCount(res.data.total_count);
    } catch (e) {
      console.error("Failed fetching catalog:", e);
    }
  };

  const handleLikeToggle = async (design) => {
    try {
      const res = await axios.post(`${API_URL}/api/preferences`, {
        userId: sessionId,
        likedDesignId: design.id
      });
      if (res.data.success) {
        // Refresh preferences to sync UI
        fetchUserPreferences();
      }
    } catch (e) {
      console.error("Error toggling like:", e);
    }
  };

  const clearSession = () => {
    localStorage.removeItem('mehndi_session_id');
    const newSession = 'sess_' + Math.random().toString(36).substring(2, 15);
    localStorage.setItem('mehndi_session_id', newSession);
    setSessionId(newSession);
    setMessages([
      {
        id: 'welcome',
        sender: 'assistant',
        text: "✨ Session cleared! Let's start fresh. Tell me what type of Mehndi designs you'd like to explore today."
      }
    ]);
  };

  // 3. User Chat Actions
  const handleSendMessage = async (textToSend) => {
    const queryText = textToSend || inputValue;
    if (!queryText.trim()) return;
    
    // Add user message to chat feed
    const userMsgId = 'msg_' + Date.now();
    setMessages(prev => [...prev, { id: userMsgId, sender: 'user', text: queryText }]);
    if (!textToSend) setInputValue('');
    
    // Parse quick heuristics locally to send structured query to recommendation endpoint
    setIsRecommending(true);
    
    // Conversational trigger logic
    let category = '';
    let complexity = '';
    let occasion = '';
    
    const textLower = queryText.toLowerCase();
    
    // Category mapping
    if (textLower.includes('bridal') || textLower.includes('dulhan') || textLower.includes('wedding')) {
      category = 'bridal';
      occasion = 'wedding';
    } else if (textLower.includes('arabic')) {
      if (textLower.includes('indo')) category = 'indo_arabic';
      else category = 'arabic';
    } else if (textLower.includes('minimalist') || textLower.includes('simple') || textLower.includes('easy')) {
      category = 'minimalist';
    } else if (textLower.includes('floral') || textLower.includes('flower')) {
      category = 'floral';
    } else if (textLower.includes('geometric') || textLower.includes('line') || textLower.includes('grid')) {
      category = 'geometric';
    } else if (textLower.includes('rajasthani') || textLower.includes('traditional')) {
      category = 'rajasthani';
    } else if (textLower.includes('finger') || textLower.includes('accent')) {
      category = 'finger';
    }
    
    // Complexity mapping
    if (textLower.includes('intricate') || textLower.includes('heavy') || textLower.includes('full')) {
      complexity = 'intricate';
    } else if (textLower.includes('medium') || textLower.includes('moderate')) {
      complexity = 'medium';
    } else if (textLower.includes('simple') || textLower.includes('easy') || textLower.includes('light')) {
      complexity = 'simple';
    }
    
    // Occasion mapping
    if (textLower.includes('festival') || textLower.includes('eid') || textLower.includes('karwa') || textLower.includes('diwali')) {
      occasion = 'festival';
    } else if (textLower.includes('party') || textLower.includes('guest')) {
      occasion = 'party';
    } else if (textLower.includes('everyday') || textLower.includes('daily') || textLower.includes('home')) {
      occasion = 'everyday';
    } else if (textLower.includes('wedding') || textLower.includes('bridal') || textLower.includes('marriage')) {
      occasion = 'wedding';
    }

    try {
      const res = await axios.post(`${API_URL}/api/recommend`, {
        userId: sessionId,
        category,
        complexity,
        occasion
      });
      
      const recs = res.data.recommendations;
      
      let replyText = `I searched our database for ${category || 'any'} Mehndi designs of ${complexity || 'any'} complexity for ${occasion || 'any'} occasions. `;
      
      if (recs.length > 0) {
        replyText += `Here are the top ${recs.length} matching designs I found for you:`;
      } else {
        replyText += `I couldn't find exact matches. Here are some beautiful popular designs you might like:`;
      }
      
      setMessages(prev => [...prev, {
        id: 'assistant_' + Date.now(),
        sender: 'assistant',
        text: replyText,
        designs: recs.slice(0, 8) // Limit to top 8 recommendation cards in the chat bubble
      }]);
      
      fetchUserPreferences(); // Sync history
    } catch (e) {
      console.error(e);
      setMessages(prev => [...prev, {
        id: 'assistant_err_' + Date.now(),
        sender: 'assistant',
        text: "Sorry, I had trouble talking to the recommendation service. Please make sure the services are running."
      }]);
    } finally {
      setIsRecommending(false);
    }
  };

  // 4. File Upload & Classification
  const handleFileUpload = async (file) => {
    if (!file) return;
    
    // Print file uploading message in chat
    const userMsgId = 'upload_' + Date.now();
    setMessages(prev => [...prev, {
      id: userMsgId,
      sender: 'user',
      text: `Uploaded photo: ${file.name}`,
      imgPreview: URL.createObjectURL(file)
    }]);
    
    setIsClassifying(true);
    
    const formData = new FormData();
    formData.append('image', file);
    
    try {
      // 1. Run multi-axis classification
      const classRes = await axios.post(`${API_URL}/api/classify`, formData);
      const { category, category_confidence, complexity, complexity_confidence, occasion, occasion_confidence, framework_used } = classRes.data;
      
      // 2. Fetch visually similar recommendations using the file
      const recFormData = new FormData();
      recFormData.append('userId', sessionId);
      recFormData.append('referenceImage', file);
      
      const recRes = await axios.post(`${API_URL}/api/recommend`, recFormData);
      
      // Form reply bubble
      setMessages(prev => [...prev, {
        id: 'class_res_' + Date.now(),
        sender: 'assistant',
        text: `🔍 **Image Analysis Complete** (Framework: ${framework_used})\n\nHere are the classifier predictions for your design:\n- **Pattern Style**: \`${category}\` (${Math.round(category_confidence * 100)}% confidence)\n- **Occasion Mapping**: \`${occasion}\` (${Math.round(occasion_confidence * 100)}% confidence)\n- **Density/Complexity**: \`${complexity}\` (${Math.round(complexity_confidence * 100)}% confidence)`,
        classification: classRes.data,
        designs: recRes.data.recommendations.slice(0, 8)
      }]);
      
      fetchUserPreferences(); // Sync history
    } catch (e) {
      console.error(e);
      setMessages(prev => [...prev, {
        id: 'class_err_' + Date.now(),
        sender: 'assistant',
        text: "Failed to analyze image. Ensure the Python ML service is online and running."
      }]);
    } finally {
      setIsClassifying(false);
    }
  };

  // Drag-and-drop event handlers
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setIsDragging(true);
    } else if (e.type === "dragleave") {
      setIsDragging(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  // 5. MediaPipe Hands Integration & Loop
  useEffect(() => {
    if (!activeOverlay || !activeOverlay.image_path) return;
    
    let active = true;
    let cameraInstance = null;
    
    const initTracking = () => {
      // Access standard MediaPipe Hands library loaded from CDN scripts
      if (typeof window.Hands === 'undefined' || typeof window.Camera === 'undefined') {
        console.log("MediaPipe Scripts not ready yet. Retrying in 1s...");
        setTimeout(initTracking, 1000);
        return;
      }
      
      const hands = new window.Hands({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`
      });
      
      hands.setOptions({
        maxNumHands: 1,
        modelComplexity: 1,
        minDetectionConfidence: 0.55,
        minTrackingConfidence: 0.5
      });
      
      hands.onResults((results) => {
        if (!active || !arConfig.enableTracking) return;
        
        if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
          const landmarks = results.multiHandLandmarks[0];
          setHandTracked(true);
          
          // Calculate Center, Scale and Angle
          const landmark0 = landmarks[0]; // Wrist
          const landmark9 = landmarks[9]; // Middle finger MCP (center of palm)
          
          const xDiff = landmark9.x - landmark0.x;
          const yDiff = landmark9.y - landmark0.y;
          
          // Translate to camera bounds (%)
          const xPos = landmark9.x * 100;
          const yPos = landmark9.y * 100;
          
          // Rotation angle
          const angleRad = Math.atan2(xDiff, -yDiff);
          const angleDeg = (angleRad * 180) / Math.PI;
          
          // Scale multiplier based on hand length
          const handSize = Math.sqrt(xDiff * xDiff + yDiff * yDiff);
          const normalizedScale = handSize * 3.8; 
          
          setTrackingOffset({
            x: xPos,
            y: yPos,
            angle: angleDeg,
            scale: normalizedScale
          });
        } else {
          setHandTracked(false);
        }
      });
      
      // Start camera feed loop
      const checkWebcam = setInterval(() => {
        if (webcamRef.current && webcamRef.current.video && webcamRef.current.video.readyState === 4) {
          clearInterval(checkWebcam);
          
          cameraInstance = new window.Camera(webcamRef.current.video, {
            onFrame: async () => {
              if (active && webcamRef.current && webcamRef.current.video) {
                await hands.send({ image: webcamRef.current.video });
              }
            },
            width: 640,
            height: 480
          });
          cameraInstance.start();
        }
      }, 500);
    };
    
    initTracking();
    
    return () => {
      active = false;
      if (cameraInstance) {
        cameraInstance.stop();
      }
    };
  }, [activeOverlay, arConfig.enableTracking]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-henna-50 font-sans text-henna-950">
      
      {/* ==========================================
          SIDEBAR
          ========================================== */}
      <div className={`transition-smooth relative flex flex-col border-r border-henna-100 bg-white shadow-xl ${
        isSidebarOpen ? 'w-80' : 'w-0 overflow-hidden border-none'
      }`}>
        {/* Sidebar Header */}
        <div className="flex items-center justify-between border-b border-henna-100 p-4">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-tr from-henna-800 to-henna-600 text-white font-extrabold shadow-md">
              M
            </div>
            <span className="font-sans text-xl font-bold tracking-tight text-henna-900">
              Mehndi<span className="text-henna-500">AI</span>
            </span>
          </div>
          <button
            onClick={() => setIsSidebarOpen(false)}
            className="rounded-full p-1 hover:bg-henna-50 text-henna-700"
          >
            <ChevronLeft size={20} />
          </button>
        </div>

        {/* Sidebar Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6">
          
          {/* Status Alert */}
          <div className={`rounded-xl border p-3 flex items-start gap-2.5 shadow-sm text-xs ${
            mlStatus === 'healthy' 
              ? 'bg-emerald-50/50 border-emerald-100 text-emerald-950'
              : mlStatus === 'fallback'
                ? 'bg-amber-50/50 border-amber-100 text-amber-950'
                : 'bg-henna-100/50 border-henna-200 text-henna-800'
          }`}>
            <div className={`h-2.5 w-2.5 rounded-full mt-0.5 shrink-0 ${
              mlStatus === 'healthy' ? 'bg-emerald-500' : mlStatus === 'fallback' ? 'bg-amber-500' : 'bg-red-500 pulse-ring'
            }`} />
            <div>
              <p className="font-semibold capitalize">
                ML Server: {mlStatus === 'healthy' ? 'CNN (TFLite) Mode' : mlStatus === 'fallback' ? 'Feature Fallback (Python 3.14)' : 'Connecting...'}
              </p>
              <p className="text-[10px] opacity-75 mt-0.5">
                {mlStatus === 'healthy' 
                  ? 'High-precision MobileNetV2 hand model active.'
                  : mlStatus === 'fallback'
                    ? 'Running locally via Scikit-Learn RandomForest.'
                    : 'Awaiting ML service connection on local port 8000.'}
              </p>
            </div>
          </div>

          {/* Quick Tabs */}
          <div className="flex rounded-lg bg-henna-100 p-1 text-sm font-medium">
            <button
              onClick={() => setActiveTab('chat')}
              className={`flex-1 rounded-md py-1.5 text-center transition-all ${
                activeTab === 'chat' ? 'bg-white text-henna-900 shadow-sm' : 'text-henna-700 hover:text-henna-900'
              }`}
            >
              Consultant Chat
            </button>
            <button
              onClick={() => setActiveTab('catalog')}
              className={`flex-1 rounded-md py-1.5 text-center transition-all ${
                activeTab === 'catalog' ? 'bg-white text-henna-900 shadow-sm' : 'text-henna-700 hover:text-henna-900'
              }`}
            >
              Explore Catalog
            </button>
          </div>

          {/* Drag & Drop Upload classification */}
          <div
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            className={`relative rounded-2xl border-2 border-dashed p-5 text-center transition-all ${
              isDragging
                ? 'border-henna-600 bg-henna-50/50'
                : 'border-henna-200 bg-white hover:border-henna-400'
            }`}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={(e) => handleFileUpload(e.target.files[0])}
              className="hidden"
              accept="image/*"
            />
            <div className="flex flex-col items-center justify-center space-y-2">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-henna-100 text-henna-700">
                <Upload size={20} />
              </div>
              <div>
                <p className="text-sm font-semibold text-henna-900">Analyze reference image</p>
                <p className="text-[11px] text-henna-600 mt-0.5">Drag photo or browse to classify and find similar patterns</p>
              </div>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="mt-1 rounded-lg bg-henna-800 hover:bg-henna-700 text-white px-3 py-1 text-xs font-semibold shadow transition-colors"
              >
                Upload File
              </button>
            </div>
          </div>

          {/* User Saved Likes Section */}
          <div className="space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-henna-800 flex items-center gap-1.5">
              <Heart size={14} className="fill-henna-800 text-henna-800" />
              Liked Collections ({likedDesigns.length})
            </h3>
            {likedDesigns.length === 0 ? (
              <p className="text-xs text-henna-600 italic bg-henna-50/50 rounded-xl p-3 border border-henna-100">
                No liked designs yet. Click the heart icon on recommended items to save them here.
              </p>
            ) : (
              <div className="grid grid-cols-4 gap-2">
                {likedDesigns.map(design => (
                  <div
                    key={design.id}
                    className="group relative aspect-square rounded-lg overflow-hidden border border-henna-100 bg-henna-100 shadow-sm cursor-pointer"
                    onClick={() => setActiveOverlay(design)}
                    title={`Try AR: ${design.category}`}
                  >
                    <img
                      src={`${API_URL}/dataset/${design.image_path}`}
                      alt={design.category}
                      className="h-full w-full object-cover transition-transform group-hover:scale-110"
                    />
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                      <Camera size={14} className="text-white" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Search History Chips */}
          {filterHistory.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-henna-800 flex items-center gap-1.5">
                <Sparkles size={14} />
                Recent Search Preferences
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {filterHistory.slice(0, 5).map((hist, idx) => {
                  const label = [hist.complexity, hist.category, hist.occasion].filter(Boolean).join(' ');
                  if (!label) return null;
                  return (
                    <button
                      key={idx}
                      onClick={() => handleSendMessage(`Show me some ${label} designs`)}
                      className="rounded-full bg-henna-100 hover:bg-henna-200 text-henna-900 text-[10px] px-2.5 py-1 transition-colors font-medium"
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

        </div>

        {/* Sidebar Footer */}
        <div className="border-t border-henna-100 p-4 bg-henna-50/50 flex items-center justify-between text-xs text-henna-700">
          <span>Session: <code className="font-semibold font-mono">{sessionId.substring(5, 12)}...</code></span>
          <button
            onClick={clearSession}
            className="flex items-center gap-1 hover:text-red-700 transition-colors font-semibold"
            title="Reset active session history"
          >
            <Trash2 size={13} />
            Reset
          </button>
        </div>
      </div>

      {/* Sidebar Closed Toggle Button */}
      {!isSidebarOpen && (
        <button
          onClick={() => setIsSidebarOpen(true)}
          className="absolute left-4 top-4 z-20 flex h-10 w-10 items-center justify-center rounded-full bg-white text-henna-800 shadow-md border border-henna-100 hover:bg-henna-50 transition-all"
        >
          <Menu size={20} />
        </button>
      )}

      {/* ==========================================
          MAIN AREA
          ========================================== */}
      <div className="flex-1 flex flex-col h-full bg-henna-50/30">
        
        {/* ==========================================
            CHAT VIEW TAB
            ========================================== */}
        {activeTab === 'chat' && (
          <div className="flex-1 flex flex-col h-full overflow-hidden">
            {/* Header */}
            <div className="bg-white border-b border-henna-100 p-4 flex items-center justify-between shadow-sm">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-henna-900">Virtual Mehndi Designer</span>
                <span className="text-xs bg-henna-100 text-henna-800 px-2 py-0.5 rounded-full">Assistant Bot</span>
              </div>
              <button 
                onClick={() => setActiveTab('catalog')} 
                className="text-xs font-semibold text-henna-800 hover:text-henna-600 transition-colors"
              >
                View full catalog catalog &rarr;
              </button>
            </div>

            {/* Message Feed */}
            <div className="flex-1 overflow-y-auto p-4 space-y-6">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div className={`max-w-[85%] rounded-2xl p-4 shadow-sm space-y-3 transition-all ${
                    msg.sender === 'user'
                      ? 'bg-henna-800 text-white rounded-tr-none'
                      : 'bg-white text-henna-950 rounded-tl-none border border-henna-100/50'
                  }`}>
                    {/* Text block */}
                    <div className="text-sm leading-relaxed whitespace-pre-line prose max-w-none">
                      {msg.text}
                    </div>

                    {/* Optional Local image upload preview */}
                    {msg.imgPreview && (
                      <div className="rounded-lg overflow-hidden border border-white/20 max-w-xs shadow-md">
                        <img src={msg.imgPreview} alt="User Reference Input" className="w-full h-auto" />
                      </div>
                    )}

                    {/* Optional Recommendation results grid */}
                    {msg.designs && msg.designs.length > 0 && (
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-2">
                        {msg.designs.map((design) => {
                          const isLiked = likedDesigns.some(item => item.id === design.id);
                          return (
                            <div
                              key={design.id}
                              className="rounded-xl border border-henna-100/60 bg-henna-50/50 overflow-hidden shadow-sm hover:shadow-md transition-shadow flex flex-col group relative"
                            >
                              {/* Thumbnail */}
                              <div className="relative aspect-[3/4] bg-henna-100 overflow-hidden">
                                <img
                                  src={`${API_URL}/dataset/${design.image_path}`}
                                  alt={design.category}
                                  className="h-full w-full object-cover group-hover:scale-105 transition-transform duration-300"
                                />
                                
                                {/* Similarity Score badge if exists */}
                                {design.similarity_score !== undefined && design.similarity_score < 1.0 && (
                                  <div className="absolute top-2 left-2 text-[9px] font-bold bg-henna-800 text-white px-2 py-0.5 rounded-full shadow">
                                    Sim: {Math.round(design.similarity_score * 100)}%
                                  </div>
                                )}

                                {/* Hover AR Try trigger */}
                                <div className="absolute inset-0 bg-black/30 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity duration-300">
                                  <button
                                    onClick={() => setActiveOverlay(design)}
                                    className="flex items-center gap-1 bg-white hover:bg-henna-50 text-henna-950 font-bold px-3 py-1.5 rounded-full text-xs shadow-lg transition-transform hover:scale-105"
                                  >
                                    <Camera size={12} className="fill-henna-800 stroke-none" />
                                    Try AR
                                  </button>
                                </div>
                              </div>

                              {/* Title Details */}
                              <div className="p-2.5 flex-1 flex flex-col justify-between text-xs bg-white text-henna-950">
                                <div>
                                  <div className="flex items-center justify-between gap-1">
                                    <span className="font-bold truncate capitalize">{design.category.replace('_', ' ')}</span>
                                    <button
                                      onClick={() => handleLikeToggle(design)}
                                      className="text-henna-300 hover:text-red-600 transition-colors shrink-0"
                                    >
                                      <Heart size={14} className={isLiked ? 'fill-red-600 text-red-600' : ''} />
                                    </button>
                                  </div>
                                  <div className="flex flex-wrap gap-1 mt-1.5">
                                    <span className="text-[9px] bg-amber-50 text-amber-800 font-semibold px-1.5 py-0.5 rounded border border-amber-100 capitalize">{design.complexity}</span>
                                    <span className="text-[9px] bg-rose-50 text-rose-800 font-semibold px-1.5 py-0.5 rounded border border-rose-100 capitalize">{design.occasion}</span>
                                  </div>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {/* Typing indicators */}
              {(isClassifying || isRecommending) && (
                <div className="flex justify-start">
                  <div className="bg-white border border-henna-100/50 rounded-2xl rounded-tl-none p-4 shadow-sm flex items-center gap-2">
                    <RefreshCw size={15} className="animate-spin text-henna-700" />
                    <span className="text-xs text-henna-700 font-medium">
                      {isClassifying ? 'Analyzing uploaded image...' : 'Consulting database for recommendations...'}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Input Action Tray */}
            <div className="p-4 bg-white border-t border-henna-100 flex flex-col gap-3">
              
              {/* Recommendation helper prompts */}
              <div className="flex gap-2 overflow-x-auto pb-1 text-xs shrink-0 select-none">
                <button
                  onClick={() => handleSendMessage("Show me simple floral designs for everyday wear")}
                  className="rounded-full border border-henna-200 bg-white hover:bg-henna-50 text-henna-800 px-3.5 py-1.5 transition-colors font-medium shrink-0 shadow-sm"
                >
                  🌸 Simple Floral (Everyday)
                </button>
                <button
                  onClick={() => handleSendMessage("Show me intricate bridal designs for full wedding")}
                  className="rounded-full border border-henna-200 bg-white hover:bg-henna-50 text-henna-800 px-3.5 py-1.5 transition-colors font-medium shrink-0 shadow-sm"
                >
                  👑 Intricate Bridal (Wedding)
                </button>
                <button
                  onClick={() => handleSendMessage("Show me modern Arabic patterns of medium density")}
                  className="rounded-full border border-henna-200 bg-white hover:bg-henna-50 text-henna-800 px-3.5 py-1.5 transition-colors font-medium shrink-0 shadow-sm"
                >
                  ⚡ Medium Arabic (Party)
                </button>
                <button
                  onClick={() => handleSendMessage("Show me geometric minimalist designs")}
                  className="rounded-full border border-henna-200 bg-white hover:bg-henna-50 text-henna-800 px-3.5 py-1.5 transition-colors font-medium shrink-0 shadow-sm"
                >
                  📐 Minimalist Geometric
                </button>
              </div>

              {/* Chat Input Field */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSendMessage();
                }}
                className="flex items-center gap-2"
              >
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder="Describe your design or select a helper card above..."
                  className="flex-1 rounded-xl border border-henna-200 px-4 py-3 text-sm focus:outline-none focus:border-henna-600 shadow-inner"
                />
                
                <button
                  type="submit"
                  className="bg-henna-800 hover:bg-henna-700 text-white rounded-xl p-3 shadow-md transition-colors"
                >
                  <Send size={18} />
                </button>
              </form>
            </div>
          </div>
        )}

        {/* ==========================================
            CATALOG EXPLORER TAB
            ========================================== */}
        {activeTab === 'catalog' && (
          <div className="flex-1 flex flex-col h-full overflow-hidden">
            {/* Filters panel */}
            <div className="bg-white border-b border-henna-100 p-4 shadow-sm flex flex-col md:flex-row md:items-center gap-3 justify-between">
              
              {/* Filters dropdown */}
              <div className="flex flex-wrap items-center gap-2 text-xs">
                {/* Category select */}
                <select
                  value={catalogFilters.category}
                  onChange={(e) => setCatalogFilters(prev => ({ ...prev, category: e.target.value, page: 1 }))}
                  className="rounded-lg border border-henna-200 bg-white p-2 text-henna-900 focus:outline-none focus:border-henna-600 font-semibold"
                >
                  <option value="">All Categories</option>
                  <option value="arabic">Arabic</option>
                  <option value="bridal">Bridal</option>
                  <option value="finger">Finger Accent</option>
                  <option value="floral">Floral</option>
                  <option value="geometric">Geometric</option>
                  <option value="indo_arabic">Indo-Arabic</option>
                  <option value="minimalist">Minimalist</option>
                  <option value="rajasthani">Rajasthani</option>
                </select>

                {/* Complexity select */}
                <select
                  value={catalogFilters.complexity}
                  onChange={(e) => setCatalogFilters(prev => ({ ...prev, complexity: e.target.value, page: 1 }))}
                  className="rounded-lg border border-henna-200 bg-white p-2 text-henna-900 focus:outline-none focus:border-henna-600 font-semibold"
                >
                  <option value="">All Complexities</option>
                  <option value="simple">Simple</option>
                  <option value="medium">Medium</option>
                  <option value="intricate">Intricate</option>
                </select>

                {/* Occasion select */}
                <select
                  value={catalogFilters.occasion}
                  onChange={(e) => setCatalogFilters(prev => ({ ...prev, occasion: e.target.value, page: 1 }))}
                  className="rounded-lg border border-henna-200 bg-white p-2 text-henna-900 focus:outline-none focus:border-henna-600 font-semibold"
                >
                  <option value="">All Occasions</option>
                  <option value="everyday">Everyday</option>
                  <option value="festival">Festival</option>
                  <option value="party">Party</option>
                  <option value="wedding">Wedding</option>
                </select>
              </div>

              {/* Search text input */}
              <div className="relative max-w-xs w-full">
                <input
                  type="text"
                  value={catalogFilters.search}
                  onChange={(e) => setCatalogFilters(prev => ({ ...prev, search: e.target.value, page: 1 }))}
                  placeholder="Search catalog tags..."
                  className="w-full rounded-lg border border-henna-200 bg-white px-3 py-2 pl-9 text-xs focus:outline-none focus:border-henna-600 shadow-sm"
                />
                <Search size={14} className="absolute left-3 top-2.5 text-henna-600" />
              </div>
            </div>

            {/* Catalog Grid */}
            <div className="flex-1 overflow-y-auto p-6">
              {designs.length === 0 ? (
                <div className="text-center py-20 bg-white rounded-3xl border border-henna-100 p-8 shadow-sm">
                  <ImageIcon size={48} className="mx-auto text-henna-300 animate-pulse" />
                  <h3 className="text-lg font-bold text-henna-900 mt-4">No designs found</h3>
                  <p className="text-sm text-henna-600 mt-1">Try clearing some filters or searching for another term.</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-6">
                  {designs.map((design) => {
                    const isLiked = likedDesigns.some(item => item.id === design.id);
                    return (
                      <div
                        key={design.id}
                        className="rounded-2xl border border-henna-100 bg-white overflow-hidden shadow-sm hover:shadow-lg transition-all flex flex-col group relative"
                      >
                        {/* Thumbnail */}
                        <div className="relative aspect-[3/4] bg-henna-50 overflow-hidden border-b border-henna-50">
                          <img
                            src={`${API_URL}/dataset/${design.image_path}`}
                            alt={design.category}
                            className="h-full w-full object-cover group-hover:scale-105 transition-transform duration-500"
                          />
                          
                          {/* Floating AR Hover trigger */}
                          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity duration-300">
                            <button
                              onClick={() => setActiveOverlay(design)}
                              className="flex items-center gap-1.5 bg-white hover:bg-henna-50 text-henna-950 font-bold px-4 py-2 rounded-full text-xs shadow-lg transition-transform hover:scale-105"
                            >
                              <Camera size={14} className="fill-henna-800 stroke-none" />
                              Try AR Overlay
                            </button>
                          </div>
                        </div>

                        {/* Card Details */}
                        <div className="p-4 flex-1 flex flex-col justify-between">
                          <div>
                            <div className="flex items-center justify-between gap-1.5">
                              <span className="font-bold text-sm text-henna-900 capitalize truncate">
                                {design.category.replace('_', ' ')}
                              </span>
                              <button
                                onClick={() => handleLikeToggle(design)}
                                className="text-henna-300 hover:text-red-600 transition-colors shrink-0"
                              >
                                <Heart size={16} className={isLiked ? 'fill-red-600 text-red-600' : ''} />
                              </button>
                            </div>
                            
                            <div className="flex flex-wrap gap-1.5 mt-3">
                              <span className="text-[10px] bg-amber-50 text-amber-800 font-semibold px-2 py-0.5 rounded border border-amber-100 capitalize">{design.complexity}</span>
                              <span className="text-[10px] bg-rose-50 text-rose-800 font-semibold px-2 py-0.5 rounded border border-rose-100 capitalize">{design.occasion}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Pagination Controls */}
            {catalogTotalPages > 1 && (
              <div className="bg-white border-t border-henna-100 p-4 flex items-center justify-center gap-4 text-xs font-semibold text-henna-800 shadow-inner">
                <button
                  disabled={catalogFilters.page === 1}
                  onClick={() => setCatalogFilters(prev => ({ ...prev, page: prev.page - 1 }))}
                  className="rounded-lg border border-henna-200 bg-white p-2 hover:bg-henna-50 transition-colors disabled:opacity-50"
                >
                  <ChevronLeft size={16} />
                </button>
                <span>Page {catalogFilters.page} of {catalogTotalPages}</span>
                <button
                  disabled={catalogFilters.page === catalogTotalPages}
                  onClick={() => setCatalogFilters(prev => ({ ...prev, page: prev.page + 1 }))}
                  className="rounded-lg border border-henna-200 bg-white p-2 hover:bg-henna-50 transition-colors disabled:opacity-50"
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ==========================================
          CAMERA AR OVERLAY PORTAL SCREEN
          ========================================== */}
      {activeOverlay && (
        <div className="absolute inset-0 z-50 flex flex-col md:flex-row bg-black text-white overflow-hidden">
          
          {/* Close Modal Button */}
          <button
            onClick={() => setActiveOverlay(null)}
            className="absolute top-4 right-4 z-50 flex h-10 w-10 items-center justify-center rounded-full bg-black/60 border border-white/20 text-white hover:bg-black transition-colors"
          >
            <X size={20} />
          </button>

          {/* Left Side: Video Feed */}
          <div className="flex-1 relative bg-black flex items-center justify-center">
            
            {/* Webcam viewport */}
            <div className="relative w-full max-w-3xl aspect-[4/3] bg-neutral-900 overflow-hidden shadow-2xl rounded-2xl border border-white/10" ref={arContainerRef}>
              <Webcam
                ref={webcamRef}
                audio={false}
                screenshotFormat="image/jpeg"
                videoConstraints={{
                  width: 640,
                  height: 480,
                  facingMode: arConfig.facingMode
                }}
                className="w-full h-full object-cover scale-x-[-1]" // mirror local camera feed
              />

              {/* Hybrid AR Overlay layer */}
              {/* Uses GPU hardware-accelerated transforms based on Landmark positions (if tracked) + control panel offsets */}
              <div
                className="absolute pointer-events-none transition-transform duration-75"
                style={{
                  left: arConfig.enableTracking && handTracked ? `${100 - trackingOffset.x}%` : '50%',
                  top: arConfig.enableTracking && handTracked ? `${trackingOffset.y}%` : '50%',
                  transform: `
                    translate(-50%, -50%)
                    translate(${arConfig.translateX}px, ${arConfig.translateY}px)
                    rotate(${arConfig.enableTracking && handTracked ? -trackingOffset.angle + arConfig.rotate : arConfig.rotate}deg)
                    scale(${arConfig.enableTracking && handTracked ? trackingOffset.scale * arConfig.scale : arConfig.scale})
                  `,
                  width: '280px',
                  height: '280px',
                  opacity: arConfig.opacity,
                  mixBlendMode: arConfig.blendMode
                }}
              >
                <img
                  src={`${API_URL}/dataset/${activeOverlay.image_path}`}
                  alt="Mehndi Overlay"
                  className="w-full h-full object-contain filter contrast-125 brightness-95"
                />
              </div>

              {/* Camera indicators */}
              <div className="absolute bottom-4 left-4 z-10 text-xs bg-black/60 border border-white/20 rounded-lg px-3 py-1.5 flex items-center gap-2">
                <span className={`h-2 w-2 rounded-full ${handTracked && arConfig.enableTracking ? 'bg-emerald-500 animate-ping' : 'bg-amber-500'}`} />
                <span>
                  {arConfig.enableTracking 
                    ? (handTracked ? 'MediaPipe Tracking Active' : 'Align palm in front of camera') 
                    : 'Manual Adjustment Only'}
                </span>
              </div>
            </div>
          </div>

          {/* Right Side: Alignment Control Panel Drawer */}
          <div className="w-full md:w-80 border-t md:border-t-0 md:border-l border-white/10 bg-neutral-950 p-6 flex flex-col justify-between overflow-y-auto shrink-0 space-y-6">
            
            {/* Panel Header */}
            <div>
              <h3 className="font-bold text-lg flex items-center gap-2">
                <Sliders className="text-henna-500" />
                AR Alignment Console
              </h3>
              <p className="text-xs text-neutral-400 mt-1 capitalize">
                Fitting: {activeOverlay.category.replace('_', ' ')} ({activeOverlay.complexity})
              </p>
            </div>

            {/* Sliders Console */}
            <div className="space-y-5 text-sm flex-1 pt-4">
              
              {/* MediaPipe Auto-tracking switch */}
              <div className="flex items-center justify-between bg-neutral-900 border border-white/10 rounded-xl p-3">
                <div>
                  <p className="font-semibold text-xs">AI Auto Hand-Tracking</p>
                  <p className="text-[10px] text-neutral-400 mt-0.5">Locks overlay onto your palm center</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={arConfig.enableTracking}
                    onChange={(e) => setArConfig(prev => ({ ...prev, enableTracking: e.target.checked }))}
                    className="sr-only peer"
                  />
                  <div className="w-9 h-5 bg-neutral-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:height-4 after:width-4 after:transition-all peer-checked:bg-henna-600"></div>
                </label>
              </div>

              {/* Sliders */}
              <div className="space-y-3.5">
                {/* Scale */}
                <div>
                  <div className="flex justify-between text-xs text-neutral-400 font-semibold">
                    <span>Overlay Size (Scale)</span>
                    <span>{Math.round(arConfig.scale * 100)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0.2"
                    max="2.5"
                    step="0.05"
                    value={arConfig.scale}
                    onChange={(e) => setArConfig(prev => ({ ...prev, scale: parseFloat(e.target.value) }))}
                    className="w-full h-1 mt-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-henna-500"
                  />
                </div>

                {/* Rotate */}
                <div>
                  <div className="flex justify-between text-xs text-neutral-400 font-semibold">
                    <span>Pattern Rotation</span>
                    <span>{arConfig.rotate}&deg;</span>
                  </div>
                  <input
                    type="range"
                    min="-180"
                    max="180"
                    step="5"
                    value={arConfig.rotate}
                    onChange={(e) => setArConfig(prev => ({ ...prev, rotate: parseInt(e.target.value) }))}
                    className="w-full h-1 mt-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-henna-500"
                  />
                </div>

                {/* Translate X */}
                <div>
                  <div className="flex justify-between text-xs text-neutral-400 font-semibold">
                    <span>Shift Left / Right (X)</span>
                    <span>{arConfig.translateX}px</span>
                  </div>
                  <input
                    type="range"
                    min="-250"
                    max="250"
                    step="5"
                    value={arConfig.translateX}
                    onChange={(e) => setArConfig(prev => ({ ...prev, translateX: parseInt(e.target.value) }))}
                    className="w-full h-1 mt-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-henna-500"
                  />
                </div>

                {/* Translate Y */}
                <div>
                  <div className="flex justify-between text-xs text-neutral-400 font-semibold">
                    <span>Shift Up / Down (Y)</span>
                    <span>{arConfig.translateY}px</span>
                  </div>
                  <input
                    type="range"
                    min="-250"
                    max="250"
                    step="5"
                    value={arConfig.translateY}
                    onChange={(e) => setArConfig(prev => ({ ...prev, translateY: parseInt(e.target.value) }))}
                    className="w-full h-1 mt-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-henna-500"
                  />
                </div>

                {/* Opacity */}
                <div>
                  <div className="flex justify-between text-xs text-neutral-400 font-semibold">
                    <span>Blend Intensity (Opacity)</span>
                    <span>{Math.round(arConfig.opacity * 100)}%</span>
                  </div>
                  <input
                    type="range"
                    min="0.1"
                    max="1.0"
                    step="0.05"
                    value={arConfig.opacity}
                    onChange={(e) => setArConfig(prev => ({ ...prev, opacity: parseFloat(e.target.value) }))}
                    className="w-full h-1 mt-1.5 bg-neutral-800 rounded-lg appearance-none cursor-pointer accent-henna-500"
                  />
                </div>
              </div>

              {/* Blend Mode controls */}
              <div className="space-y-1.5">
                <span className="text-xs text-neutral-400 font-semibold">Camera Blend Mode</span>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <button
                    onClick={() => setArConfig(prev => ({ ...prev, blendMode: 'multiply' }))}
                    className={`py-1.5 px-3 rounded-lg border text-center font-bold transition-all ${
                      arConfig.blendMode === 'multiply'
                        ? 'border-henna-600 bg-henna-950 text-white'
                        : 'border-white/10 text-neutral-400 hover:text-white'
                    }`}
                  >
                    Henna Ink (Multiply)
                  </button>
                  <button
                    onClick={() => setArConfig(prev => ({ ...prev, blendMode: 'normal' }))}
                    className={`py-1.5 px-3 rounded-lg border text-center font-bold transition-all ${
                      arConfig.blendMode === 'normal'
                        ? 'border-henna-600 bg-henna-950 text-white'
                        : 'border-white/10 text-neutral-400 hover:text-white'
                    }`}
                  >
                    Opaque Stamp
                  </button>
                </div>
              </div>
            </div>

            {/* Action Bar Footer */}
            <div className="space-y-2 border-t border-white/10 pt-4 text-xs font-semibold">
              <button
                onClick={() => setArConfig(prev => ({ 
                  ...prev, 
                  facingMode: prev.facingMode === 'user' ? 'environment' : 'user' 
                }))}
                className="w-full rounded-lg bg-neutral-900 border border-white/10 hover:bg-neutral-800 py-2.5 text-center transition-colors flex items-center justify-center gap-1.5"
              >
                <RefreshCw size={14} />
                Flip Camera Mode
              </button>
              
              <button
                onClick={() => setArConfig({
                  rotate: 0,
                  scale: 1.0,
                  translateX: 0,
                  translateY: 0,
                  opacity: 0.85,
                  blendMode: 'multiply',
                  enableTracking: true,
                  facingMode: arConfig.facingMode
                })}
                className="w-full rounded-lg bg-neutral-900 border border-white/10 hover:bg-neutral-800 py-2.5 text-center transition-colors flex items-center justify-center gap-1.5"
              >
                Reset Controls
              </button>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
