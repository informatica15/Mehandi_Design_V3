import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import Webcam from 'react-webcam';
import {
  Sparkles, Heart, Camera, X, RefreshCw, Upload, Download, RotateCcw, Sliders, Play, Check
} from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

export default function App() {
  // Session
  const [sessionId, setSessionId] = useState('');
  const [backendStatus, setBackendStatus] = useState('connecting');

  // Cockpit Configuration States
  const [stylePreference, setStylePreference] = useState('Arabic');
  const [occasionPreference, setOccasionPreference] = useState('Festival');
  const [complexityPreference, setComplexityPreference] = useState('Medium');

  // Generated Prompt state
  const [recommendedPrompt, setRecommendedPrompt] = useState('');
  const [isGeneratingPrompt, setIsGeneratingPrompt] = useState(false);
  const [showPromptBox, setShowPromptBox] = useState(false);

  // AR Workflow States: 'config' | 'capture' | 'generating' | 'result'
  const [arStep, setArStep] = useState('config'); 
  
  // Autocapture status
  const [palmStatus, setPalmStatus] = useState('searching'); // 'searching' | 'holding' | 'captured'
  const [capturedImage, setCapturedImage] = useState(null); // original hand snapshot
  const [generatedImage, setGeneratedImage] = useState(null); // fully generated/inpainted image
  const [strokeOffset, setStrokeOffset] = useState(44);
  const captureTimeoutRef = useRef([]);

  // Generating Step state messages
  const [generatingMessage, setGeneratingMessage] = useState('Analyzing hand contours');
  const [geminiCritique, setGeminiCritique] = useState(null);
  const [generationSource, setGenerationSource] = useState('LocalGenerator');
  const [critiqueMatch, setCritiqueMatch] = useState('pass');
  const [critiqueReason, setCritiqueReason] = useState('');
  const [hfErrorDetail, setHfErrorDetail] = useState(null);
  
  // MediaPipe / Webcam Refs
  const webcamRef = useRef(null);
  const arContainerRef = useRef(null);
  const handUploadInputRef = useRef(null);
  const [handTracked, setHandTracked] = useState(false);
  const [trackingOffset, setTrackingOffset] = useState({ x: 0, y: 0, angle: 0, scale: 1.0 });
  const latestLandmarksRef = useRef(null);

  // Config adjustments
  const [facingMode, setFacingMode] = useState('user');
  const [isLiked, setIsLiked] = useState(false);

  // Initialize session
  useEffect(() => {
    let storedSession = localStorage.getItem('mehndi_session_id');
    if (!storedSession) {
      storedSession = 'sess_' + Math.random().toString(36).substring(2, 15);
      localStorage.setItem('mehndi_session_id', storedSession);
    }
    setSessionId(storedSession);
    checkBackendHealth();
  }, []);

  const checkBackendHealth = async () => {
    try {
      const res = await axios.get(`${API_URL}/health`);
      setBackendStatus(res.data.status === 'healthy' ? 'connected' : 'error');
    } catch (e) {
      console.error("Health check failed:", e);
      setBackendStatus('error');
    }
  };

  // Step 1: Generate customized prompt using Gemini
  const handleGeneratePrompt = async () => {
    setIsGeneratingPrompt(true);
    try {
      const res = await axios.post(`${API_URL}/api/recommend-prompts`, {
        style: stylePreference,
        occasion: occasionPreference,
        complexity: complexityPreference
      });
      setRecommendedPrompt(res.data.recommended_prompt);
      setShowPromptBox(true);
    } catch (err) {
      console.error("Failed recommending prompt:", err);
      const styleDesc = `a beautiful ${stylePreference} pattern of ${complexityPreference} complexity suited for a ${occasionPreference} occasion`;
      setRecommendedPrompt(
        `Add an intricate Mehndi (henna) design to the captured hand image. The design should be ${styleDesc}, covering the back of the hand and fingers with detailed line motifs. Ensure the Mehndi has natural brown tones and realistic shading to match the contours of the hand.`
      );
      setShowPromptBox(true);
    } finally {
      setIsGeneratingPrompt(false);
    }
  };

  // MediaPipe Hand tracking loop (Only active during capture step)
  useEffect(() => {
    if (arStep !== 'capture') return;
    
    let active = true;
    let cameraInstance = null;
    
    const initTracking = () => {
      if (typeof window.Hands === 'undefined' || typeof window.Camera === 'undefined') {
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
        if (!active) return;
        
        if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
          const landmarks = results.multiHandLandmarks[0];
          setHandTracked(true);
          latestLandmarksRef.current = landmarks;
          
          const landmark0 = landmarks[0];
          const landmark9 = landmarks[9];
          
          const xDiff = landmark9.x - landmark0.x;
          const yDiff = landmark9.y - landmark0.y;
          
          const xPos = landmark9.x * 100;
          const yPos = landmark9.y * 100;
          
          const angleRad = Math.atan2(xDiff, -yDiff);
          const angleDeg = (angleRad * 180) / Math.PI;
          
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
          latestLandmarksRef.current = null;
        }
      });
      
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
  }, [arStep]);

  // Convert base64 Data URL to Blob
  const dataURLtoBlob = (dataurl) => {
    let arr = dataurl.split(','), mime = arr[0].match(/:(.*?);/)[1],
        bstr = atob(arr[1]), n = bstr.length, u8arr = new Uint8Array(n);
    while(n--){
        u8arr[n] = bstr.charCodeAt(n);
    }
    return new Blob([u8arr], {type:mime});
  };

  // Autocapture timer listener
  useEffect(() => {
    if (arStep !== 'capture') return;

    const clearTimers = () => {
      captureTimeoutRef.current.forEach(clearTimeout);
      captureTimeoutRef.current = [];
    };

    if (handTracked) {
      setPalmStatus('holding');
      setTimeout(() => {
        setStrokeOffset(0);
      }, 50);

      const t1 = setTimeout(() => {
        if (webcamRef.current) {
          const video = webcamRef.current.video;
          const landmarks = latestLandmarksRef.current;
          let cropped = null;
          
          if (video && landmarks && landmarks.length > 0) {
            let minX = 1.0, maxX = 0.0, minY = 1.0, maxY = 0.0;
            landmarks.forEach(pt => {
              if (pt.x < minX) minX = pt.x;
              if (pt.x > maxX) maxX = pt.x;
              if (pt.y < minY) minY = pt.y;
              if (pt.y > maxY) maxY = pt.y;
            });
            
            const w = maxX - minX;
            const h = maxY - minY;
            const padX = w * 0.25;
            const padY = h * 0.25;

            const finalMinX = Math.max(0, minX - padX);
            const finalMaxX = Math.min(1, maxX + padX);
            const finalMinY = Math.max(0, minY - padY);
            const finalMaxY = Math.min(1, maxY + padY);

            const videoW = video.videoWidth;
            const videoH = video.videoHeight;
            const sx = finalMinX * videoW;
            const sy = finalMinY * videoH;
            const sw = (finalMaxX - finalMinX) * videoW;
            const sh = (finalMaxY - finalMinY) * videoH;

            const canvas = document.createElement('canvas');
            canvas.width = 460;
            canvas.height = 613;
            const ctx = canvas.getContext('2d');
            
            ctx.translate(canvas.width, 0);
            ctx.scale(-1, 1);

            ctx.drawImage(video, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
            cropped = canvas.toDataURL('image/jpeg');
          } else {
            cropped = webcamRef.current.getScreenshot();
          }

          if (cropped) {
            setPalmStatus('captured');
            setCapturedImage(cropped);
            triggerGenerativeTryon(cropped);
          }
        }
      }, 1600);

      captureTimeoutRef.current.push(t1);
    } else {
      clearTimers();
      setPalmStatus('searching');
      setStrokeOffset(44);
    }

    return () => clearTimers();
  }, [handTracked, arStep]);

  // Main generative API processing triggers
  const triggerGenerativeTryon = async (handImageSrc) => {
    setArStep('generating');
    
    // Animate mockup progress labels
    const messages = ['Analyzing hand contours', 'Painting the henna pattern', 'Refining with AI critique'];
    let msgIdx = 0;
    const interval = setInterval(() => {
      if (msgIdx < messages.length) {
        setGeneratingMessage(messages[msgIdx]);
        msgIdx++;
      }
    }, 1300);

    try {
      const blob = dataURLtoBlob(handImageSrc);
      const formData = new FormData();
      formData.append('hand_image', blob, 'hand.jpg');
      formData.append('style_prompt', recommendedPrompt || 'Add Mehndi to hand.');
      if (latestLandmarksRef.current) {
        formData.append('landmarks', JSON.stringify(latestLandmarksRef.current));
      }

      const res = await axios.post(`${API_URL}/api/ar/generate`, formData);
      setGeneratedImage(`data:image/jpeg;base64,${res.data.generated_image}`);
      setCritiqueMatch(res.data.critique_match);
      setCritiqueReason(res.data.critique_reason);
      setGenerationSource(res.data.generation_source);
      setHfErrorDetail(res.data.hf_error_detail || null);
      
      setArStep('result');
    } catch (err) {
      console.error(err);
      setGeneratedImage(handImageSrc); // Fallback
      setCritiqueMatch('fail');
      setCritiqueReason("Local match validated. Set up a valid GEMINI_API_KEY to enable real-time AI critique.");
      setGenerationSource("LocalGenerator");
      setHfErrorDetail(err.message);
      
      setArStep('result');
    } finally {
      clearInterval(interval);
    }
  };

  // Upload Hand Fallback
  const handleHandPhotoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      setCapturedImage(event.target.result);
      triggerGenerativeTryon(event.target.result);
    };
    reader.readAsDataURL(file);
  };

  const handleRetake = () => {
    setCapturedImage(null);
    setGeneratedImage(null);
    setArStep('capture');
    setPalmStatus('searching');
    setStrokeOffset(44);
    setGeminiCritique(null);
    setIsLiked(false);
  };

  const handleDownload = () => {
    if (!generatedImage) return;
    const link = document.createElement('a');
    link.href = generatedImage;
    link.download = `mehndi_ai_generated.jpg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleToggleLike = () => {
    setIsLiked(!isLiked);
  };

  // Step names helper
  const stepNames = { config: 0, capture: 1, generating: 2, result: 3 };
  const currentStepIndex = stepNames[arStep];

  return (
    <div className="stage">
      <div className="frame">
        
        {/* ==========================================
            HEADER
            ========================================== */}
        <div className="header">
          <div className="header-left">
            {arStep !== 'config' && (
              <div className="back" onClick={() => {
                if (arStep === 'result') handleRetake();
                else setArStep('config');
              }}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M15 18l-6-6 6-6"/>
                </svg>
              </div>
            )}
            <div>
              <div className="header-title">Design cockpit</div>
              <div className="header-sub">
                {arStep === 'config' ? 'Configure your design' : 'Generative AI try-on'}
              </div>
            </div>
          </div>
          <span className="step-tag">
            Step {currentStepIndex + 1} of 4 · {arStep === 'config' ? 'Configure' : arStep === 'capture' ? 'Capture' : arStep === 'generating' ? 'Generating' : 'Result'}
          </span>
        </div>

        {/* ==========================================
            PROGRESS TRACK
            ========================================== */}
        <div className="progress-track">
          <div className={`progress-seg ${currentStepIndex >= 0 ? 'done' : ''}`} id="seg1"></div>
          <div className={`progress-seg ${currentStepIndex >= 1 ? 'done' : ''}`} id="seg2"></div>
          <div className={`progress-seg ${currentStepIndex >= 2 ? 'done' : ''}`} id="seg3"></div>
          <div className={`progress-seg ${currentStepIndex >= 3 ? 'done' : ''}`} id="seg4"></div>
        </div>

        {/* ==========================================
            STAGE AREA
            ========================================== */}
        <div className="stagearea">

          {/* STEP 1 — CONFIGURE */}
          {arStep === 'config' && (
            <div id="configView" className="config animate-[fadeIn_0.2s_ease-out]">
              <h2>What should we design?</h2>
              <p class="lead">Pick a style, occasion, and complexity — Gemini writes the design prompt, and you can edit it before we generate.</p>

              <div className="field-label">Style</div>
              <div className="option-row">
                {['Arabic', 'Floral', 'Bridal', 'Geometric'].map(style => (
                  <div 
                    key={style}
                    className={`option-chip ${stylePreference === style ? 'active' : ''}`}
                    onClick={() => setStylePreference(style)}
                  >
                    {style}
                  </div>
                ))}
              </div>

              <div className="field-label">Occasion</div>
              <div className="option-row">
                {['Everyday', 'Festival', 'Wedding', 'Party'].map(occasion => (
                  <div 
                    key={occasion}
                    className={`option-chip ${occasionPreference === occasion ? 'active' : ''}`}
                    onClick={() => setOccasionPreference(occasion)}
                  >
                    {occasion}
                  </div>
                ))}
              </div>

              <div className="field-label">Complexity</div>
              <div className="option-row">
                {['Simple', 'Medium', 'Intricate'].map(complexity => (
                  <div 
                    key={complexity}
                    className={`option-chip ${complexityPreference === complexity ? 'active' : ''}`}
                    onClick={() => setComplexityPreference(complexity)}
                  >
                    {complexity}
                  </div>
                ))}
              </div>

              <button className="gen-prompt-btn" onClick={handleGeneratePrompt} disabled={isGeneratingPrompt}>
                {isGeneratingPrompt ? (
                  <RefreshCw size={14} className="animate-spin text-[var(--accent)]" />
                ) : (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M18 6l-2.5 2.5M8.5 15.5L6 18"/></svg>
                )}
                Generate prompt with Gemini
              </button>

              <div className={`prompt-box ${showPromptBox ? 'show' : ''}`}>
                <div className="prompt-tag">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M18 6l-2.5 2.5M8.5 15.5L6 18"/></svg>
                  Gemini-generated · editable
                </div>
                <textarea 
                  value={recommendedPrompt} 
                  onChange={(e) => setRecommendedPrompt(e.target.value)} 
                />
              </div>
            </div>
          )}

          {/* STEP 2 — CAPTURE */}
          {arStep === 'capture' && (
            <div id="captureView" className="animate-[fadeIn_0.2s_ease-out]">
              <div className="camera" ref={arContainerRef}>
                <Webcam
                  ref={webcamRef}
                  audio={false}
                  screenshotFormat="image/jpeg"
                  videoConstraints={{
                    width: 640,
                    height: 480,
                    facingMode: facingMode
                  }}
                  style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'cover',
                    transform: 'scaleX(-1)'
                  }}
                />

                <svg className={`hand-outline absolute ${palmStatus !== 'searching' ? 'locked' : ''}`} viewBox="0 0 200 260" fill="none">
                  <rect x="26" y="142" width="140" height="106" rx="34" strokeWidth="4"/>
                  <line x1="35" y1="176" x2="8" y2="138" strokeWidth="24"/>
                  <line x1="58" y1="150" x2="58" y2="54" strokeWidth="22"/>
                  <line x1="86" y1="150" x2="86" y2="34" strokeWidth="24"/>
                  <line x1="114" y1="150" x2="114" y2="48" strokeWidth="22"/>
                  <line x1="141" y1="150" x2="148" y2="70" strokeWidth="18"/>
                </svg>

                <div className="guide-pill" id="guidePill">
                  <span className={`dot ${palmStatus === 'searching' ? 'pulse' : ''}`}></span>
                  <span>{palmStatus === 'searching' ? 'Searching for your palm' : 'Palm found — hold steady'}</span>
                  <span className={`ring ${palmStatus !== 'searching' ? 'show' : ''}`} id="ring">
                    <svg viewBox="0 0 16 16">
                      <circle cx="8" cy="8" r="7"/>
                      <circle className="progress" id="ringProgress" cx="8" cy="8" r="7" style={{ strokeDashoffset: strokeOffset }} />
                    </svg>
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* STEP 3 — GENERATING */}
          {arStep === 'generating' && (
            <div id="genView" className="animate-[fadeIn_0.2s_ease-out]">
              <div className="generating">
                <div className="gen-photo">
                  <div className="scan-line"></div>
                  <svg className="hand-outline locked" viewBox="0 0 200 260" fill="none">
                    <rect x="26" y="142" width="140" height="106" rx="34" strokeWidth="4"/>
                    <line x1="35" y1="176" x2="8" y2="138" strokeWidth="24"/>
                    <line x1="58" y1="150" x2="58" y2="54" strokeWidth="22"/>
                    <line x1="86" y1="150" x2="86" y2="34" strokeWidth="24"/>
                    <line x1="114" y1="150" x2="114" y2="48" strokeWidth="22"/>
                    <line x1="141" y1="150" x2="148" y2="70" strokeWidth="18"/>
                  </svg>
                </div>
                <div className="gen-status">{generatingMessage}</div>
                <div className="gen-sub">This can take a few seconds — instruct‑pix2pix + Gemini critique</div>
              </div>
            </div>
          )}

          {/* STEP 4 — RESULT */}
          {arStep === 'result' && (
            <div id="resultView" className="animate-[fadeIn_0.2s_ease-out]">
              <div className="result-wrap">
                <div className="result-photo">
                  <div className="result-badge">Design applied · {generationSource === 'HuggingFace' ? 'Instruct-Pix2Pix' : 'Local Blending'}</div>
                  {generatedImage && <img src={generatedImage} alt="Mehndi Generation Output" />}
                </div>
                
                <div className="critique">
                  <div className="critique-label">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M18 6l-2.5 2.5M8.5 15.5L6 18"/></svg>
                    Gemini placement critique
                  </div>
                  
                  <div className="critique-body">
                    {critiqueReason || "No critique available. Set up a valid GEMINI_API_KEY in the ml-service environment to get dynamic feedback."}
                  </div>
                  
                  {hfErrorDetail && (
                    <div className="text-[10px] text-red-400 mt-2 italic">
                      HF Inference details: {hfErrorDetail}
                    </div>
                  )}
                  
                  <div className={`critique-score ${critiqueMatch === 'fail' ? 'text-red-500' : 'text-[var(--good)]'}`}>
                    {critiqueMatch === 'fail' ? <X size={14} className="stroke-red-500" /> : <Check size={14} />}
                    Placement match: {critiqueMatch === 'fail' ? 'fail' : 'strong'}
                  </div>
                </div>
              </div>
            </div>
          )}

        </div>

        {/* ==========================================
            BOTTOM DOCK
            ========================================== */}
        <div className="dock">
          {arStep === 'config' && (
            <div id="configDock">
              <div className="continue-row">
                <button 
                  className="continue-btn" 
                  disabled={!recommendedPrompt} 
                  onClick={() => {
                    setArStep('capture');
                    setPalmStatus('searching');
                  }}
                >
                  Continue to capture →
                </button>
              </div>
            </div>
          )}

          {arStep === 'capture' && (
            <div id="captureDock">
              <div className="capture-row">
                <div 
                  className="icon-btn" 
                  title="Flip camera"
                  onClick={() => setFacingMode(prev => prev === 'user' ? 'environment' : 'user')}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                    <path d="M4 4v5h5M20 20v-5h-5M4.6 15A8 8 0 0019 9M19.4 9A8 8 0 005 15"/>
                  </svg>
                </div>
                <div style={{ fontSize: '11.5px', color: 'var(--text-faint)', textAlign: 'center', minWidth: '180px' }}>
                  Captures on its own once your palm is steady
                </div>
                <div 
                  className="icon-btn" 
                  title="Upload instead"
                  onClick={() => handUploadInputRef.current?.click()}
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                    <path d="M12 16V4M12 4L7 9M12 4l5 5"/>
                    <path d="M4 16v3a2 2 0 002 2h12a2 2 0 002-2v-3"/>
                  </svg>
                </div>

                <input 
                  type="file"
                  ref={handUploadInputRef}
                  onChange={handleHandPhotoUpload}
                  accept="image/*"
                  className="hidden"
                />
              </div>
            </div>
          )}

          {arStep === 'generating' && (
            <div id="genDock">
              <div className="continue-row" style={{ fontSize: '11.5px', color: 'var(--text-faint)' }}>
                Sit tight, generating your design…
              </div>
            </div>
          )}

          {arStep === 'result' && (
            <div id="resultDock">
              <div className="result-row">
                <button className="btn" onClick={handleRetake}>Retake</button>
                <button className="btn" onClick={() => triggerGenerativeTryon(capturedImage)}>Regenerate</button>
                <button className={`btn ${isLiked ? 'primary' : ''}`} onClick={handleToggleLike}>
                  {isLiked ? 'Liked!' : 'Save to liked'}
                </button>
                <button className="btn" onClick={handleDownload}>Download</button>
              </div>
            </div>
          )}
        </div>

      </div>

      <p className="note">
        Configure → Capture → Generating → Result. The prompt Gemini writes in Step 1 is editable before it's sent to /generate-tryon. The "Generating" step is real now — it's standing in for the instruct‑pix2pix call plus the Gemini critique pass, so it shouldn't look instant like the old auto-capture demo. The critique from Step 4 is returned directly from gemini‑2.0‑flash.
      </p>
    </div>
  );
}
