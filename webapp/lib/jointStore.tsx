"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
} from "react";
import {
  HOME_POSE,
  JOINTS,
  URDF_TO_BRIDGE,
  BRIDGE_TO_URDF,
  type JointValues,
} from "./joints";

const WS_URL =
  process.env.NEXT_PUBLIC_BRIDGE_URL || "ws://localhost:9090";

export type BridgeStatus = "connecting" | "online" | "offline";
export type CameraFrame = {
  data: string;
  width: number;
  height: number;
  encoding: string;
} | null;

export type Vector3 = { x: number; y: number; z: number };
export type Quaternion = { x: number; y: number; z: number; w: number };

export type TrajectoryStatus = "idle" | "executing" | "succeeded" | "aborted";
export type RecordingStatus = "idle" | "recording" | "replaying";

type RobotCtx = {
  /** commanded values — what the sliders show / send */
  values: JointValues;
  /** what the 3D should render: live feedback when online, else commanded */
  armValues: JointValues;
  setJoint: (name: string, value: number) => void;
  home: () => void;
  /** live WebSocket link to the ROS2 web_bridge */
  status: BridgeStatus;
  cameraFrame: CameraFrame;
  setCameraEnabled: (enabled: boolean) => void;
  /** teleoperation control */
  teleopEnabled: boolean;
  setTeleopMode: (enabled: boolean, velocityScale?: number) => void;
  sendTeleopVelocity: (linear: [number, number, number], angular: [number, number, number]) => void;
  /** trajectory control */
  trajectoryStatus: TrajectoryStatus;
  sendTrajectoryGoal: (waypoints: JointValues[], durations: number[]) => void;
  /** cartesian control */
  sendCartesianGoal: (position: Vector3, orientation?: Quaternion, duration?: number) => void;
  /** episode recording */
  recordingStatus: RecordingStatus;
  startRecording: () => void;
  stopRecording: () => void;
  discardRecording: () => void;
  episodes: string[];
  replayEpisode: (episodeName: string) => void;
  stopReplay: () => void;
  listEpisodes: () => void;
};

const Ctx = createContext<RobotCtx | null>(null);

