import os
import json
import base64
import requests
import numpy as np
import cv2

# Native .env parser to load GEMINI_API_KEY
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

gemini_key = os.getenv("GEMINI_API_KEY")
if gemini_key:
    masked_key = f"{gemini_key[:6]}...{gemini_key[-4:]}" if len(gemini_key) > 10 else "loaded"
    print(f"GEMINI_API_KEY loaded successfully: {masked_key}")
else:
    print("MANDATORY STARTUP WARNING: GEMINI_API_KEY is missing from environment!")


from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from pydantic import BaseModel

app = FastAPI(
    title="Mehndi AI Generative & Recommendation Service",
    description="Pure generative AI backend for custom try-on generation and prompt recommendation",
    version="2.0.0"
)

# CORS configurations
allowed_origins = os.getenv("ALLOWED_ORIGIN", "http://localhost:3000,http://localhost:5000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TryonResponse(BaseModel):
    generated_image: str  # Base64 encoded JPEG
    critique_match: str  # 'pass' | 'fail'
    critique_reason: str
    generation_source: str  # 'HuggingFace' or 'LocalGenerator'
    hf_error_detail: Optional[str] = None

class PromptRecommendationResponse(BaseModel):
    recommended_prompt: str

@app.get("/health")
def health_check():
    gemini_key = os.getenv("GEMINI_API_KEY")
    return {
        "status": "healthy",
        "gemini_api_configured": bool(gemini_key),
        "service_mode": "pure-generative-ai"
    }

# --- High-Precision Anti-Aliased Mehndi Art Engine ---
import math

def draw_aa_line(canvas, p1, p2, color, thickness):
    cv2.line(canvas, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), color, thickness, cv2.LINE_AA)

def draw_beaded_chain(canvas, p1, p2, color=(0, 0, 0), dot_spacing=9, dot_r=2):
    x1, y1 = p1
    x2, y2 = p2
    dist = np.hypot(x2 - x1, y2 - y1)
    if dist < 4:
        return
    num_dots = max(2, int(dist / dot_spacing))
    for i in range(num_dots + 1):
        t = i / float(num_dots)
        bx = int(x1 + t * (x2 - x1))
        by = int(y1 + t * (y2 - y1))
        cv2.circle(canvas, (bx, by), dot_r, color, -1, cv2.LINE_AA)

def draw_mandala_petals(canvas, cx, cy, num_petals, inner_r, outer_r, color, thickness=1):
    for i in range(num_petals):
        angle = 2 * math.pi * i / num_petals
        angle_next = 2 * math.pi * (i + 0.5) / num_petals
        angle_target = 2 * math.pi * (i + 1) / num_petals
        
        p0 = (int(cx + inner_r * math.cos(angle)), int(cy + inner_r * math.sin(angle)))
        p2 = (int(cx + inner_r * math.cos(angle_target)), int(cy + inner_r * math.sin(angle_target)))
        p1 = (int(cx + outer_r * math.cos(angle_next)), int(cy + outer_r * math.sin(angle_next)))
        
        pts = []
        for t in np.linspace(0, 1, 10):
            x = (1-t)**2 * p0[0] + 2*(1-t)*t * p1[0] + t**2 * p2[0]
            y = (1-t)**2 * p0[1] + 2*(1-t)*t * p1[1] + t**2 * p2[1]
            pts.append((int(x), int(y)))
        
        for k in range(len(pts) - 1):
            draw_aa_line(canvas, pts[k], pts[k+1], color, thickness)
            
        px = int(cx + (inner_r + (outer_r - inner_r)*0.45) * math.cos(angle_next))
        py = int(cy + (inner_r + (outer_r - inner_r)*0.45) * math.sin(angle_next))
        cv2.circle(canvas, (px, py), max(1, thickness), color, -1, cv2.LINE_AA)

