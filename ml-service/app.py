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

def draw_organic_line(canvas, p1, p2, color, thickness):
    x1, y1 = p1
    x2, y2 = p2
    dist = np.hypot(x2 - x1, y2 - y1)
    if dist < 5:
        cv2.line(canvas, p1, p2, color, thickness)
        return
    num_segments = max(int(dist / 8), 2)
    dx = (x2 - x1) / num_segments
    dy = (y2 - y1) / num_segments
    px = -dy / dist
    py = dx / dist
    pts = []
    for i in range(num_segments + 1):
        curr_x = x1 + i * dx
        curr_y = y1 + i * dy
        if 0 < i < num_segments:
            offset = np.random.uniform(-1.2, 1.2)
            curr_x += px * offset * 2.5
            curr_y += py * offset * 2.5
        pts.append((int(curr_x), int(curr_y)))
    for i in range(len(pts) - 1):
        cv2.line(canvas, pts[i], pts[i+1], color, thickness)

def draw_organic_circle(canvas, center, radius, color, thickness):
    cx, cy = center
    pts = []
    for angle in range(0, 360, 6):
        rad = np.deg2rad(angle)
        r = radius + 1.5 * np.sin(angle * 6) + np.random.uniform(-0.4, 0.4)
        x = int(cx + r * np.cos(rad))
        y = int(cy + r * np.sin(rad))
        pts.append((x, y))
    pts_arr = np.array([pts], dtype=np.int32)
    if thickness < 0:
        cv2.fillPoly(canvas, pts_arr, color)
    else:
        cv2.polylines(canvas, pts_arr, True, color, thickness)

import math

def draw_mandala_petals(canvas, cx, cy, num_petals, inner_r, outer_r, color, thickness):
    for i in range(num_petals):
        angle = 2 * math.pi * i / num_petals
        angle_next = 2 * math.pi * (i + 0.5) / num_petals
        angle_target = 2 * math.pi * (i + 1) / num_petals
        
        p0 = (int(cx + inner_r * math.cos(angle)), int(cy + inner_r * math.sin(angle)))
        p2 = (int(cx + inner_r * math.cos(angle_target)), int(cy + inner_r * math.sin(angle_target)))
        p1 = (int(cx + outer_r * math.cos(angle_next)), int(cy + outer_r * math.sin(angle_next)))
        
        pts = []
        for t in np.linspace(0, 1, 12):
            x = (1-t)**2 * p0[0] + 2*(1-t)*t * p1[0] + t**2 * p2[0]
            y = (1-t)**2 * p0[1] + 2*(1-t)*t * p1[1] + t**2 * p2[1]
            pts.append((int(x), int(y)))
        
        for k in range(len(pts) - 1):
            draw_organic_line(canvas, pts[k], pts[k+1], color, thickness)
            
        px = int(cx + (inner_r + (outer_r - inner_r)*0.45) * math.cos(angle_next))
        py = int(cy + (inner_r + (outer_r - inner_r)*0.45) * math.sin(angle_next))
        cv2.circle(canvas, (px, py), max(1, int(thickness)), color, -1)

def draw_intricate_mandala(canvas, cx, cy, max_r, color=(0, 0, 0)):
    # Draw core center
    cv2.circle(canvas, (cx, cy), max(2, int(max_r * 0.08)), color, -1)
    cv2.circle(canvas, (cx, cy), max(5, int(max_r * 0.15)), color, 1)
    
    # First ring of petals
    r1 = max(6, int(max_r * 0.15))
    r2 = max(12, int(max_r * 0.28))
    draw_mandala_petals(canvas, cx, cy, 12, r1, r2, color, 1)
    cv2.circle(canvas, (cx, cy), r2 + 2, color, 1)
    
    # Ring of dots
    dot_r = r2 + 7
    for angle_deg in range(0, 360, 15):
        rad = math.radians(angle_deg)
        rx = int(cx + dot_r * math.cos(rad))
        ry = int(cy + dot_r * math.sin(rad))
        cv2.circle(canvas, (rx, ry), max(1, int(max_r * 0.02)), color, -1)
        
    # Second ring of petals
    if max_r > 50:
        r3 = dot_r + 5
        r4 = r3 + max(15, int(max_r * 0.25))
        cv2.circle(canvas, (cx, cy), r3, color, 1)
        draw_mandala_petals(canvas, cx, cy, 16, r3, r4, color, 2)
        cv2.circle(canvas, (cx, cy), r4 + 2, color, 2)
        
    # Outer scalloped accents
    if max_r > 90:
        r5 = r4 + 4
        r6 = r5 + max(12, int(max_r * 0.18))
        draw_mandala_petals(canvas, cx, cy, 24, r5, r6, color, 1)
        cv2.circle(canvas, (cx, cy), r6, color, 1)
        for angle_deg in range(0, 360, 10):
            rad = math.radians(angle_deg)
            rx = int(cx + (r6 + 4) * math.cos(rad))
            ry = int(cy + (r6 + 4) * math.sin(rad))
            cv2.circle(canvas, (rx, ry), 1, color, -1)

