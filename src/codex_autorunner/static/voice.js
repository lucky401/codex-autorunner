import { confirmModal, flash, resolvePath } from "./utils.js";

const MIC_ICON = "🎤";
const RETRY_ICON = "↻";

function supportsVoice() {
  return !!(navigator.mediaDevices && window.MediaRecorder);
}

async function fetchVoiceConfig() {
  const res = await fetch(resolvePath("/api/voice/config"));
  if (!res.ok) throw new Error("Voice config unavailable");
  return res.json();
}

function pickMimeType() {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/ogg",
  ];
  for (const mime of candidates) {
    if (MediaRecorder.isTypeSupported(mime)) return mime;
  }
  return null;
}

function formatErrorMessage(err, fallback) {
  if (!err) return fallback;
  if (typeof err === "string") return err;
  if (err.detail) return err.detail;
  if (err.message) return err.message;
  return fallback;
}

export async function initVoiceInput({
  button,
  input,
  statusEl,
  onTranscript,
  onError,
}) {
  if (!button) return null;
  button.type = "button";

  if (!supportsVoice()) {
    disableButton(button, statusEl, "Voice capture not supported");
    return null;
  }

  let config;
  try {
    config = await fetchVoiceConfig();
  } catch (err) {
    disableButton(button, statusEl, "Voice unavailable");
    return null;
  }

  if (!config.enabled) {
    disableButton(button, statusEl, "Voice disabled");
    return null;
  }

  const state = {
    recording: false,
    sending: false,
    pendingBlob: null,
    optInAccepted: !config.warn_on_remote_api,
    chunks: [],
    recorder: null,
    stream: null,
    lastError: "",
  };

  setStatus(statusEl, "Hold to talk");
  resetButton(button);

  const triggerStart = async ({ forceRetry = false } = {}) => {
    if (state.recording || state.sending) {
      return;
    }
    if (state.pendingBlob && !forceRetry) {
      await retryTranscription();
      return;
    }
    state.pendingBlob = null;
    state.lastError = "";
    await startRecording();
  };

  const startHandler = async (event) => {
    event.preventDefault();
    await triggerStart({ forceRetry: Boolean(event.shiftKey) });
  };

  const endHandler = () => {
    if (state.recording) stopRecording();
  };

  button.addEventListener("pointerdown", startHandler);
  button.addEventListener("pointerup", endHandler);
  button.addEventListener("pointerleave", endHandler);
  button.addEventListener("pointercancel", endHandler);
  button.addEventListener("click", (e) => e.preventDefault());

  async function startRecording() {
    if (config.warn_on_remote_api && !state.optInAccepted) {
      const ok = await confirmModal(
        "Voice capture will send audio to the configured provider. Continue?"
      );
      if (!ok) {
        state.lastError = "Voice opt-in required";
        setStatus(statusEl, state.lastError);
        setButtonError(button, state.pendingBlob);
        if (onError) onError(state.lastError);
        return;
      }
      state.optInAccepted = true;
    }

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      state.lastError = "Microphone permission denied";
      setStatus(statusEl, state.lastError);
      setButtonError(button, state.pendingBlob);
      if (onError) onError(state.lastError);
      return;
    }
    state.stream = stream;
    const mimeType = pickMimeType();
    try {
      state.recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    } catch (err) {
      state.lastError = "Microphone unavailable";
      cleanupStream(state);
      setStatus(statusEl, state.lastError);
      setButtonError(button, state.pendingBlob);
      if (onError) onError(state.lastError);
      return;
    }
    state.chunks = [];
    state.recorder.addEventListener("dataavailable", (e) => {
      if (e.data && e.data.size > 0) {
        state.chunks.push(e.data);
      }
    });
    state.recorder.addEventListener("stop", onRecorderStop);
    state.recording = true;
    setStatus(statusEl, "Listening… release to transcribe");
    setButtonRecording(button);
    try {
      state.recorder.start(config.chunk_ms || 600);
    } catch (err) {
      state.recording = false;
      state.lastError = "Unable to start recorder";
      setStatus(statusEl, state.lastError);
      setButtonError(button, state.pendingBlob);
      if (onError) onError(state.lastError);
    }
  }

  function stopRecording() {
    if (!state.recorder) return;
    state.recording = false;
    state.sending = true;
    setStatus(statusEl, "Transcribing…");
    setButtonSending(button);
    try {
      state.recorder.stop();
    } catch (err) {
      state.sending = false;
      state.lastError = "Unable to stop recorder";
      setButtonError(button, state.pendingBlob);
      if (onError) onError(state.lastError);
    }
  }

  async function onRecorderStop() {
    const blob = new Blob(state.chunks, {
      type: (state.recorder && state.recorder.mimeType) || "audio/webm",
    });
    cleanupRecorder(state);
    if (!blob.size) {
      state.sending = false;
      state.lastError = "No audio captured";
      setStatus(statusEl, state.lastError);
      setButtonError(button, state.pendingBlob);
      if (onError) onError(state.lastError);
      return;
    }
    await sendForTranscription(blob);
  }

  async function retryTranscription() {
    if (!state.pendingBlob) return;
    setStatus(statusEl, "Retrying…");
    setButtonSending(button);
    await sendForTranscription(state.pendingBlob, { retry: true });
  }

  async function sendForTranscription(blob, { retry = false } = {}) {
    state.sending = true;
    state.pendingBlob = blob;
    try {
      const text = await transcribeBlob(blob, state.optInAccepted);
      state.sending = false;
      state.pendingBlob = null;
      setStatus(statusEl, text ? "Transcript ready" : "No speech detected");
      resetButton(button);
      if (text && onTranscript) onTranscript(text);
      if (!text) flash("No speech detected in recording", "error");
    } catch (err) {
      state.sending = false;
      state.lastError = formatErrorMessage(err, "Voice transcription failed");
      setStatus(statusEl, state.lastError);
      setButtonError(button, state.pendingBlob);
      flash(
        retry
          ? "Voice retry failed; try again."
          : "Voice upload failed, tap to retry or Shift+tap to re-record.",
        "error"
      );
      if (onError) onError(state.lastError);
    } finally {
      cleanupStream(state);
    }
  }

  async function transcribeBlob(blob, optIn) {
    const formData = new FormData();
    formData.append("file", blob, "voice.webm");
    formData.append("opt_in", optIn ? "1" : "0");
    const res = await fetch(resolvePath("/api/voice/transcribe"), {
      method: "POST",
      body: formData,
    });
    let payload = {};
    try {
      payload = await res.json();
    } catch (err) {
      // Ignore JSON errors; will fall back to generic message
    }
    if (!res.ok) {
      const detail =
        payload.detail ||
        payload.error ||
        (typeof payload === "string" ? payload : "") ||
        `Voice failed (${res.status})`;
      throw new Error(detail);
    }
    return payload.text || "";
  }

  return {
    config,
    start: () => triggerStart(),
    stop: () => endHandler(),
    isRecording: () => state.recording,
    hasPending: () => Boolean(state.pendingBlob),
  };
}

