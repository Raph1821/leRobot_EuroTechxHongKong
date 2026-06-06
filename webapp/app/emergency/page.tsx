"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { Siren, MapPin, Phone, TriangleAlert } from "lucide-react";
import type { Hospital } from "@/components/EmergencyMap";

// Leaflet touches `window` → client-only
const EmergencyMap = dynamic(() => import("@/components/EmergencyMap"), {
  ssr: false,
  loading: () => (
    <div className="grid h-full place-items-center bg-paper-2/40 text-sm text-ink-soft">
      Loading map…
    </div>
  ),
});

// CDTM venue, Marsstraße 20, Munich
const HOME = { lat: 48.1488, lon: 11.5556 };

function haversine(a: { lat: number; lon: number }, b: { lat: number; lon: number }) {
  const R = 6371;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLon = ((b.lon - a.lon) * Math.PI) / 180;
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((a.lat * Math.PI) / 180) *
      Math.cos((b.lat * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s));
}

export default function EmergencyPage() {
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");

  useEffect(() => {
    const query = `[out:json][timeout:25];
(node["amenity"="hospital"](around:7000,${HOME.lat},${HOME.lon});
 way["amenity"="hospital"](around:7000,${HOME.lat},${HOME.lon});
);
out center 40;`;
    fetch("https://overpass-api.de/api/interpreter", {
      method: "POST",
      body: query,
    })
      .then((r) => r.json())
      .then((data) => {
        const list: Hospital[] = (data.elements ?? [])
          .map((el: { id: number; lat?: number; lon?: number; center?: { lat: number; lon: number }; tags?: { name?: string } }) => {
            const lat = el.lat ?? el.center?.lat;
            const lon = el.lon ?? el.center?.lon;
            if (lat == null || lon == null) return null;
            return {
              id: el.id,
              name: el.tags?.name ?? "Hospital",
              lat,
              lon,
              distance: haversine(HOME, { lat, lon }),
            };
          })
          .filter((h: Hospital | null): h is Hospital => h !== null)
          // dedupe by name, keep closest
          .sort((a: Hospital, b: Hospital) => a.distance - b.distance);
        const seen = new Set<string>();
        const deduped = list.filter((h: Hospital) => {
          if (seen.has(h.name)) return false;
          seen.add(h.name);
          return true;
        });
        setHospitals(deduped);
        setStatus("ok");
      })
      .catch(() => setStatus("error"));
  }, []);

  const nearest = hospitals[0] ?? null;
  const nearestId = useMemo(() => nearest?.id ?? null, [nearest]);

  return (
    <div className="grid h-full grid-cols-1 lg:grid-cols-[1fr_360px]">
      {/* map */}
      <div className="relative min-h-[45vh] lg:min-h-0">
        <EmergencyMap home={HOME} hospitals={hospitals} nearestId={nearestId} />
      </div>

      {/* side panel */}
      <aside className="flex min-h-0 flex-col border-t border-hairline bg-paper-2/40 lg:border-l lg:border-t-0">
        <div className="border-b border-hairline p-5">
          <div className="flex items-center gap-2 text-coral">
            <Siren size={18} />
            <h2 className="font-display text-sm font-semibold uppercase tracking-[0.18em]">
              Emergency
            </h2>
          </div>
          <button className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-coral px-4 py-3 text-sm font-semibold text-paper transition-transform hover:-translate-y-0.5">
            <TriangleAlert size={16} /> Trigger emergency flow
          </button>
          <p className="mt-2 text-[11px] text-ink-soft">
            Notifies relatives + the nearest hospital with a scene photo.
          </p>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          <div className="mb-3 flex items-center justify-between text-xs uppercase tracking-[0.15em] text-ink-soft">
            <span>Nearest hospitals · Munich</span>
            {status === "loading" && <span>loading…</span>}
            {status === "error" && <span className="text-coral">offline</span>}
          </div>

          {nearest && (
            <div className="mb-4 rounded-xl border border-gold/40 bg-gold/10 p-4">
              <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-gold">
                <MapPin size={12} /> Nearest
              </div>
              <div className="mt-1 font-display text-base font-bold">{nearest.name}</div>
              <div className="text-sm text-ink-soft">{nearest.distance.toFixed(1)} km away</div>
              <a
                href="tel:112"
                className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-ink px-3 py-1.5 text-xs font-medium text-paper"
              >
                <Phone size={13} /> Call 112
              </a>
            </div>
          )}

          <ul className="space-y-2">
            {hospitals.slice(1, 12).map((h) => (
              <li
                key={h.id}
                className="flex items-center justify-between rounded-lg border border-hairline bg-paper px-3 py-2.5 text-sm"
              >
                <span className="min-w-0 truncate pr-2">{h.name}</span>
                <span className="flex-none text-xs text-ink-soft">
                  {h.distance.toFixed(1)} km
                </span>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}