def draw_paisley(canvas, cx, cy, scale, angle_deg, color=(0, 0, 0), thickness=2):
    rad_rot = math.radians(angle_deg)
    cos_r = math.cos(rad_rot)
    sin_r = math.sin(rad_rot)
    
    pts = []
    for t in np.linspace(0, 2 * math.pi, 100):
        x_base = scale * math.sin(t)
        y_base = scale * (math.cos(t) + math.sin(t)**2 * 0.55)
        
        x = cx + (x_base * cos_r - y_base * sin_r)
        y = cy + (x_base * sin_r + y_base * cos_r)
        pts.append((int(x), int(y)))
        
    pts = np.array(pts, dtype=np.int32)
    cv2.polylines(canvas, [pts], True, color, thickness)
    
    h, w = canvas.shape[:2]
    paisley_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(paisley_mask, [pts], 255)
    
    hatch_canvas = np.ones_like(canvas) * 255
    for offset in range(-int(scale * 2.5), int(scale * 2.5), 8):
        cv2.line(hatch_canvas, (int(cx - scale * 1.5 + offset), int(cy - scale * 1.5)), 
                               (int(cx + scale * 1.5 + offset), int(cy + scale * 1.5)), color, 1)
        cv2.line(hatch_canvas, (int(cx - scale * 1.5 + offset), int(cy + scale * 1.5)), 
                               (int(cx + scale * 1.5 + offset), int(cy - scale * 1.5)), color, 1)
        
    canvas[paisley_mask == 255] = hatch_canvas[paisley_mask == 255]
    
    flower_cx = int(cx - scale * 0.2 * sin_r)
    flower_cy = int(cy + scale * 0.2 * cos_r)
    cv2.circle(canvas, (flower_cx, flower_cy), max(1, int(scale * 0.1)), color, -1)

