"""Privacy processor: strips EXIF and marks unverified redaction when detectors are absent."""
import hashlib
import io
import re
from fastapi import APIRouter, HTTPException
from PIL import Image, ImageFilter
from worker.store import get_store

router = APIRouter()

@router.post("/process")
async def process_privacy(ticket_id: str):
    store = get_store(); source = store.root / "originals" / f"{ticket_id}/complaint.jpg"
    if not source.exists():
        raise HTTPException(status_code=404, detail="original evidence not found")
    original = source.read_bytes(); verified = True; faces = plates = 0
    try:
        image = Image.open(io.BytesIO(original)).convert("RGB")
        import easyocr
        import mediapipe as mp
        import numpy as np
        pixels = np.array(image)
        detector = mp.solutions.face_detection.FaceDetection(model_selection=0, min_detection_confidence=0.5)
        detections = detector.process(pixels).detections or []
        for detection in detections:
            box = detection.location_data.relative_bounding_box; height, width = pixels.shape[:2]
            x, y = max(0, int(box.xmin * width)), max(0, int(box.ymin * height)); w, h = int(box.width * width), int(box.height * height)
            crop = Image.fromarray(pixels[y:y+h, x:x+w]); block = max(12, w // 12)
            pixels[y:y+h, x:x+w] = np.array(crop.resize((max(1, w // block), max(1, h // block))).resize((w, h)))
            faces += 1
        reader = easyocr.Reader(["en"], gpu=False)
        for box, text, _confidence in reader.readtext(pixels):
            if re.fullmatch(r"[A-Z]{2,3}[ -]?\d{1,2}[A-Z]{0,3}[ -]?\d{4}", text.upper().replace(" ", "")):
                xs, ys = [point[0] for point in box], [point[1] for point in box]
                x1, y1, x2, y2 = map(int, (min(xs), min(ys), max(xs), max(ys)))
                pixels[y1:y2, x1:x2] = np.array(Image.fromarray(pixels[y1:y2, x1:x2]).filter(ImageFilter.GaussianBlur(radius=12)))
                plates += 1
        image = Image.fromarray(pixels)
    except Exception:
        verified = False
        # ponytail: offline dependencies are optional; install detector packages for verified redaction.
    out = io.BytesIO(); image.save(out, format="JPEG")
    blurred = out.getvalue(); result = store.put_blurred(f"{ticket_id}/complaint.jpg", blurred)
    detail = {"ticket_id": ticket_id, "faces": faces, "plates": plates, "blur_unverified": not verified, "blurred_sha256": result["sha256"]}
    store.data["evidence"].append({"ticket_id": ticket_id, "kind": "photo_blurred", "sha256": result["sha256"], "meta": {"blur_unverified": not verified}})
    store.audit("privacy_blur" if verified else "blur_unverified", detail)
    return {"success": verified, "ticket_id": ticket_id, "blur_verified": verified, "original_sha256": hashlib.sha256(original).hexdigest(), "blurred_sha256": result["sha256"]}
