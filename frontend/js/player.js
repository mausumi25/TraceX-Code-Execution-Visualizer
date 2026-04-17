/**
 * player.js  —  Video player utilities
 * Keeps the step-badge in sync with video playback and highlights
 * the corresponding row in the steps table as the video plays.
 */
'use strict';

const TracePlayer = (() => {
  let _steps      = [];
  let _video      = null;
  let _badge      = null;
  let _tbody      = null;
  let _totalSteps = 0;
  let _durationPerStep = 2; // seconds per step (must match VideoExporter)

  // ── Initialise ────────────────────────────────────────────────────────────
  function init(videoEl, badgeEl, tbodyEl, steps, durationPerStep = 2) {
    _video          = videoEl;
    _badge          = badgeEl;
    _tbody          = tbodyEl;
    _steps          = steps     || [];
    _totalSteps     = _steps.length;
    _durationPerStep = durationPerStep;

    // Remove any old listener then add fresh
    _video.removeEventListener('timeupdate', _onTimeUpdate);
    _video.addEventListener('timeupdate', _onTimeUpdate);
    _video.addEventListener('ended', _onEnded);
  }

  // ── Internal: sync badge + table row ─────────────────────────────────────
  function _onTimeUpdate() {
    if (!_video || _totalSteps === 0) return;

    const elapsed  = _video.currentTime;
    const stepIdx  = Math.min(
      Math.floor(elapsed / _durationPerStep),
      _totalSteps - 1
    );

    // Update badge
    if (_badge) {
      _badge.textContent = `Step ${stepIdx + 1} / ${_totalSteps}`;
    }

    // Highlight active row in table
    if (_tbody) {
      const rows = _tbody.querySelectorAll('tr');
      rows.forEach((row, i) => {
        row.classList.toggle('row-active', i === stepIdx);
      });

      // Scroll active row into view (once per step)
      const activeRow = _tbody.querySelector('tr.row-active');
      if (activeRow) {
        activeRow.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
    }
  }

  function _onEnded() {
    if (_badge) _badge.textContent = `Done  ✓`;
  }

  // ── Public helpers ────────────────────────────────────────────────────────
  function loadVideo(url) {
    if (!_video) return;
    _video.src  = url;
    _video.load();
  }

  function scrollToStep(n) {
    if (!_tbody) return;
    const row = _tbody.querySelector(`tr[data-step="${n}"]`);
    if (row) row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  return { init, loadVideo, scrollToStep };
})();

window.TracePlayer = TracePlayer;