// Holds joint state AND the bridge connection. Lives in the app shell so it
// persists across routes; both Manual Control and the Overview read from it.
// When no bridge is running, Elda still works fully locally (commands no-op).
export function JointProvider({ children }: { children: React.ReactNode }) {
  const [values, setValues] = useState<JointValues>({ ...HOME_POSE }); // commanded
  const [actual, setActual] = useState<JointValues>({ ...HOME_POSE }); // feedback
  const [status, setStatus] = useState<BridgeStatus>("offline");
  const [cameraFrame, setCameraFrame] = useState<CameraFrame>(null);
  const [teleopEnabled, setTeleopEnabled] = useState(false);
  const [trajectoryStatus, setTrajectoryStatus] = useState<TrajectoryStatus>("idle");
  const [recordingStatus, setRecordingStatus] = useState<RecordingStatus>("idle");
  const [episodes, setEpisodes] = useState<string[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  // stream on by default so the Overview preview always has a frame
  const cameraWanted = useRef(true);

  const send = useCallback((obj: unknown) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
  }, []);

  // connect + auto-reconnect
  useEffect(() => {
    let closed = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const scheduleReconnect = () => {
      if (closed) return;
      if (timer) clearTimeout(timer);
      timer = setTimeout(connect, 2000);
    };

    const handle = (raw: string) => {
      let msg: any;
      try {
        msg = JSON.parse(raw);
      } catch {
        return;
      }
      
      switch (msg.type) {
        case "joint_state":
          if (msg.joints?.names) {
            const { names, positions } = msg.joints;
            setActual((prev) => {
              const next = { ...prev };
              names.forEach((bn: string, i: number) => {
                const un = BRIDGE_TO_URDF[bn];
                if (un != null) next[un] = positions[i];
              });
              return next;
            });
          }
          break;
          
        case "camera_frame":
          if (msg.data) {
            setCameraFrame({
              data: msg.data,
              width: msg.width ?? 0,
              height: msg.height ?? 0,
              encoding: msg.encoding ?? "jpeg",
            });
          }
          break;
          
        case "trajectory_status":
          setTrajectoryStatus(msg.status as TrajectoryStatus);
          break;
          
        case "recording_status":
          setRecordingStatus(msg.status as RecordingStatus);
          break;
          
        case "episode_list":
          setEpisodes(msg.episodes || []);
          break;
          
        case "error":
          console.error("WebSocket error:", msg.message, msg.code);
          break;
      }
    };

    function connect() {
      if (closed) return;
      setStatus("connecting");
      let ws: WebSocket;
      try {
        ws = new WebSocket(WS_URL);
      } catch {
        scheduleReconnect();
        return;
      }
      wsRef.current = ws;
      ws.onopen = () => {
        setStatus("online");
        if (cameraWanted.current) send({ type: "camera_stream_control", enabled: true });
      };
      ws.onclose = () => {
        setStatus("offline");
        wsRef.current = null;
        scheduleReconnect();
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (ev) => handle(String(ev.data));
    }

    connect();
    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
      wsRef.current?.close();
    };
  }, [send]);

  const setJoint = useCallback(
    (name: string, value: number) => {
      setValues((prev) => ({ ...prev, [name]: value }));
      if (name === "gripper") {
        send({ type: "gripper_command", position: value });
      } else {
        const bridge = URDF_TO_BRIDGE[name];
        if (bridge) send({ type: "joint_command", joints: [{ name: bridge, position: value }] });
      }
    },
    [send],
  );

  const home = useCallback(() => {
    setValues({ ...HOME_POSE });
    const arm = JOINTS.filter((j) => j.name !== "gripper").map((j) => ({
      name: j.bridge,
      position: 0,
    }));
    send({ type: "joint_command", joints: arm });
    send({ type: "gripper_command", position: 0 });
  }, [send]);

  const setCameraEnabled = useCallback(
    (enabled: boolean) => {
      cameraWanted.current = enabled;
      send({ type: "camera_stream_control", enabled });
      if (!enabled) setCameraFrame(null);
    },
    [send],
  );

  const setTeleopMode = useCallback((enabled: boolean, velocityScale = 0.05) => {
    send({ type: "teleop_mode", enabled, velocity_scale: velocityScale });
    setTeleopEnabled(enabled);
    // Send zero velocity when disabling
    if (!enabled) {
      send({ type: "teleop_velocity", linear: [0, 0, 0], angular: [0, 0, 0] });
    }
  }, [send]);

  const sendTeleopVelocity = useCallback((
    linear: [number, number, number], 
    angular: [number, number, number]
  ) => {
    send({ type: "teleop_velocity", linear, angular });
  }, [send]);

  const sendTrajectoryGoal = useCallback((waypoints: JointValues[], durations: number[]) => {
    const trajectory = waypoints.map((wp, i) => ({
      positions: JOINTS.filter(j => j.name !== "gripper").map(j => wp[j.name] || 0),
      duration_sec: durations[i] || 1.0,
    }));
    send({ type: "trajectory_goal", waypoints: trajectory });
  }, [send]);

  const sendCartesianGoal = useCallback((
    position: Vector3, 
    orientation?: Quaternion, 
    duration = 2.0
  ) => {
    send({
      type: "cartesian_goal",
      position,
      orientation: orientation || { x: 0, y: 0, z: 0, w: 1 },
      duration_sec: duration,
    });
  }, [send]);

  const startRecording = useCallback(() => {
    send({ type: "episode_control", command: "start_recording" });
  }, [send]);

  const stopRecording = useCallback(() => {
    send({ type: "episode_control", command: "stop_recording" });
  }, [send]);

  const discardRecording = useCallback(() => {
    send({ type: "episode_control", command: "discard_recording" });
  }, [send]);

  const listEpisodes = useCallback(() => {
    send({ type: "episode_control", command: "list_episodes" });
  }, [send]);

  const replayEpisode = useCallback((episodeName: string) => {
    send({ type: "episode_control", command: "replay_episode", episode_name: episodeName });
  }, [send]);

  const stopReplay = useCallback(() => {
    send({ type: "episode_control", command: "stop_replay" });
  }, [send]);

  // 3D follows live feedback when the bridge is up, else the commanded values
  const armValues = status === "online" ? actual : values;

  return (
    <Ctx.Provider
      value={{ 
        values, 
        armValues, 
        setJoint, 
        home, 
        status, 
        cameraFrame, 
        setCameraEnabled,
        teleopEnabled,
        setTeleopMode,
        sendTeleopVelocity,
        trajectoryStatus,
        sendTrajectoryGoal,
        sendCartesianGoal,
        recordingStatus,
        startRecording,
        stopRecording,
        discardRecording,
        episodes,
        replayEpisode,
        stopReplay,
        listEpisodes,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useJoints(): RobotCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useJoints must be used within JointProvider");
  return c;
}