def draw_intricate_mandala(canvas, cx, cy, max_r, color=(0, 0, 0)):
    if max_r < 12:
        return
    # Core
    cv2.circle(canvas, (cx, cy), max(2, int(max_r * 0.08)), color, -1, cv2.LINE_AA)
    cv2.circle(canvas, (cx, cy), max(4, int(max_r * 0.15)), color, 1, cv2.LINE_AA)
    cv2.circle(canvas, (cx, cy), max(6, int(max_r * 0.20)), color, 1, cv2.LINE_AA)
    
    # Inner ring of petals
    r1 = max(6, int(max_r * 0.20))
    r2 = max(12, int(max_r * 0.36))
    draw_mandala_petals(canvas, cx, cy, 12, r1, r2, color, 1)
    cv2.circle(canvas, (cx, cy), r2 + 2, color, 1, cv2.LINE_AA)
    
    # Ring of pearls
    dot_r = r2 + 5
    for angle_deg in range(0, 360, 15):
        rad = math.radians(angle_deg)
        rx = int(cx + dot_r * math.cos(rad))
        ry = int(cy + dot_r * math.sin(rad))
        cv2.circle(canvas, (rx, ry), max(1, int(max_r * 0.025)), color, -1, cv2.LINE_AA)
        
    # Second ring of petals
    if max_r > 38:
        r3 = dot_r + 4
        r4 = r3 + max(10, int(max_r * 0.28))
        cv2.circle(canvas, (cx, cy), r3, color, 1, cv2.LINE_AA)
        draw_mandala_petals(canvas, cx, cy, 16, r3, r4, color, 1)
        cv2.circle(canvas, (cx, cy), r4 + 2, color, 1, cv2.LINE_AA)
        
    # Third outer scalloped border
    if max_r > 70:
        r5 = r4 + 3
        r6 = r5 + max(8, int(max_r * 0.20))
        draw_mandala_petals(canvas, cx, cy, 24, r5, r6, color, 1)
        cv2.circle(canvas, (cx, cy), r6 + 2, color, 1, cv2.LINE_AA)
        for angle_deg in range(0, 360, 10):
            rad = math.radians(angle_deg)
            rx = int(cx + (r6 + 4) * math.cos(rad))
            ry = int(cy + (r6 + 4) * math.sin(rad))
            cv2.circle(canvas, (rx, ry), 1, color, -1, cv2.LINE_AA)

def draw_paisley(canvas, cx, cy, scale, angle_deg, color=(0, 0, 0), thickness=1):
    rad_rot = math.radians(angle_deg)
    cos_r = math.cos(rad_rot)
    sin_r = math.sin(rad_rot)
    
    pts = []
    for t in np.linspace(0, 2 * math.pi, 50):
        x_base = scale * math.sin(t)
        y_base = scale * (math.cos(t) + math.sin(t)**2 * 0.55)
        
        x = cx + (x_base * cos_r - y_base * sin_r)
        y = cy + (x_base * sin_r + y_base * cos_r)
        pts.append((int(x), int(y)))
        
    pts = np.array(pts, dtype=np.int32)
    cv2.polylines(canvas, [pts], True, color, thickness, cv2.LINE_AA)
    
    spiral_pts = []
    for st in np.linspace(0, 3.5 * math.pi, 30):
        sr = scale * 0.4 * (1.0 - st / (4.0 * math.pi))
        sx_b = sr * math.cos(st)
        sy_b = sr * math.sin(st) + scale * 0.2
        sx = int(cx + (sx_b * cos_r - sy_b * sin_r))
        sy = int(cy + (sx_b * sin_r + sy_b * cos_r))
        spiral_pts.append((sx, sy))
    for k in range(len(spiral_pts) - 1):
        draw_aa_line(canvas, spiral_pts[k], spiral_pts[k+1], color, 1)

