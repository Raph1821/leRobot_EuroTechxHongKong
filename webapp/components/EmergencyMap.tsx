"use client";

import "leaflet/dist/leaflet.css";
import { MapContainer, TileLayer, CircleMarker, Popup, Tooltip } from "react-leaflet";

export type Hospital = {
  id: number;
  name: string;
  lat: number;
  lon: number;
  distance: number; // km from home
};

export default function EmergencyMap({
  home,
  hospitals,
  nearestId,
}: {
  home: { lat: number; lon: number };
  hospitals: Hospital[];
  nearestId: number | null;
}) {
  return (
    <MapContainer
      center={[home.lat, home.lon]}
      zoom={13}
      scrollWheelZoom
      className="h-full w-full"
    >
      <TileLayer
        attribution='&copy; OpenStreetMap'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {/* home / patient */}
      <CircleMarker
        center={[home.lat, home.lon]}
        radius={9}
        pathOptions={{ color: "#0e4fe0", fillColor: "#0e4fe0", fillOpacity: 0.9 }}
      >
        <Tooltip permanent direction="top" offset={[0, -8]}>
          Home
        </Tooltip>
      </CircleMarker>

      {hospitals.map((h) => {
        const isNearest = h.id === nearestId;
        return (
          <CircleMarker
            key={h.id}
            center={[h.lat, h.lon]}
            radius={isNearest ? 10 : 6}
            pathOptions={{
              color: isNearest ? "#d9a441" : "#ff3b53",
              fillColor: isNearest ? "#d9a441" : "#ff3b53",
              fillOpacity: 0.85,
              weight: isNearest ? 3 : 1,
            }}
          >
            <Popup>
              <strong>{h.name}</strong>
              <br />
              {h.distance.toFixed(1)} km{isNearest ? " · nearest" : ""}
            </Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