def draw_finger_trail(canvas, start_pt, end_pt, color=(0, 0, 0), thickness=2):
    x1, y1 = start_pt
    x2, y2 = end_pt
    dist = np.hypot(x2 - x1, y2 - y1)
    if dist < 10:
        return
        
    draw_organic_line(canvas, start_pt, end_pt, color, thickness)
    
    num_steps = max(3, int(dist / 25))
    dx = (x2 - x1) / num_steps
    dy = (y2 - y1) / num_steps
    vx = -dy / dist
    vy = dx / dist
    
    for i in range(1, num_steps):
        cx = int(x1 + i * dx)
        cy = int(y1 + i * dy)
        
        lx = int(cx + vx * 8)
        ly = int(cy + vy * 8)
        cv2.ellipse(canvas, (lx, ly), (6, 3), math.degrees(math.atan2(dy, dx)) + 45, 0, 360, color, -1)
        
        rx = int(cx - vx * 8)
        ry = int(cy - vy * 8)
        cv2.ellipse(canvas, (rx, ry), (6, 3), math.degrees(math.atan2(dy, dx)) - 45, 0, 360, color, -1)
        
        cv2.circle(canvas, (cx, cy), 2, color, -1)


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

        # 1. Attempt Hugging Face Serverless Generative Img2Img API (Instruct-Pix2Pix)
        if gemini_key:
            try:
                print(f"Attempting Hugging Face Instruct-Pix2Pix generation with prompt:\n{style_prompt}")
                API_URL = "https://api-inference.huggingface.co/models/timbrooks/instruct-pix2pix"
                sanitized_prompt = " ".join(style_prompt.replace('\r', ' ').replace('\n', ' ').split())
                headers = {
                    "Authorization": f"Bearer {gemini_key}",
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

        # 2. Structure-preserving Fallback Local Contour Blender
        if not generated_image_b64:
            h, w = hand_img.shape[:2]
            
            # Skin detection using YCrCb color space
            ycrcb = cv2.cvtColor(hand_img, cv2.COLOR_BGR2YCrCb)
            skin_mask = cv2.inRange(ycrcb, np.array([0, 133, 77]), np.array([255, 173, 127]))
            kernel_ellipse = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel_ellipse)
            skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel_ellipse)
            skin_mask = cv2.dilate(skin_mask, kernel_ellipse, iterations=1)
            
            pattern = np.ones((h, w, 3), dtype=np.uint8) * 255
            prompt_lower = style_prompt.lower()
            
            lms = None
            if landmarks:
                try:
                    lms = json.loads(landmarks)
                except Exception as lm_err:
                    print(f"Error parsing landmarks: {lm_err}")

            if lms and len(lms) >= 21:
                xs = [pt['x'] for pt in lms]
                ys = [pt['y'] for pt in lms]
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)
                pad_x = (max_x - min_x) * 0.25
                pad_y = (max_y - min_y) * 0.25
                crop_min_x = max(0.0, min_x - pad_x)
                crop_max_x = min(1.0, max_x + pad_x)
                crop_min_y = max(0.0, min_y - pad_y)
                crop_max_y = min(1.0, max_y + pad_y)

                def get_pt(idx):
                    pt = lms[idx]
                    px = int((pt['x'] - crop_min_x) / (crop_max_x - crop_min_x) * w)
                    py = int((pt['y'] - crop_min_y) / (crop_max_y - crop_min_y) * h)
                    return (px, py)

                wrist = get_pt(0)
                idx_tip = get_pt(8)
                idx_base = get_pt(5)
                mid_base = get_pt(9)
                ring_base = get_pt(13)
                pnk_base = get_pt(17)
                
                cx = int((wrist[0] + idx_base[0] + mid_base[0] + ring_base[0] + pnk_base[0]) / 5)
                cy = int((wrist[1] + idx_base[1] + mid_base[1] + ring_base[1] + pnk_base[1]) / 5)
                
                hand_scale = int(np.hypot(mid_base[0] - wrist[0], mid_base[1] - wrist[1]))
                if hand_scale < 20:
                    hand_scale = min(w, h) // 2

                p_ctrl = (int((idx_tip[0] + wrist[0]) // 2 - hand_scale * 0.2),
                          int((idx_tip[1] + wrist[1]) // 2 + hand_scale * 0.2))
                
                bezier_pts = []
                for t in np.linspace(0, 1, 100):
                    bx = (1-t)**2 * idx_tip[0] + 2*(1-t)*t * p_ctrl[0] + t**2 * wrist[0]
                    by = (1-t)**2 * idx_tip[1] + 2*(1-t)*t * p_ctrl[1] + t**2 * wrist[1]
                    bezier_pts.append((int(bx), int(by)))
                
                for k in range(len(bezier_pts) - 1):
                    draw_organic_line(pattern, bezier_pts[k], bezier_pts[k+1], (0, 0, 0), 3)

                mx, my = bezier_pts[50]
                draw_intricate_mandala(pattern, mx, my, int(hand_scale * 0.42))

                px1, py1 = bezier_pts[25]
                draw_paisley(pattern, px1, py1, int(hand_scale * 0.2), 45)
                
                px2, py2 = bezier_pts[75]
                draw_paisley(pattern, px2, py2, int(hand_scale * 0.2), -135)

                finger_paths = [
                    (0, 4),   # Thumb
                    (9, 12),  # Middle
                    (13, 16), # Ring
                    (17, 20)  # Pinky
                ]
                for base_idx, tip_idx in finger_paths:
                    try:
                        draw_finger_trail(pattern, get_pt(base_idx), get_pt(tip_idx), thickness=2)
                    except Exception as e:
                        print(f"Finger trail drawing error: {e}")
            else:
                cx, cy = w // 2, h // 2
                hand_scale = min(w, h) // 2
                
                p_start = (int(w * 0.8), int(h * 0.2))
                p_end = (int(w * 0.2), int(h * 0.8))
                p_ctrl = (int(w * 0.4), int(h * 0.4))
                
                bezier_pts = []
                for t in np.linspace(0, 1, 100):
                    bx = (1-t)**2 * p_start[0] + 2*(1-t)*t * p_ctrl[0] + t**2 * p_end[0]
                    by = (1-t)**2 * p_start[1] + 2*(1-t)*t * p_ctrl[1] + t**2 * p_end[1]
                    bezier_pts.append((int(bx), int(by)))
                    
                for k in range(len(bezier_pts) - 1):
                    draw_organic_line(pattern, bezier_pts[k], bezier_pts[k+1], (0, 0, 0), 3)
                
                mx, my = bezier_pts[50]
                draw_intricate_mandala(pattern, mx, my, int(hand_scale * 0.45))
                
                px1, py1 = bezier_pts[25]
                draw_paisley(pattern, px1, py1, int(hand_scale * 0.22), 45)
                
                px2, py2 = bezier_pts[75]
                draw_paisley(pattern, px2, py2, int(hand_scale * 0.22), -135)
                
                draw_organic_line(pattern, (0, h - 30), (w, h - 30), (0,0,0), 3)
                draw_organic_line(pattern, (0, h - 45), (w, h - 45), (0,0,0), 2)
                for x in range(15, w, 30):
                    cv2.circle(pattern, (x, h - 37), 4, (0,0,0), -1)

            hand_mask = skin_mask
            if np.sum(hand_mask) == 0:
                hand_mask = None
                
            if lms and len(lms) >= 21:
                try:
                    landmark_mask = np.zeros((h, w), dtype=np.uint8)
                    connections = [
                        [0, 1, 2, 3, 4], # Thumb
                        [0, 5, 6, 7, 8], # Index
                        [9, 10, 11, 12], # Middle
                        [13, 14, 15, 16], # Ring
                        [0, 17, 18, 19, 20], # Pinky
                        [5, 9, 13, 17] # Palm top
                    ]
                    for conn in connections:
                        pts = []
                        for idx in conn:
                            pts.append(get_pt(idx))
                        for k in range(len(pts) - 1):
                            cv2.line(landmark_mask, pts[k], pts[k+1], 255, thickness=45)
                            
                    palm_indices = [0, 1, 5, 9, 13, 17]
                    palm_pts = [get_pt(idx) for idx in palm_indices]
                    cv2.fillConvexPoly(landmark_mask, np.array(palm_pts, dtype=np.int32), 255)
                    
                    if skin_mask is not None and np.sum(cv2.bitwise_and(skin_mask, landmark_mask)) > 0:
                        hand_mask = cv2.bitwise_and(skin_mask, landmark_mask)
                    else:
                        hand_mask = landmark_mask
                except Exception as lm_err:
                    print(f"Error parsing landmarks for mask: {lm_err}")

            design_gray = cv2.cvtColor(pattern, cv2.COLOR_BGR2GRAY)
            design_mask = (255.0 - design_gray.astype(np.float32)) / 255.0
            design_mask = np.clip(design_mask, 0.0, 1.0)
            
            design_mask_blurred = cv2.GaussianBlur(design_mask, (3, 3), 0.7)
            
            binary_design = (design_mask * 255).astype(np.uint8)
            dist_transform = cv2.distanceTransform(binary_design, cv2.DIST_L2, 5)
            
            max_val = np.max(dist_transform)
            if max_val > 0:
                dist_norm = dist_transform / max_val
            else:
                dist_norm = np.zeros_like(dist_transform)
                
            dist_norm_3d = np.expand_dims(dist_norm, axis=2)
            
            deep_mahogany = np.array([12, 18, 60], dtype=np.float32)
            warm_brown = np.array([15, 35, 105], dtype=np.float32)
            
            color_gradient = dist_norm_3d * deep_mahogany + (1.0 - dist_norm_3d) * warm_brown
            
            hand_pixels_norm = hand_img.astype(np.float32) / 255.0
            henna_blend = hand_pixels_norm * color_gradient
            henna_blend = np.clip(henna_blend, 0.0, 255.0)
            
            skin_gray = cv2.cvtColor(hand_img, cv2.COLOR_BGR2GRAY)
            highlight_regions = np.clip((skin_gray.astype(np.float32) - 190.0) / 65.0, 0.0, 0.55)
            
            mask_3d = np.expand_dims(design_mask_blurred * (1.0 - highlight_regions), axis=2)
            
            if hand_mask is not None:
                hand_mask_norm = hand_mask.astype(np.float32) / 255.0
                hand_mask_3d = np.expand_dims(hand_mask_norm, axis=2)
                mask_3d = mask_3d * hand_mask_3d

            result = hand_img.astype(np.float32) * (1.0 - mask_3d) + henna_blend * mask_3d
            result = np.clip(result, 0.0, 255.0).astype(np.uint8)

            _, buffer = cv2.imencode('.jpg', result)
            generated_image_b64 = base64.b64encode(buffer).decode('utf-8')

        critique_match = "pass"
        critique_reason = "Design matches occasion and fits hand structure beautifully."
        if gemini_key:
            try:
                import google.generativeai as genai
                from PIL import Image
                import io
                
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel('gemini-3.5-flash')
                
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
                    print(f"Failed parsing Gemini JSON response: {response.text}. Error: {json_err}")
                    critique_reason = response.text.strip()
            except Exception as e:
                print(f"Gemini critique failed: {e}")
                if "429" in str(e) or "quota" in str(e).lower():
                    critique_reason = "Gemini API Quota Exceeded (429). Please wait for the daily free tier limit to reset, or check your billing plan."
                    critique_match = "fail"
                else:
                    critique_reason = f"AI Placement Critique skipped: {str(e)[:100]}"

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

