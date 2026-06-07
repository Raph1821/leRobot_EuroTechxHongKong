// Hospitals near Home (TUM Garching, Boltzmannstraße 15) within 20 km.
// Captured once from OpenStreetMap via the Overpass API, then frozen as static
// data so the Emergency page renders instantly and works offline (no live fetch).
// To refresh: re-run the Overpass query for amenity=hospital around:20000.

export type Hospital = {
  id: number;
  name: string;
  lat: number;
  lon: number;
  /** km from Home, precomputed (haversine) */
  distance: number;
};

// Home = TUM Garching (Boltzmannstraße 15, 85748 Garching bei München)
export const HOME = { lat: 48.2656, lon: 11.6699 };

// sorted nearest-first, deduped by name
export const HOSPITALS: Hospital[] = [
  { id: 1598962239, name: "Klinik mednord", lat: 48.2019, lon: 11.58726, distance: 9.36 },
  { id: 1598964034, name: "Belegklinikfür Neurochirurgie, plastisch-ästhetische Chirurgie,Chirurgie und Orthopädie", lat: 48.20184, lon: 11.58725, distance: 9.37 },
  { id: 386791408, name: "Schön Klinik München Schwabing", lat: 48.17178, lon: 11.585, distance: 12.18 },
  { id: 122727555, name: "Klinik des Max-Planck-Instituts für Psychiatrie", lat: 48.17388, lon: 11.57644, distance: 12.33 },
  { id: 30683541, name: "München Klinik Schwabing", lat: 48.17194, lon: 11.57843, distance: 12.43 },
  { id: 1423551888, name: "Paracelsus Klinik München", lat: 48.1553, lon: 11.63126, distance: 12.59 },
  { id: 1428000359, name: "Klinik und Poliklinik für Dermatologie und Allergologie am Biederstein, Technische Universität München", lat: 48.16423, lon: 11.59283, distance: 12.64 },
  { id: 1026169510, name: "München Klinik Bogenhausen", lat: 48.15515, lon: 11.62477, distance: 12.73 },
  { id: 1285286391, name: "Arabella-Klinik", lat: 48.1506, lon: 11.61848, distance: 13.34 },
  { id: 1423551898, name: "Dr. Lubos Kliniken Bogenhausen", lat: 48.14855, lon: 11.61459, distance: 13.65 },
  { id: 291898706, name: "Frauenklinik Dr. Geisenhofer", lat: 48.15151, lon: 11.59605, distance: 13.82 },
  { id: 127460320, name: "HNO-Klinik Bogenhausen Dr. Gaertner", lat: 48.14383, lon: 11.60626, distance: 14.34 },
  { id: 1423630775, name: "Josephinum", lat: 48.14552, lon: 11.58138, distance: 14.88 },
  { id: 23684048, name: "Klinikum rechts der Isar", lat: 48.13786, lon: 11.60154, distance: 15.08 },
  { id: 174549561, name: "TUM Klinikum Deutsches Herzzentrum", lat: 48.15307, lon: 11.54979, distance: 15.36 },
  { id: 474050250, name: "Rotkreuzklinikum München Frauenklinik", lat: 48.16135, lon: 11.53176, distance: 15.46 },
  { id: 1446522229, name: "Augenklinik Herzog Carl Theodor", lat: 48.14857, lon: 11.55035, distance: 15.74 },
  { id: 258124384, name: "Rotkreuzklinikum München", lat: 48.15397, lon: 11.53183, distance: 16.09 },
  { id: 1375946558, name: "Krankenhaus Neuwittelsbach", lat: 48.15697, lon: 11.52545, distance: 16.14 },
  { id: 195738244, name: "Klinikum Freising", lat: 48.40494, lon: 11.74503, distance: 16.46 },
  { id: 332617267, name: "ISAR Klinikum", lat: 48.1347, lon: 11.56502, distance: 16.5 },
  { id: 8887372, name: "Klinikum Dritter Orden", lat: 48.16574, lon: 11.5051, distance: 16.5 },
  { id: 8056138, name: "LMU Klinikum Campus Innenstadt", lat: 48.13153, lon: 11.56073, distance: 16.96 },
  { id: 198989981, name: "Krankenhaus der Barmherzigen Brüder", lat: 48.15654, lon: 11.50949, distance: 16.98 },
  { id: 238738906, name: "Klinikum Landkreis Erding", lat: 48.29471, lon: 11.89624, distance: 17.06 },
  { id: 8056619, name: "München Klinik Thalkirchner Straße", lat: 48.12898, lon: 11.56426, distance: 17.09 },
  { id: 1201919908, name: "Artemed Fachklinik München", lat: 48.13032, lon: 11.55483, distance: 17.29 },
  { id: 204282271, name: "kbo-Isar-Amper-Klinikum München-Ost", lat: 48.11725, lon: 11.74914, distance: 17.51 },
  { id: 5110996243, name: "Maria-Theresia-Klinik", lat: 48.12667, lon: 11.54934, distance: 17.85 },
  { id: 1126993180, name: "Helios Amper-Klinikum Dachau", lat: 48.26537, lon: 11.42837, distance: 17.88 },
  { id: 29327859, name: "kbo-Heckscher-Klinikum", lat: 48.11368, lon: 11.5828, distance: 18.08 },
  { id: 13723012401, name: "Psychosomatische Tagesklinik Westend", lat: 48.13403, lon: 11.52357, distance: 18.21 },
  { id: 69564042, name: "Helios Klinik München Perlach", lat: 48.1021, lon: 11.62931, distance: 18.43 },
  { id: 9058187, name: "München Klinik Neuperlach", lat: 48.09445, lon: 11.65604, distance: 19.06 },
  { id: 329675311, name: "Schön Klinik München Harlaching", lat: 48.10405, lon: 11.56707, distance: 19.51 },
];
