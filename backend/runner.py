"""
runner.py  —  Trace Flask API entry point
Start with:  python runner.py
Serves the API at /api/* and the frontend at /

Policy
------
* ONLY syntax errors block the pipeline and return an error response.
* Runtime errors / logical errors -> still generate a video showing all
  traced steps up to (and including) the error frame.  The response will
  carry  has_runtime_error=True  and  runtime_error_msg  so the frontend
  can display a warning banner while still playing the video.
"""
import os
import uuid
import sys

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ── Make sure tracer / video packages are importable regardless of CWD ────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from tracer.syntax_checker import SyntaxChecker
from tracer.python_tracer  import PythonTracer
from tracer.js_tracer      import JSTracer
from tracer.c_tracer       import CTracer
from tracer.cpp_tracer     import CppTracer
from video.frame_builder   import FrameBuilder
from video.video_exporter  import VideoExporter

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

VIDEOS_DIR   = os.path.join(BASE_DIR, "static", "videos")
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")
os.makedirs(VIDEOS_DIR, exist_ok=True)

SUPPORTED_LANGUAGES = {
    "python":     "Python 3",
    "javascript": "JavaScript (Node.js)",
    "c":          "C (GCC/GDB)",
    "cpp":        "C++ (G++/GDB)",
}

# ── API routes ────────────────────────────────────────────────────────────────
@app.route("/api/languages", methods=["GET"])
def get_languages():
    return jsonify({"languages": SUPPORTED_LANGUAGES})


@app.route("/api/trace", methods=["POST"])
def trace():
    data     = request.get_json(silent=True) or {}
    code     = (data.get("code") or "").strip()
    language = (data.get("language") or "python").lower()

    if not code:
        return jsonify({"error": "No code provided."}), 400

    if language not in SUPPORTED_LANGUAGES:
        return jsonify({"error": f"Unsupported language: '{language}'."}), 400

    # ── 1. Syntax check ───────────────────────────────────────────────────────
    # ONLY a syntax error stops the pipeline here.  Runtime / logical errors
    # are surfaced inside the video as a clearly labelled error frame.
    checker        = SyntaxChecker()
    syntax_result  = checker.check(code, language)

    if not syntax_result["valid"]:
        return jsonify({
            "syntax_error": True,
            "error":        syntax_result["error"],
            "error_line":   syntax_result.get("line"),
        }), 200   # 200 so the frontend can display the message

    # ── 2. Trace execution ────────────────────────────────────────────────────
    # Runtime errors inside the user's code are captured as steps by the
    # tracer; they do NOT raise exceptions here.  Exceptions here would only
    # be an internal bug in the tracer itself.
    try:
        if language == "python":
            steps = PythonTracer().trace(code)
        elif language == "javascript":
            steps = JSTracer().trace(code)
        elif language == "cpp":
            steps = CppTracer().trace(code)
        else:  # c
            steps = CTracer().trace(code)
    except Exception as exc:
        return jsonify({"error": f"Tracer internal error: {exc}"}), 500

    if not steps:
        # Even if the only captured step is an error step, we continue.
        # A completely empty step list means the tracer itself failed.
        return jsonify({"error": "No execution steps were captured."}), 500

    # Collect any runtime error message to surface in the response.
    # This does NOT stop video generation.
    runtime_error_msg = None
    has_runtime_error = False
    for s in steps:
        if s.get("event") in ("error", "exception") and s.get("error"):
            has_runtime_error = True
            if runtime_error_msg is None:
                runtime_error_msg = s["error"]

    # ── 3. Build frames ───────────────────────────────────────────────────────
    # Pass has_runtime_error so the builder can add a final error summary frame
    code_lines  = code.split("\n")
    builder     = FrameBuilder(code_lines, language)
    frame_paths = builder.build_frames(steps, has_runtime_error=has_runtime_error,
                                       runtime_error_msg=runtime_error_msg)

    if not frame_paths:
        return jsonify({"error": "Frame generation produced no output."}), 500

    # ── 4. Export video ───────────────────────────────────────────────────────
    video_id       = str(uuid.uuid4())[:8]
    video_filename = f"trace_{video_id}.mp4"
    video_path     = os.path.join(VIDEOS_DIR, video_filename)

    try:
        VideoExporter().export(frame_paths, video_path)
    except Exception as exc:
        return jsonify({"error": f"Video export failed: {exc}"}), 500
    finally:
        # Clean up temporary PNG frames
        for fp in frame_paths:
            try:
                os.remove(fp)
            except OSError:
                pass

    return jsonify({
        "video_url":          f"/static/videos/{video_filename}",
        "steps":              steps,
        "total_steps":        len(steps),
        "has_runtime_error":  has_runtime_error,
        "runtime_error_msg":  runtime_error_msg,
        "language":           language,
    })


# ── Video serve ───────────────────────────────────────────────────────────────
@app.route("/static/videos/<path:filename>")
def serve_video(filename):
    return send_from_directory(VIDEOS_DIR, filename)


# ── Frontend serve ────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/css/<path:filename>")
def serve_css(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, "css"), filename)


@app.route("/js/<path:filename>")
def serve_js(filename):
    return send_from_directory(os.path.join(FRONTEND_DIR, "js"), filename)


@app.route("/favicon.ico")
def favicon():
    return "", 204


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n  [trace]  Code Execution Visualizer")
    print("  Running at  ->  http://localhost:5000\n")
    # use_reloader=False prevents sys.settrace conflicts with Flask reloader
    app.run(debug=True, port=5000, use_reloader=False)
