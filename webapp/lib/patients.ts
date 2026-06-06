// Mock patient roster for the nurse/doctor spaces (beta).
// Patient #1 is the live demo patient (CareAI + SO-101 backed); others are mocks.
export type PatientMed = {
  name: string;
  dose: string;
  expiry: string;
  status: "ok" | "soon" | "low";
};

export type Prescription = {
  id: string;
  medicine_name: string;
  dose: string;
  times: string[];
  notes?: string;
  active: boolean;
};

export type PatientEvent = {
  id: string;
  type: "medicine" | "fall" | "voice" | "patrol" | "alert";
  message: string;
  time: string;
  acked?: boolean;
};

export type Patient = {
  id: string;
  name: string;
  age: number;
  address: string;
  status: "live" | "stable" | "attention";
  meds: PatientMed[];
  prescriptions: Prescription[];
  events: PatientEvent[];
  notes: string[];
};

export const PATIENTS: Patient[] = [
  {
    id: "mei-ling-chan",
    name: "Mei-Ling Chan",
    age: 84,
    address: "Schwabing, München",
    status: "live",
    meds: [
      { name: "Aspirin", dose: "100mg", expiry: "2027-03", status: "ok" },
      { name: "Metformin", dose: "500mg", expiry: "2026-11", status: "ok" },
      { name: "Ibuprofen", dose: "200mg", expiry: "2026-07", status: "low" },
    ],
    prescriptions: [
      {
        id: "rx-1",
        medicine_name: "Aspirin",
        dose: "100mg · 1 pill",
        times: ["14:00"],
        notes: "After lunch",
        active: true,
      },
      {
        id: "rx-2",
        medicine_name: "Metformin",
        dose: "500mg · 1 pill",
        times: ["08:00", "20:00"],
        active: true,
      },
    ],
    events: [
      { id: "e1", type: "medicine", message: "14:00 dose dispensed (Aspirin)", time: "today 14:00" },
      { id: "e2", type: "alert", message: "Ibuprofen low stock (4 left)", time: "today 11:20" },
      { id: "e3", type: "patrol", message: "Patrol completed, no anomalies", time: "today 09:00" },
    ],
    notes: ["Prefers reminders in the morning."],
  },
  {
    id: "wei-zhang",
    name: "Wei Zhang",
    age: 79,
    address: "Sendling, München",
    status: "stable",
    meds: [
      { name: "Ramipril", dose: "5mg", expiry: "2027-01", status: "ok" },
      { name: "Simvastatin", dose: "20mg", expiry: "2026-09", status: "ok" },
    ],
    prescriptions: [
      {
        id: "rx-1",
        medicine_name: "Ramipril",
        dose: "5mg · 1 pill",
        times: ["08:00"],
        active: true,
      },
    ],
    events: [
      { id: "e1", type: "medicine", message: "08:00 dose dispensed (Ramipril)", time: "today 08:01" },
    ],
    notes: [],
  },
  {
    id: "sakura-tanaka",
    name: "Sakura Tanaka",
    age: 88,
    address: "Pasing, München",
    status: "attention",
    meds: [
      { name: "Warfarin", dose: "3mg", expiry: "2026-08", status: "soon" },
      { name: "Vitamin D", dose: "1000 IU", expiry: "2027-05", status: "ok" },
    ],
    prescriptions: [
      {
        id: "rx-1",
        medicine_name: "Warfarin",
        dose: "3mg · 1 pill",
        times: ["18:00"],
        notes: "Monitor INR weekly",
        active: true,
      },
    ],
    events: [
      { id: "e1", type: "fall", message: "Fall detected, resolved (false alarm)", time: "yesterday 16:40" },
      { id: "e2", type: "alert", message: "Warfarin expiring soon (2026-08)", time: "yesterday 10:00" },
    ],
    notes: ["Follow-up call scheduled."],
  },
  {
    id: "jin-ho-park",
    name: "Jin-Ho Park",
    age: 81,
    address: "Giesing, München",
    status: "stable",
    meds: [{ name: "Levothyroxin", dose: "75µg", expiry: "2027-02", status: "ok" }],
    prescriptions: [
      {
        id: "rx-1",
        medicine_name: "Levothyroxin",
        dose: "75µg · 1 pill",
        times: ["07:30"],
        notes: "Before breakfast",
        active: true,
      },
    ],
    events: [
      { id: "e1", type: "medicine", message: "07:30 dose dispensed (Levothyroxin)", time: "today 07:31" },
    ],
    notes: [],
  },
];

export const getPatient = (id: string) => PATIENTS.find((p) => p.id === id);