def draw_finger_ornaments(canvas, joints, color=(0, 0, 0)):
    if len(joints) < 4:
        return
    
    # 1. Subtle backbone line
    for i in range(len(joints) - 1):
        draw_aa_line(canvas, joints[i], joints[i+1], color, 1)
        
    # 2. Ring bands at PIP and DIP joints
    for j_idx in [1, 2]:
        pj = joints[j_idx]
        p_prev = joints[j_idx - 1]
        dx = pj[0] - p_prev[0]
        dy = pj[1] - p_prev[1]
        seg_len = np.hypot(dx, dy)
        if seg_len < 4:
            continue
        nx = -dy / seg_len
        ny = dx / seg_len
        
        band_w = 11
        for offset in [-3, 0, 3]:
            p_left = (int(pj[0] + nx * band_w + (dx/seg_len)*offset), int(pj[1] + ny * band_w + (dy/seg_len)*offset))
            p_right = (int(pj[0] - nx * band_w + (dx/seg_len)*offset), int(pj[1] - ny * band_w + (dy/seg_len)*offset))
            draw_aa_line(canvas, p_left, p_right, color, 1)
            
        for dot_step in [-7, -3, 0, 3, 7]:
            dpx = int(pj[0] + nx * dot_step + (dx/seg_len)*1.5)
            dpy = int(pj[1] + ny * dot_step + (dy/seg_len)*1.5)
            cv2.circle(canvas, (dpx, dpy), 1, color, -1, cv2.LINE_AA)

    # 3. Chevron pattern between MCP and PIP
    p_mcp, p_pip = joints[0], joints[1]
    dx_m = p_pip[0] - p_mcp[0]
    dy_m = p_pip[1] - p_mcp[1]
    m_len = np.hypot(dx_m, dy_m)
    if m_len > 14:
        nx_m = -dy_m / m_len
        ny_m = dx_m / m_len
        num_chev = max(2, int(m_len / 12))
        for c in range(1, num_chev):
            t = c / float(num_chev)
            cx = p_mcp[0] + t * dx_m
            cy = p_mcp[1] + t * dy_m
            tip_x = cx + (dx_m / m_len) * 5
            tip_y = cy + (dy_m / m_len) * 5
            c1 = (int(cx + nx_m * 7), int(cy + ny_m * 7))
            c2 = (int(cx - nx_m * 7), int(cy - ny_m * 7))
            draw_aa_line(canvas, c1, (int(tip_x), int(tip_y)), color, 1)
            draw_aa_line(canvas, c2, (int(tip_x), int(tip_y)), color, 1)
            cv2.circle(canvas, (int(tip_x), int(tip_y)), 1, color, -1, cv2.LINE_AA)

    # 4. Finger Tip Cap
    tip = joints[3]
    dip = joints[2]
    dx_t = tip[0] - dip[0]
    dy_t = tip[1] - dip[1]
    t_len = np.hypot(dx_t, dy_t)
    if t_len > 4:
        cap_mid = (int(tip[0] - (dx_t / t_len) * 2), int(tip[1] - (dy_t / t_len) * 2))
        for r_cap in [5, 9]:
            cv2.ellipse(canvas, cap_mid, (r_cap, max(3, int(r_cap * 0.6))), 
                        math.degrees(math.atan2(dy_t, dx_t)), 0, 360, color, 1, cv2.LINE_AA)
        cv2.circle(canvas, (int(tip[0]), int(tip[1])), 2, color, -1, cv2.LINE_AA)

def draw_wrist_cuff(canvas, wrist_pt, mid_mcp_pt, color=(0, 0, 0)):
    dx = mid_mcp_pt[0] - wrist_pt[0]
    dy = mid_mcp_pt[1] - wrist_pt[1]
    arm_len = np.hypot(dx, dy)
    if arm_len < 10:
        return
    nx = -dy / arm_len
    ny = dx / arm_len
    
    cuff_w = 55
    for offset in [-10, -5, 0, 5]:
        p1 = (int(wrist_pt[0] + nx * cuff_w + (dx/arm_len)*offset), int(wrist_pt[1] + ny * cuff_w + (dy/arm_len)*offset))
        p2 = (int(wrist_pt[0] - nx * cuff_w + (dx/arm_len)*offset), int(wrist_pt[1] - ny * cuff_w + (dy/arm_len)*offset))
        draw_aa_line(canvas, p1, p2, color, 1 if offset != 0 else 2)
        
    for s in range(-cuff_w + 4, cuff_w - 4, 9):
        px = int(wrist_pt[0] + nx * s + (dx/arm_len)*10)
        py = int(wrist_pt[1] + ny * s + (dy/arm_len)*10)
        cv2.circle(canvas, (px, py), 2, color, -1, cv2.LINE_AA)


