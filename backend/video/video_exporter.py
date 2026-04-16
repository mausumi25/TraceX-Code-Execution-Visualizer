"""
video_exporter.py
Stitches PNG frames into an MP4 video using MoviePy.
Handles both MoviePy 1.x and 2.x APIs transparently.
"""
import os


def _get_image_clip():
    """Return ImageClip and a factory that sets duration (v1 vs v2 API)."""
    try:
        from moviepy.editor import ImageClip, concatenate_videoclips  # v1
        def make_clip(path, duration):
            return ImageClip(path).set_duration(duration)
        return make_clip, concatenate_videoclips
    except ImportError:
        from moviepy import ImageClip, concatenate_videoclips  # v2
        def make_clip(path, duration):
            return ImageClip(path).with_duration(duration)
        return make_clip, concatenate_videoclips


class VideoExporter:
    """
    Parameters
    ----------
    duration_per_frame : float
        Seconds each execution-step frame is shown (default 2.0).
    fps : int
        Output video frame rate (default 24).
    """

    def __init__(self, duration_per_frame: float = 2.0, fps: int = 24):
        self.duration_per_frame = duration_per_frame
        self.fps = fps

    def export(
        self,
        frame_paths: list[str],
        output_path: str,
        duration_per_frame: float | None = None,
    ) -> None:
        if not frame_paths:
            raise ValueError("No frames provided to export.")

        duration = duration_per_frame if duration_per_frame is not None else self.duration_per_frame
        make_clip, concatenate_videoclips = _get_image_clip()

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        clips = [make_clip(p, duration) for p in frame_paths]
        final = concatenate_videoclips(clips, method="compose")

        final.write_videofile(
            output_path,
            fps=self.fps,
            codec="libx264",
            audio=False,
            logger=None,      # silence moviepy progress bars
            preset="fast",
        )

        for clip in clips:
            clip.close()
        final.close()
