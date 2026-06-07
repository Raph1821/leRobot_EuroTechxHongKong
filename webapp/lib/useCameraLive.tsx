"use client";

import { useEffect, useRef, useState } from "react";
import { CAREAI_URL } from "./careApi";

const STREAM_URL = `${CAREAI_URL}/camera/stream`;
const SNAPSHOT_URL = `${CAREAI_URL}/camera/snapshot`;

// How long without a fresh frame before we declare the camera offline.
const STALE_MS = 4000;
// How often to probe the backend for a current frame.
const PROBE_MS = 2500;

/**
 * Liveness for the MJPEG camera stream.
 *
 * The `<img>` MJPEG trick fires `onLoad` only once (and `onError` only on the
 * initial connection), so if the backend dies mid-stream the image just freezes
 * on its last frame and would wrongly stay "online". This hook instead probes
 * `/camera/snapshot` on an interval: each success refreshes a watchdog, and if
 * no fresh frame arrives within STALE_MS we flip back to offline — even if we
 * were online before. When it recovers, `streamKey` bumps so the consumer can
 * force the MJPEG `<img>` to reconnect (a frozen stream won't resume on its own).
 */
export function useCameraLive() {
  const [live, setLive] = useState(false);
  const [streamKey, setStreamKey] = useState(0);
  const liveRef = useRef(false);
  const lastFrameRef = useRef(0);

  useEffect(() => {
    let cancelled = false;

    const goOffline = () => {
      if (!liveRef.current) return;
      liveRef.current = false;
      setLive(false);
    };
    const goOnline = () => {
      lastFrameRef.current = Date.now();
      if (liveRef.current) return;
      liveRef.current = true;
      setLive(true);
      // force the frozen MJPEG <img> to re-open its connection
      setStreamKey((k) => k + 1);
    };

    const probe = async () => {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), PROBE_MS - 200);
      try {
        const res = await fetch(`${SNAPSHOT_URL}?t=${Date.now()}`, {
          signal: ctrl.signal,
          cache: "no-store",
        });
        if (!cancelled && res.ok) goOnline();
        else if (!cancelled) goOffline();
      } catch {
        // network error / timeout / backend down
      } finally {
        clearTimeout(t);
      }
      // watchdog: no fresh frame within STALE_MS ⇒ offline
      if (!cancelled && Date.now() - lastFrameRef.current > STALE_MS) goOffline();
    };

    probe();
    const id = setInterval(probe, PROBE_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return { live, streamKey, STREAM_URL, SNAPSHOT_URL };
}