function cleanupRecorder(state) {
  if (state.recorder) {
    state.recorder.onstop = null;
    state.recorder.ondataavailable = null;
  }
  state.recorder = null;
}

function cleanupStream(state) {
  if (state.stream) {
    state.stream.getTracks().forEach((track) => track.stop());
  }
  state.stream = null;
}

function setStatus(el, text) {
  if (!el) return;
  el.textContent = text || "";
  el.classList.toggle("hidden", !text);
}

function resetButton(button) {
  button.disabled = false;
  button.classList.remove("voice-recording", "voice-sending", "voice-error", "voice-retry");
  button.textContent = MIC_ICON;
}

function setButtonRecording(button) {
  button.classList.add("voice-recording");
  button.classList.remove("voice-sending", "voice-error");
  button.textContent = MIC_ICON;
}

function setButtonSending(button) {
  button.classList.add("voice-sending");
  button.classList.remove("voice-recording", "voice-error");
  button.textContent = MIC_ICON;
}

function setButtonError(button, hasPending) {
  button.classList.remove("voice-recording", "voice-sending");
  button.classList.add("voice-error");
  if (hasPending) {
    button.classList.add("voice-retry");
    button.textContent = RETRY_ICON;
  } else {
    button.textContent = MIC_ICON;
  }
}

function disableButton(button, statusEl, reason) {
  button.disabled = true;
  button.classList.add("disabled");
  button.textContent = MIC_ICON;
  button.title = reason;
  setStatus(statusEl, reason);
}