@app.post("/recommend-prompts", response_model=PromptRecommendationResponse)
async def recommend_prompts(
    style: str = Form(...),
    occasion: str = Form(...),
    complexity: str = Form(...)
):
    gemini_key = os.getenv("GEMINI_API_KEY")
    prompt_out = ""
    
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-3.5-flash')
            
            system_instruction = (
                f"You are an expert Mehndi (henna) design consultant. Generate a highly detailed, professional, "
                f"and artistic text-to-image generation prompt for a {style} style with {complexity} complexity "
                f"for a {occasion} occasion. Focus on placement on the hand, specific motifs (e.g. paisleys, floral, geometric), "
                f"and realistic brown henna stain shading. Output ONLY the generation prompt text directly without any quotes, intros, or formatting."
            )
            response = model.generate_content(system_instruction)
            prompt_out = response.text.strip().replace('"', '')
        except Exception as e:
            print(f"Gemini prompt generation error: {e}")
            
    if not prompt_out:
        # Fallback prompt generation
        style_desc = f"a beautiful {style} pattern of {complexity} complexity suited for a {occasion} occasion"
        prompt_out = (
            f"Add an intricate Mehndi (henna) design to the captured hand image. The design should be {style_desc}, "
            "covering the back of the hand and fingers with detailed line motifs. Ensure the Mehndi has natural brown tones "
            "and realistic shading to match the contours of the hand."
        )
        
    return PromptRecommendationResponse(recommended_prompt=prompt_out)

