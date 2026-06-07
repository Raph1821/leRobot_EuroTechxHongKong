"use client";

import { useEffect } from "react";
import { Circle, Square, Trash2, Play, List, RefreshCw } from "lucide-react";
import { useJoints } from "@/lib/jointStore";

export default function EpisodeRecorder() {
  const {
    status,
    recordingStatus,
    startRecording,
    stopRecording,
    discardRecording,
    episodes,
    replayEpisode,
    stopReplay,
    listEpisodes,
  } = useJoints();

  // Load episodes on mount
  useEffect(() => {
    if (status === "online") {
      listEpisodes();
    }
  }, [status, listEpisodes]);

  const isRecording = recordingStatus === "recording";
  const isReplaying = recordingStatus === "replaying";
  const isIdle = recordingStatus === "idle";

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Circle className="h-4 w-4 text-ink-soft" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-ink">
            Episode Recorder
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`rounded px-2 py-1 text-[10px] font-semibold uppercase tracking-wider ${
              recordingStatus === "recording"
                ? "bg-red-500/10 text-red-600"
                : recordingStatus === "replaying"
                  ? "bg-emerald-500/10 text-emerald-600"
                  : "bg-paper-2/40 text-ink-soft"
            }`}
          >
            {recordingStatus}
          </span>
        </div>
      </div>

      {/* Recording Controls */}
      <div className="rounded-lg border border-hairline bg-paper-2/40 p-4">
        <h4 className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-soft">
          Recording Controls
        </h4>

        <div className="flex flex-col gap-2">
          {isIdle && (
            <button
              onClick={startRecording}
              disabled={status !== "online"}
              className="flex items-center justify-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 py-3 font-display text-sm font-semibold uppercase tracking-wider text-red-600 transition-colors hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Circle className="h-4 w-4 fill-current" />
              Start Recording
            </button>
          )}

          {isRecording && (
            <>
              <button
                onClick={stopRecording}
                className="flex items-center justify-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 py-3 font-display text-sm font-semibold uppercase tracking-wider text-emerald-600 transition-colors hover:bg-emerald-500/20"
              >
                <Square className="h-4 w-4" />
                Save Recording
              </button>
              <button
                onClick={discardRecording}
                className="flex items-center justify-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 py-3 font-display text-sm font-semibold uppercase tracking-wider text-amber-600 transition-colors hover:bg-amber-500/20"
              >
                <Trash2 className="h-4 w-4" />
                Discard
              </button>
            </>
          )}

          {isReplaying && (
            <button
              onClick={stopReplay}
              className="flex items-center justify-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 py-3 font-display text-sm font-semibold uppercase tracking-wider text-red-600 transition-colors hover:bg-red-500/20"
            >
              <Square className="h-4 w-4" />
              Stop Replay
            </button>
          )}
        </div>
      </div>

      {/* Episode List */}
      <div className="rounded-lg border border-hairline bg-paper-2/40 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-ink-soft">
            Saved Episodes
          </h4>
          <button
            onClick={listEpisodes}
            disabled={status !== "online"}
            className="rounded p-1 text-ink-soft transition-colors hover:bg-ink/5 hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="flex flex-col gap-2">
          {episodes.length === 0 ? (
            <div className="rounded border border-dashed border-hairline p-4 text-center">
              <List className="mx-auto mb-2 h-6 w-6 text-ink-soft/40" />
              <p className="text-xs text-ink-soft">No episodes recorded yet</p>
            </div>
          ) : (
            episodes.map((episode) => (
              <div
                key={episode}
                className="flex items-center justify-between rounded border border-hairline bg-paper p-3"
              >
                <div className="flex-1">
                  <div className="font-mono text-xs font-medium text-ink">
                    {episode}
                  </div>
                </div>
                <button
                  onClick={() => replayEpisode(episode)}
                  disabled={status !== "online" || !isIdle}
                  className="flex items-center gap-1.5 rounded border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-emerald-600 transition-colors hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Play className="h-3 w-3" />
                  Replay
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Info */}
      <div className="rounded border border-hairline bg-paper-2/40 p-3 text-xs leading-relaxed text-ink-soft">
        <strong>Episode Recording:</strong> Record robot movements to create
        training datasets. Episodes are saved as rosbag2 MCAP files and can be
        replayed or used for imitation learning.
      </div>

      {/* Instructions */}
      <div className="rounded border border-amber-500/30 bg-amber-500/10 p-3">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-amber-700">
          How to Use:
        </div>
        <ol className="list-inside list-decimal space-y-1 text-xs leading-relaxed text-amber-700">
          <li>Click "Start Recording" to begin capturing</li>
          <li>Control the robot using keyboard or manual controls</li>
          <li>Click "Save Recording" when finished</li>
          <li>Replay episodes to verify or use for training</li>
        </ol>
      </div>
    </div>
  );
}
