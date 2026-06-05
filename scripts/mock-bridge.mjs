// Mock of the ROS2 so_arm_100_web_bridge for local Elda testing.
// Speaks the same WebSocket protocol on ws://localhost:9090:
//   in : joint_command, gripper_command, camera_stream_control, …
//   out: joint_state, camera_frame, sim_status
// The real Isaac/Gazebo sim can't run on macOS — this lets us verify the
// frontend wiring end-to-end. Run:  node scripts/mock-bridge.mjs
import { WebSocketServer } from "ws";
import zlib from "node:zlib";

const PORT = 9090;
const ARM = ["Shoulder_Rotation", "Shoulder_Pitch", "Elbow", "Wrist_Pitch", "Wrist_Roll"];
const ALL = [...ARM, "Gripper"];

// ── tiny dependency-free PNG encoder (RGB) ──
const CRC = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return (buf) => {
    let c = 0xffffffff;
    for (let i = 0; i < buf.length; i++) c = t[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
})();
function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length, 0);
  const tc = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(CRC(tc), 0);
  return Buffer.concat([len, tc, crc]);
}
function makePNG(w, h, rgb) {
  const raw = Buffer.alloc(h * (1 + w * 3));
  for (let y = 0; y < h; y++) {
    raw[y * (1 + w * 3)] = 0; // filter: none
    rgb.copy(raw, y * (1 + w * 3) + 1, y * w * 3, (y + 1) * w * 3);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0);
  ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 2; // colour type RGB
  const sig = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  return Buffer.concat([
    sig,
    chunk("IHDR", ihdr),
    chunk("IDAT", zlib.deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}
const W = 240, H = 180;
function frame(t) {
  const rgb = Buffer.alloc(W * H * 3);
  const bar = t % W;
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const i = (y * W + x) * 3;
      const near = Math.abs(x - bar) < 3;
      rgb[i] = near ? 255 : (x + t) & 255;
      rgb[i + 1] = near ? 255 : (y + t) & 255;
      rgb[i + 2] = near ? 255 : (x + y + t * 2) & 255;
    }
  }
  return makePNG(W, H, rgb).toString("base64");
}

const wss = new WebSocketServer({ port: PORT });
console.log(`[mock-bridge] listening on ws://localhost:${PORT}`);

wss.on("connection", (ws) => {
  console.log("[mock-bridge] client connected");
  const target = Object.fromEntries(ALL.map((n) => [n, 0]));
  const actual = { ...target };
  let t = 0;

  ws.send(JSON.stringify({ type: "sim_status", state: "running" }));

  const jointTimer = setInterval(() => {
    for (const n of ALL) actual[n] += (target[n] - actual[n]) * 0.25;
    ws.send(
      JSON.stringify({
        type: "joint_state",
        timestamp: 0,
        joints: {
          names: ALL,
          positions: ALL.map((n) => actual[n]),
          velocities: ALL.map(() => 0),
          efforts: ALL.map(() => 0),
        },
      }),
    );
  }, 50);

  let camTimer = null;
  const startCamera = () => {
    if (camTimer) return;
    camTimer = setInterval(() => {
      t += 4;
      ws.send(
        JSON.stringify({
          type: "camera_frame",
          timestamp: 0,
          width: W,
          height: H,
          encoding: "png",
          quality: 80,
          data: frame(t),
        }),
      );
    }, 100);
  };
  const stopCamera = () => {
    if (camTimer) clearInterval(camTimer);
    camTimer = null;
  };

  ws.on("message", (raw) => {
    let msg;
    try {
      msg = JSON.parse(raw.toString());
    } catch {
      return;
    }
    switch (msg.type) {
      case "joint_command":
        for (const j of msg.joints ?? []) if (j.name in target) target[j.name] = j.position;
        break;
      case "gripper_command":
        target.Gripper = msg.position;
        break;
      case "camera_stream_control":
        msg.enabled ? startCamera() : stopCamera();
        break;
      default:
        break;
    }
  });

  ws.on("close", () => {
    clearInterval(jointTimer);
    stopCamera();
    console.log("[mock-bridge] client disconnected");
  });
});