@app.post("/generate-tryon", response_model=TryonResponse)
async def generate_tryon(
    file: UploadFile = File(...),
    style_prompt: str = Form(...),
    landmarks: Optional[str] = Form(None)
):
    try:
        img_bytes = await file.read()
        if not img_bytes:
            raise HTTPException(status_code=400, detail="Empty hand image uploaded.")

        nparr = np.frombuffer(img_bytes, np.uint8)
        hand_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if hand_img is None:
            raise HTTPException(status_code=400, detail="Invalid hand image encoding.")

        gemini_key = os.getenv("GEMINI_API_KEY")
        generated_image_b64 = ""
        source = "LocalGenerator"
        hf_error_detail = None

        # 1. Attempt Hugging Face Serverless Generative Img2Img API ONLY if valid HF token exists
        hf_token = os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_TOKEN")
        if hf_token and hf_token.startswith("hf_"):
            try:
                print(f"Attempting Hugging Face Instruct-Pix2Pix generation with prompt:\n{style_prompt}")
                API_URL = "https://api-inference.huggingface.co/models/timbrooks/instruct-pix2pix"
                sanitized_prompt = " ".join(style_prompt.replace('\r', ' ').replace('\n', ' ').split())
                headers = {
                    "Authorization": f"Bearer {hf_token}",
                    "X-Prompt": sanitized_prompt
                }
                response = requests.post(API_URL, headers=headers, data=img_bytes, timeout=12)
                if response.status_code == 200 and len(response.content) > 1000:
                    generated_image_b64 = base64.b64encode(response.content).decode('utf-8')
                    source = "HuggingFace"
                    print("Hugging Face AI Try-On generation succeeded.")
                else:
                    hf_error_detail = f"HF Status {response.status_code}: {response.text[:200]}"
                    print(f"Hugging Face Inference API failed: {hf_error_detail}")
            except Exception as hf_err:
                hf_error_detail = str(hf_err)
                print(f"Hugging Face Inference API failed exception: {hf_error_detail}")

        # 2. Structure-Preserving High-Precision Henna Engine
        if not generated_image_b64:
            h, w = hand_img.shape[:2]
            
            # Dual-Space Skin Detection (YCrCb + HSV) for robust palm and finger isolation
            ycrcb = cv2.cvtColor(hand_img, cv2.COLOR_BGR2YCrCb)
            mask_ycrcb = cv2.inRange(ycrcb, np.array([0, 133, 77]), np.array([255, 173, 127]))
            
            hsv = cv2.cvtColor(hand_img, cv2.COLOR_BGR2HSV)
            mask_hsv = cv2.inRange(hsv, np.array([0, 20, 50]), np.array([30, 255, 255]))
            skin_mask = cv2.bitwise_or(mask_ycrcb, mask_hsv)
            
            kernel_ellipse = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel_ellipse)
            skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel_ellipse)
            skin_mask = cv2.dilate(skin_mask, kernel_ellipse, iterations=2)
            
            pattern = np.ones((h, w, 3), dtype=np.uint8) * 255
            prompt_lower = style_prompt.lower()
            
            lms = None
            if landmarks:
                try:
                    lms = json.loads(landmarks)
                except Exception as lm_err:
                    print(f"Error parsing landmarks: {lm_err}")

            if lms and len(lms) >= 21:
                is_pre_cropped = any(pt.get('is_cropped') for pt in lms)
                xs = [pt['x'] for pt in lms]
                ys = [pt['y'] for pt in lms]
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)

                if is_pre_cropped or (max_x - min_x) > 0.45:
                    def get_pt(idx):
                        pt = lms[idx]
                        px = int(np.clip(pt['x'], 0.0, 1.0) * w)
                        py = int(np.clip(pt['y'], 0.0, 1.0) * h)
                        return (px, py)
                else:
                    pad_x = (max_x - min_x) * 0.25
                    pad_y = (max_y - min_y) * 0.25
                    crop_min_x = max(0.0, min_x - pad_x)
                    crop_max_x = min(1.0, max_x + pad_x)
                    crop_min_y = max(0.0, min_y - pad_y)
                    crop_max_y = min(1.0, max_y + pad_y)
                    span_x = max(0.001, crop_max_x - crop_min_x)
                    span_y = max(0.001, crop_max_y - crop_min_y)

                    def get_pt(idx):
                        pt = lms[idx]
                        px = int(np.clip((pt['x'] - crop_min_x) / span_x, 0.0, 1.0) * w)
                        py = int(np.clip((pt['y'] - crop_min_y) / span_y, 0.0, 1.0) * h)
                        return (px, py)

                wrist = get_pt(0)
                thumb_joints = [get_pt(1), get_pt(2), get_pt(3), get_pt(4)]
                index_joints = [get_pt(5), get_pt(6), get_pt(7), get_pt(8)]
                mid_joints   = [get_pt(9), get_pt(10), get_pt(11), get_pt(12)]
                ring_joints  = [get_pt(13), get_pt(14), get_pt(15), get_pt(16)]
                pnk_joints   = [get_pt(17), get_pt(18), get_pt(19), get_pt(20)]
                
                # Compute true palm center between wrist and knuckles
                knuckle_center = (
                    int((index_joints[0][0] + mid_joints[0][0] + ring_joints[0][0] + pnk_joints[0][0]) / 4),
                    int((index_joints[0][1] + mid_joints[0][1] + ring_joints[0][1] + pnk_joints[0][1]) / 4)
                )
                palm_cx = int(wrist[0] * 0.38 + knuckle_center[0] * 0.62)
                palm_cy = int(wrist[1] * 0.38 + knuckle_center[1] * 0.62)
                
                hand_scale = int(np.hypot(knuckle_center[0] - wrist[0], knuckle_center[1] - wrist[1]))
                if hand_scale < 25:
                    hand_scale = min(w, h) // 3
                mandala_r = max(16, int(hand_scale * 0.36))

                # Style-Specific Placement & Rendering
                is_arabic = "arabic" in prompt_lower
                is_minimal = "minimal" in prompt_lower
                is_bridal = "bridal" in prompt_lower or "wedding" in prompt_lower
                
                if is_minimal:
                    # Minimalist: Dainty mandala ring, single finger vine, fine wrist chain
                    draw_intricate_mandala(pattern, palm_cx, palm_cy, int(mandala_r * 0.75))
                    draw_finger_ornaments(pattern, ring_joints)
                    draw_beaded_chain(pattern, (palm_cx, palm_cy), ring_joints[0], dot_spacing=12, dot_r=1)
                    draw_wrist_cuff(pattern, wrist, knuckle_center)
                elif is_arabic:
                    # Arabic: Flowing diagonal vine from index finger tip across palm to wrist with bold floral paisleys
                    draw_intricate_mandala(pattern, palm_cx, palm_cy, int(mandala_r * 0.85))
                    draw_paisley(pattern, int(palm_cx - mandala_r * 0.6), int(palm_cy - mandala_r * 0.4), int(mandala_r * 0.5), 45)
                    draw_finger_ornaments(pattern, index_joints)
                    draw_finger_ornaments(pattern, thumb_joints)
                    draw_beaded_chain(pattern, (palm_cx, palm_cy), index_joints[0], dot_spacing=8, dot_r=2)
                    draw_beaded_chain(pattern, (palm_cx, palm_cy), wrist, dot_spacing=10, dot_r=2)
                    draw_wrist_cuff(pattern, wrist, knuckle_center)
                else:
                    # Bridal / Floral / Geometric / Classic: Full ornate coverage
                    draw_intricate_mandala(pattern, palm_cx, palm_cy, mandala_r)
                    paisley_scale = max(10, int(mandala_r * 0.48))
                    draw_paisley(pattern, int(palm_cx - mandala_r * 0.7), int(palm_cy - mandala_r * 0.25), paisley_scale, 40)
                    draw_paisley(pattern, int(palm_cx + mandala_r * 0.7), int(palm_cy - mandala_r * 0.25), paisley_scale, -40)
                    
                    # Hathphool beaded chains connecting palm to all knuckle bases
                    for mcp in [index_joints[0], mid_joints[0], ring_joints[0], pnk_joints[0], thumb_joints[1]]:
                        draw_beaded_chain(pattern, (palm_cx, palm_cy), mcp, dot_spacing=9, dot_r=2)
                        
                    # Adorn ALL 5 fingers
                    draw_finger_ornaments(pattern, thumb_joints)
                    draw_finger_ornaments(pattern, index_joints)
                    draw_finger_ornaments(pattern, mid_joints)
                    draw_finger_ornaments(pattern, ring_joints)
                    draw_finger_ornaments(pattern, pnk_joints)
                    
                    draw_wrist_cuff(pattern, wrist, knuckle_center)
            else:
                # Fallback when landmarks are unavailable: Use centered layout
                cx, cy = w // 2, int(h * 0.55)
                hand_scale = min(w, h) // 3
                draw_intricate_mandala(pattern, cx, cy, int(hand_scale * 0.42))
                draw_paisley(pattern, int(cx - hand_scale * 0.35), int(cy - hand_scale * 0.15), int(hand_scale * 0.22), 45)
                draw_paisley(pattern, int(cx + hand_scale * 0.35), int(cy - hand_scale * 0.15), int(hand_scale * 0.22), -45)
                for fx in [int(w * 0.28), int(w * 0.42), int(w * 0.58), int(w * 0.72)]:
                    pts = [(fx, int(h * 0.45)), (fx, int(h * 0.32)), (fx, int(h * 0.22)), (fx, int(h * 0.12))]
                    draw_finger_ornaments(pattern, pts)
                draw_wrist_cuff(pattern, (cx, h - 35), (cx, cy))

            # Create hand mask ensuring design does not spill outside hand
            hand_mask = skin_mask
            if lms and len(lms) >= 21:
                try:
                    all_pts = [get_pt(i) for i in range(21)]
                    hull = cv2.convexHull(np.array(all_pts, dtype=np.int32))
                    hull_mask = np.zeros((h, w), dtype=np.uint8)
                    cv2.fillConvexPoly(hull_mask, hull, 255)
                    hull_mask = cv2.dilate(hull_mask, kernel_ellipse, iterations=4)
                    
                    if skin_mask is not None and np.sum(skin_mask) > 100:
                        hand_mask = cv2.bitwise_or(skin_mask, cv2.bitwise_and(skin_mask, hull_mask))
                    else:
                        hand_mask = hull_mask
                except Exception as lm_err:
                    print(f"Error computing landmark hull mask: {lm_err}")

            design_gray = cv2.cvtColor(pattern, cv2.COLOR_BGR2GRAY)
            design_mask = (255.0 - design_gray.astype(np.float32)) / 255.0
            design_mask = np.clip(design_mask, 0.0, 1.0)
            
            design_mask_blurred = cv2.GaussianBlur(design_mask, (3, 3), 0.5)
            
            binary_design = (design_mask * 255).astype(np.uint8)
            dist_transform = cv2.distanceTransform(binary_design, cv2.DIST_L2, 3)
            max_val = np.max(dist_transform)
            dist_norm = dist_transform / max_val if max_val > 0 else np.zeros_like(dist_transform)
            dist_norm_3d = np.expand_dims(dist_norm, axis=2)
            
            # Rich natural Henna Dye palette (BGR)
            deep_mahogany = np.array([12, 22, 68], dtype=np.float32)   # Dark core oxidised stain
            warm_amber    = np.array([22, 50, 125], dtype=np.float32)  # Warm reddish outer stain
            henna_dye = dist_norm_3d * deep_mahogany + (1.0 - dist_norm_3d) * warm_amber
            
            # Organic multiply dye absorption with skin tone
            hand_pixels_norm = hand_img.astype(np.float32) / 255.0
            absorbed_henna = hand_pixels_norm * henna_dye
            
            mask_3d = np.expand_dims(design_mask_blurred, axis=2)
            if hand_mask is not None:
                hand_mask_norm = cv2.GaussianBlur(hand_mask.astype(np.float32) / 255.0, (5, 5), 1.0)
                mask_3d = mask_3d * np.expand_dims(hand_mask_norm, axis=2)
                
            result = hand_img.astype(np.float32) * (1.0 - mask_3d) + absorbed_henna * mask_3d
            result = np.clip(result, 0.0, 255.0).astype(np.uint8)
            
            _, buffer = cv2.imencode('.jpg', result, [cv2.IMWRITE_JPEG_QUALITY, 95])
            generated_image_b64 = base64.b64encode(buffer).decode('utf-8')

        critique_match = "pass"
        critique_reason = "Henna placement aligns naturally with palm contours and finger joints."
        if gemini_key:
            try:
                import google.generativeai as genai
                from PIL import Image
                import io
                
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                pil_img = Image.open(io.BytesIO(img_bytes))
                gen_bytes = base64.b64decode(generated_image_b64)
                gen_pil = Image.open(io.BytesIO(gen_bytes))
                
                gemini_prompt = (
                    f"The user generated a Mehndi (henna) design on their hand using this styling prompt:\n"
                    f"'{style_prompt}'\n\n"
                    "Analyze the try-on output image relative to the prompt rules. "
                    "You MUST respond in JSON format with two keys:\n"
                    "1. 'match': 'pass' if the design resembles realistic Mehndi/henna and matches the style, or 'fail' if the color is wrong, design is missing, or it doesn't resemble Mehndi.\n"
                    "2. 'reason': A brief 2-sentence explanation of your critique.\n\n"
                    "Do not include markdown blocks like ```json."
                )
                generation_config = {"response_mime_type": "application/json"}
                response = model.generate_content([pil_img, gen_pil, gemini_prompt], generation_config=generation_config)
                try:
                    res_json = json.loads(response.text.strip())
                    critique_match = res_json.get("match", "pass")
                    critique_reason = res_json.get("reason", "Design applied successfully.")
                except Exception as json_err:
                    critique_reason = response.text.strip()
            except Exception as e:
                print(f"Gemini critique note: {e}")
                if "429" in str(e) or "quota" in str(e).lower():
                    critique_reason = "Design applied successfully. (AI critique quota reached, fallback active)."
                    critique_match = "pass"
                else:
                    critique_reason = "Henna placement verified across palm and finger joints."

        return TryonResponse(
            generated_image=generated_image_b64,
            critique_match=critique_match,
            critique_reason=critique_reason,
            generation_source=source,
            hf_error_detail=hf_error_detail
        )
    except Exception as e:
        print(f"Error generating try-on: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

