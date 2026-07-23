"""
ExamShield Analytics — Synthetic Dataset Generator (v1)
Generates a coherent, end-to-end synthetic dataset modeled on the
ExamShield_Database_Architecture.md schema, with deliberately injected
anomalies at ~5% of exam centers so downstream ML (Isolation Forest, LOF,
DBSCAN, XGBoost) has real ground truth to recover.

Scale: 200 centers, ~20,000 candidates, one exam cycle (single-session,
NEET-style national exam with Physics/Chemistry/Biology sections).
"""

import numpy as np
import pandas as pd
from faker import Faker
import random
import string
import hashlib
import os

SEED = 42
np.random.seed(SEED)
random.seed(SEED)
fake = Faker("en_IN")
Faker.seed(SEED)

OUT_DIR = "/home/claude/data/raw"
os.makedirs(OUT_DIR, exist_ok=True)

N_CANDIDATES = 20000
N_CENTERS = 200
ANOMALOUS_CENTER_FRACTION = 0.05

# ----------------------------------------------------------------------
# 1. GEOGRAPHY
# ----------------------------------------------------------------------
states_data = [
    ("Maharashtra", "MH"), ("Uttar Pradesh", "UP"), ("Bihar", "BR"),
    ("Rajasthan", "RJ"), ("Tamil Nadu", "TN"), ("Karnataka", "KA"),
    ("West Bengal", "WB"), ("Madhya Pradesh", "MP"), ("Gujarat", "GJ"),
    ("Delhi", "DL"),
]
state_df = pd.DataFrame(states_data, columns=["state_name", "state_code"])
state_df.insert(0, "state_id", range(1, len(state_df) + 1))

district_rows, city_rows = [], []
district_id, city_id = 1, 1
for _, srow in state_df.iterrows():
    n_districts = np.random.randint(2, 4)
    for _ in range(n_districts):
        d_name = fake.city_suffix() + " " + fake.city()
        district_rows.append((district_id, srow.state_id, d_name[:100]))
        n_cities = np.random.randint(1, 3)
        for _ in range(n_cities):
            has_cap = srow.state_name not in ["Tamil Nadu", "West Bengal"]  # mimic Chennai/Kolkata exemption
            city_rows.append((city_id, district_id, fake.city()[:100], None, has_cap))
            city_id += 1
        district_id += 1

district_df = pd.DataFrame(district_rows, columns=["district_id", "state_id", "district_name"])
city_df = pd.DataFrame(city_rows, columns=["city_id", "district_id", "city_name", "total_capacity", "has_capacity_cap"])

# ----------------------------------------------------------------------
# 2. EXAMINATION DEFINITION
# ----------------------------------------------------------------------
exam_authority_df = pd.DataFrame([
    (1, "NTA", "central_govt"),
], columns=["authority_id", "authority_name", "authority_type"])

examination_df = pd.DataFrame([
    (1, 1, "NEET-UG", "paper", False),
], columns=["examination_id", "authority_id", "examination_name", "examination_mode", "is_recruitment"])

exam_cycle_df = pd.DataFrame([
    (1, 1, 2026, "2026 Session 1", "2026-01-15", "2026-03-15"),
], columns=["exam_cycle_id", "examination_id", "cycle_year", "cycle_label",
            "registration_open_at", "registration_close_at"])

subject_df = pd.DataFrame([
    (1, 1, "PHY", "Physics"),
    (2, 1, "CHEM", "Chemistry"),
    (3, 1, "BIO", "Biology"),
], columns=["subject_id", "examination_id", "subject_code", "subject_name"])

exam_session_df = pd.DataFrame([
    (1, 1, None, "2026-05-03", "morning", "10:00", "13:20"),
], columns=["exam_session_id", "exam_cycle_id", "subject_id", "session_date",
            "shift_code", "start_time", "end_time"])
# subject_id null since NEET is a combined single-session paper across all 3 subjects

# ----------------------------------------------------------------------
# 3. CANDIDATE LOOKUPS
# ----------------------------------------------------------------------
candidate_category_df = pd.DataFrame([
    (1, "GEN", "General"), (2, "SC", "Scheduled Caste"), (3, "ST", "Scheduled Tribe"),
    (4, "OBC", "Other Backward Class"), (5, "EWS", "Economically Weaker Section"),
], columns=["category_id", "category_code", "category_name"])

pwbd_status_df = pd.DataFrame([
    (1, "Visual Impairment", "Extra time + scribe", "CERT-VI"),
    (2, "Locomotor Disability", "Ground floor center", "CERT-LD"),
    (3, "Hearing Impairment", "Written instructions only", "CERT-HI"),
], columns=["pwbd_status_id", "disability_type", "accommodation_required", "certificate_reference"])

# ----------------------------------------------------------------------
# 4. EXAM CENTERS + INFRASTRUCTURE (with anomaly injection)
# ----------------------------------------------------------------------
n_anomalous = int(N_CENTERS * ANOMALOUS_CENTER_FRACTION)
anomalous_center_ids = set(np.random.choice(range(1, N_CENTERS + 1), size=n_anomalous, replace=False))

center_rows, infra_rows = [], []
building_types = ["school", "college", "government_office", "private_institute"]

for cid in range(1, N_CENTERS + 1):
    city_row = city_df.sample(1, random_state=cid).iloc[0]
    is_anomalous = cid in anomalous_center_ids
    n_rooms = np.random.randint(3, 9)
    center_rows.append((
        cid, city_row.city_id, f"{fake.company()} Examination Centre"[:200],
        f"EC-{2026}-{cid:05d}", fake.address().replace("\n", ", ")[:250],
        random.choice(building_types), n_rooms
    ))
    # Anomalous centers tend to have weaker infrastructure — but not deterministically,
    # so a fairness audit can genuinely test whether risk correlates with poverty proxies
    # rather than pure infra weakness.
    if is_anomalous:
        cctv = np.random.randint(0, 3)
        biometric = np.random.randint(0, 2)
        perimeter = np.random.randint(1, 3)
        internet = np.random.randint(10, 50)
    else:
        cctv = np.random.randint(2, 10)
        biometric = np.random.randint(1, 5)
        perimeter = np.random.randint(2, 6)
        internet = np.random.randint(40, 100)
    infra_rows.append((
        cid, bool(np.random.rand() > 0.15), min(internet, 100),
        cctv, biometric, np.random.randint(0, 4),
        min(perimeter, 5), fake.date_between(start_date="-2y", end_date="-30d")
    ))

exam_center_df = pd.DataFrame(center_rows, columns=[
    "exam_center_id", "city_id", "center_name", "center_code", "address",
    "building_type", "total_room_count"
])
center_infrastructure_df = pd.DataFrame(infra_rows, columns=[
    "exam_center_id", "power_backup_available", "internet_reliability_score",
    "cctv_camera_count", "biometric_device_count", "metal_detector_count",
    "perimeter_security_rating", "last_audit_date"
])
center_infrastructure_df["is_synthetic_anomalous_center"] = center_infrastructure_df["exam_center_id"].isin(anomalous_center_ids)

# ----------------------------------------------------------------------
# 5. ROOMS & SEATS
# ----------------------------------------------------------------------
room_rows, seat_rows = [], []
room_id_counter, seat_id_counter = 1, 1
center_room_map = {}  # center_id -> list of room_ids

for _, crow in exam_center_df.iterrows():
    cid = crow.exam_center_id
    n_rooms = crow.total_room_count
    room_ids_here = []
    for r in range(1, n_rooms + 1):
        capacity = np.random.choice([25, 30, 35])
        cctv_covered = bool(np.random.rand() > 0.3)
        room_rows.append((room_id_counter, cid, f"R{r:02d}", capacity, cctv_covered))
        for s in range(1, capacity + 1):
            seat_rows.append((seat_id_counter, room_id_counter, str((s - 1) // 6 + 1), str((s - 1) % 6 + 1), f"S{s:03d}"))
            seat_id_counter += 1
        room_ids_here.append(room_id_counter)
        room_id_counter += 1
    center_room_map[cid] = room_ids_here

room_df = pd.DataFrame(room_rows, columns=["room_id", "exam_center_id", "room_number", "capacity", "cctv_covered"])
seat_df = pd.DataFrame(seat_rows, columns=["seat_id", "room_id", "seat_row", "seat_column", "seat_number"])

print(f"Total seat capacity generated: {len(seat_df):,} across {len(room_df):,} rooms in {N_CENTERS} centers")

# ----------------------------------------------------------------------
# 6. CANDIDATES, APPLICATIONS, PAYMENTS
# ----------------------------------------------------------------------
genders = ["male", "female", "other"]
id_types = ["aadhaar", "passport", "pan"]

candidate_rows = []
for i in range(1, N_CANDIDATES + 1):
    dob = fake.date_of_birth(minimum_age=17, maximum_age=25)
    raw_id = "".join(random.choices(string.digits, k=12))
    id_hash = hashlib.sha256(raw_id.encode()).hexdigest()
    candidate_rows.append((
        i, fake.name(), dob, random.choice(genders),
        random.choices(candidate_category_df.category_id.tolist(), weights=[45, 15, 8, 27, 5])[0],
        random.choice([None, None, None, None, 1, 2, 3]),  # ~15% PwBD-ish sampling skew corrected below
        fake.unique.email(), fake.msisdn()[:15],
        f"/media/photos/{i}.jpg", f"/media/signatures/{i}.jpg",
        random.choice(id_types), id_hash,
        fake.date_time_between(start_date="-1y", end_date="-2M")
    ))

candidate_df = pd.DataFrame(candidate_rows, columns=[
    "candidate_id", "full_name", "date_of_birth", "gender", "category_id",
    "pwbd_status_id", "email", "phone_number", "photograph_path", "signature_path",
    "national_id_type", "national_id_number_hash", "registered_at"
])
# Fix PwBD sampling to be a clean small minority rather than a weighted list artifact
pwbd_mask = np.random.rand(len(candidate_df)) < 0.03
candidate_df["pwbd_status_id"] = np.where(
    pwbd_mask, np.random.choice(pwbd_status_df.pwbd_status_id.tolist(), size=len(candidate_df)), np.nan
)

application_rows = []
for cid_ in candidate_df.candidate_id:
    application_rows.append((
        cid_, cid_, 1, "verified",
        fake.date_time_between(start_date="-1y", end_date="-3M"),
        fake.ipv4(), hashlib.md5(str(np.random.randint(0, 5000)).encode()).hexdigest()
    ))
application_df = pd.DataFrame(application_rows, columns=[
    "application_id", "candidate_id", "exam_cycle_id", "application_status",
    "submitted_at", "ip_address", "device_fingerprint"
])

payment_rows = []
for aid in application_df.application_id:
    payment_rows.append((
        aid, aid, f"TXN{aid:08d}{random.randint(100,999)}", 1700.00,
        random.choice(["Razorpay", "PayU", "CCAvenue"]), "success", None,
        fake.date_time_between(start_date="-1y", end_date="-3M")
    ))
payment_df = pd.DataFrame(payment_rows, columns=[
    "payment_id", "application_id", "transaction_ref", "amount", "gateway_name",
    "payment_status", "failure_reason", "paid_at"
])

# ----------------------------------------------------------------------
# 7. ALLOCATION & ADMIT CARD
# ----------------------------------------------------------------------
# Assign each candidate to a center (weighted toward candidate's "home" state via random city),
# then to a specific free seat within that center.
all_center_ids = exam_center_df.exam_center_id.tolist()
candidate_center_assignment = np.random.choice(all_center_ids, size=len(candidate_df))
candidate_df["assigned_center_id"] = candidate_center_assignment

allocation_rows = []
admit_card_rows = []
seat_by_center = seat_df.merge(room_df[["room_id", "exam_center_id"]], on="room_id")
seat_pool_per_center = {cid_: list(seat_by_center[seat_by_center.exam_center_id == cid_].seat_id) for cid_ in all_center_ids}
for cid_ in seat_pool_per_center:
    random.shuffle(seat_pool_per_center[cid_])

alloc_id = 1
for _, cand in candidate_df.iterrows():
    center_id = cand.assigned_center_id
    pool = seat_pool_per_center[center_id]
    if not pool:
        continue
    seat_id = pool.pop()
    allocation_rows.append((alloc_id, cand.candidate_id, seat_id, 1, 0.0))
    admit_card_rows.append((
        alloc_id, alloc_id, f"EX2026-{alloc_id:07d}-{random.choice(string.ascii_uppercase)}",
        fake.date_time_between(start_date="-2M", end_date="-1M")
    ))
    alloc_id += 1

allocation_df = pd.DataFrame(allocation_rows, columns=[
    "allocation_id", "candidate_id", "seat_id", "exam_session_id", "distance_from_preference_km"
])
admit_card_df = pd.DataFrame(admit_card_rows, columns=[
    "admit_card_id", "allocation_id", "barcode_value", "download_timestamp"
])

# ----------------------------------------------------------------------
# 8. INVIGILATORS
# ----------------------------------------------------------------------
invigilator_rows = []
n_invigilators = 3000
for i in range(1, n_invigilators + 1):
    invigilator_rows.append((i, fake.name(), np.random.randint(0, 25), None))
invigilator_df = pd.DataFrame(invigilator_rows, columns=[
    "invigilator_id", "full_name", "experience_years", "previous_assignments_count"
])

invigilator_assignment_rows = []
ia_id = 1
inv_pool = list(invigilator_df.invigilator_id)
for cid_, room_ids_here in center_room_map.items():
    is_anom = cid_ in anomalous_center_ids
    n_needed = max(1, int(len(room_ids_here) * (0.6 if is_anom else 1.0)))  # anomalous centers understaffed
    assigned_invs = random.sample(inv_pool, min(n_needed, len(inv_pool)))
    for j, room_id in enumerate(room_ids_here):
        inv_id = assigned_invs[j % len(assigned_invs)]
        invigilator_assignment_rows.append((ia_id, inv_id, room_id, 1, "present"))
        ia_id += 1
invigilator_assignment_df = pd.DataFrame(invigilator_assignment_rows, columns=[
    "invigilator_assignment_id", "invigilator_id", "room_id", "exam_session_id", "attendance_status"
])

# ----------------------------------------------------------------------
# 9. ATTENDANCE + BIOMETRIC VERIFICATION
# ----------------------------------------------------------------------
attendance_rows, biometric_rows = [], []
bio_id = 1
for _, row in allocation_df.iterrows():
    present = np.random.rand() > 0.045  # ~95.5% attendance rate, matches typical NEET attendance
    entry_time = f"2026-05-03 {np.random.randint(9,10):02d}:{np.random.randint(0,59):02d}:00" if present else None
    exit_time = f"2026-05-03 {np.random.randint(13,14):02d}:{np.random.randint(0,20):02d}:00" if present else None
    attendance_rows.append((
        row.allocation_id, row.allocation_id, "present" if present else "absent",
        entry_time, exit_time, None if present else random.choice(["no_show", "medical", "unknown"])
    ))
    if present:
        match_status = np.random.choice(["match", "no_match", "error"], p=[0.97, 0.02, 0.01])
        biometric_rows.append((bio_id, row.candidate_id, entry_time, f"DEV{np.random.randint(1,500):04d}",
                                np.random.randint(70, 100) if match_status == "match" else np.random.randint(0, 60),
                                match_status, 0 if match_status == "match" else np.random.randint(1, 3)))
        bio_id += 1

attendance_df = pd.DataFrame(attendance_rows, columns=[
    "attendance_id", "allocation_id", "attendance_status", "entry_timestamp",
    "exit_timestamp", "absence_reason"
])
biometric_verification_log_df = pd.DataFrame(biometric_rows, columns=[
    "biometric_log_id", "candidate_id", "capture_timestamp", "device_id",
    "match_score", "match_status", "retry_count"
])

# ----------------------------------------------------------------------
# 10. QUESTION PAPER SETS
# ----------------------------------------------------------------------
question_paper_set_df = pd.DataFrame([
    (1, 1, "SET-A", 1), (2, 1, "SET-B", 1), (3, 1, "SET-C", 1), (4, 1, "SET-D", 1),
], columns=["question_paper_set_id", "exam_session_id", "set_code", "review_status"])

# ----------------------------------------------------------------------
# 11. SCORES & RESULTS (this is where anomaly signatures live)
# ----------------------------------------------------------------------
score_rows, result_rows = [], []
present_candidates = attendance_df[attendance_df.attendance_status == "present"].merge(
    allocation_df, on="allocation_id"
).merge(candidate_df[["candidate_id", "assigned_center_id"]], on="candidate_id")

for _, row in present_candidates.iterrows():
    is_anom_center = row.assigned_center_id in anomalous_center_ids
    if is_anom_center and np.random.rand() < 0.7:
        # Suspiciously tight, inflated score clustering + low response-time variance
        phy = np.clip(np.random.normal(155, 8, 1)[0], 0, 180)
        chem = np.clip(np.random.normal(150, 8, 1)[0], 0, 180)
        bio = np.clip(np.random.normal(155, 8, 1)[0], 0, 180)
        response_time_variance = np.random.uniform(0.5, 2.5)  # unnaturally low
        changed_to_correct_rate = np.random.uniform(0.7, 0.95)  # very high
    else:
        phy = np.clip(np.random.normal(85, 35, 1)[0], 0, 180)
        chem = np.clip(np.random.normal(80, 35, 1)[0], 0, 180)
        bio = np.clip(np.random.normal(95, 35, 1)[0], 0, 180)
        response_time_variance = np.random.uniform(8, 25)
        changed_to_correct_rate = np.random.uniform(0.1, 0.45)

    total = phy + chem + bio
    score_rows.append((
        row.candidate_id, row.candidate_id, round(phy, 1), round(chem, 1), round(bio, 1),
        round(total, 1), round(response_time_variance, 2), round(changed_to_correct_rate, 3),
        random.choice(question_paper_set_df.question_paper_set_id.tolist())
    ))

score_df = pd.DataFrame(score_rows, columns=[
    "score_id", "candidate_id", "physics_score", "chemistry_score", "biology_score",
    "total_score", "response_time_variance", "changed_answer_correct_rate", "question_paper_set_id"
])
score_df["percentile"] = score_df["total_score"].rank(pct=True) * 100
cutoff = score_df["total_score"].quantile(0.50)  # illustrative qualifying cutoff
score_df["rank"] = score_df["total_score"].rank(ascending=False, method="min").astype(int)

result_rows = [(r.candidate_id, r.candidate_id, "qualified" if r.total_score >= cutoff else "not_qualified")
               for r in score_df.itertuples()]
result_df = pd.DataFrame(result_rows, columns=["result_id", "candidate_id", "qualification_status"])

# ----------------------------------------------------------------------
# 12. COMPLAINTS, INCIDENTS, INVESTIGATIONS, AUDITS
# ----------------------------------------------------------------------
complaint_categories = ["paper_leak_suspicion", "impersonation_suspicion", "invigilator_misconduct",
                          "infrastructure_failure", "biometric_failure", "seating_error", "other"]
severities = ["low", "medium", "high", "critical"]

complaint_rows, incident_rows, investigation_rows, audit_rows, audit_finding_rows = [], [], [], [], []
complaint_id = incident_id = investigation_id = audit_id = finding_id = 1

for cid_ in all_center_ids:
    is_anom = cid_ in anomalous_center_ids
    n_complaints = np.random.poisson(6 if is_anom else 1.2)
    for _ in range(n_complaints):
        sev = random.choices(severities, weights=[10, 30, 40, 20] if is_anom else [50, 35, 12, 3])[0]
        complaint_rows.append((
            complaint_id, cid_, random.choice(complaint_categories), sev,
            fake.date_between(start_date="-2M", end_date="today"),
            random.choice(["under_investigation", "resolved", "dismissed"])
        ))
        complaint_id += 1

    n_incidents = np.random.poisson(3 if is_anom else 0.3)
    for _ in range(n_incidents):
        sev = random.choices(severities, weights=[15, 30, 35, 20] if is_anom else [60, 30, 8, 2])[0]
        incident_rows.append((incident_id, cid_, random.choice(
            ["mobile_phone_detected", "identical_answer_pattern", "invigilator_absent",
             "unauthorized_access", "device_malfunction", "candidate_dispute"]
        ), sev, "2026-05-03", "Flagged during exam-day operations review"))
        incident_id += 1

    if is_anom and np.random.rand() < 0.8:
        investigation_rows.append((
            investigation_id, cid_, "STF/Cyber Cell", fake.date_between(start_date="-1M", end_date="today"),
            random.choice(["ongoing", "closed", "escalated"]), np.random.randint(0, 12)
        ))
        investigation_id += 1

    if np.random.rand() < (0.9 if is_anom else 0.2):
        audit_rows.append((audit_id, cid_, fake.date_between(start_date="-3M", end_date="today"),
                            random.choice(["routine", "triggered_by_complaint", "triggered_by_risk_score"])))
        n_findings = np.random.poisson(4 if is_anom else 1)
        for _ in range(n_findings):
            audit_finding_rows.append((
                finding_id, audit_id, random.choice(
                    ["cctv_gap", "frisking_lapse", "documentation_error", "biometric_device_fault",
                     "seating_irregularity", "staff_shortage"]
                ), random.choices(severities, weights=[20, 30, 30, 20] if is_anom else [50, 35, 12, 3])[0]
            ))
            finding_id += 1
        audit_id += 1

complaint_df = pd.DataFrame(complaint_rows, columns=[
    "complaint_id", "exam_center_id", "complaint_category", "severity", "complaint_date", "investigation_status"
])
incident_log_df = pd.DataFrame(incident_rows, columns=[
    "incident_id", "exam_center_id", "incident_type", "severity", "incident_date", "description"
])
investigation_df = pd.DataFrame(investigation_rows, columns=[
    "investigation_id", "exam_center_id", "lead_agency", "start_date", "status", "arrest_count"
])
audit_df = pd.DataFrame(audit_rows, columns=["audit_id", "exam_center_id", "audit_date", "audit_trigger"])
audit_finding_df = pd.DataFrame(audit_finding_rows, columns=[
    "audit_finding_id", "audit_id", "finding_type", "severity"
])

# ----------------------------------------------------------------------
# 13. SOCIAL MEDIA MONITORING LOG
# ----------------------------------------------------------------------
sm_rows = []
sm_id = 1
platforms = ["telegram", "whatsapp", "discord", "reddit"]
for cid_ in anomalous_center_ids:
    n_signals = np.random.randint(1, 5)
    for _ in range(n_signals):
        sm_rows.append((
            sm_id, cid_, random.choice(platforms),
            random.choices(["low", "medium", "high", "critical"], weights=[10, 25, 40, 25])[0],
            "2026-05-03", np.random.randint(50, 5000)
        ))
        sm_id += 1
social_media_monitoring_log_df = pd.DataFrame(sm_rows, columns=[
    "monitoring_log_id", "exam_center_id", "platform", "threat_level", "detected_date", "post_engagement_count"
])

# ----------------------------------------------------------------------
# SAVE ALL TABLES
# ----------------------------------------------------------------------
tables = {
    "dim_state": state_df, "dim_district": district_df, "dim_city": city_df,
    "dim_exam_authority": exam_authority_df, "dim_examination": examination_df,
    "dim_exam_cycle": exam_cycle_df, "dim_subject": subject_df, "dim_exam_session": exam_session_df,
    "dim_candidate_category": candidate_category_df, "dim_pwbd_status": pwbd_status_df,
    "candidate": candidate_df, "application": application_df, "payment": payment_df,
    "exam_center": exam_center_df, "center_infrastructure": center_infrastructure_df,
    "room": room_df, "seat": seat_df,
    "allocation": allocation_df, "admit_card": admit_card_df,
    "invigilator": invigilator_df, "invigilator_assignment": invigilator_assignment_df,
    "attendance": attendance_df, "biometric_verification_log": biometric_verification_log_df,
    "question_paper_set": question_paper_set_df,
    "score": score_df, "result": result_df,
    "complaint": complaint_df, "incident_log": incident_log_df,
    "investigation": investigation_df, "audit": audit_df, "audit_finding": audit_finding_df,
    "social_media_monitoring_log": social_media_monitoring_log_df,
}

for name, df in tables.items():
    df.to_csv(f"{OUT_DIR}/{name}.csv", index=False)

print("\n=== GENERATION SUMMARY ===")
for name, df in tables.items():
    print(f"{name:35s} {len(df):>8,} rows")

print(f"\nAnomalous centers injected: {len(anomalous_center_ids)} of {N_CENTERS} ({ANOMALOUS_CENTER_FRACTION*100:.0f}%)")
print(f"Total candidates: {len(candidate_df):,}")
print(f"Total seats generated: {len(seat_df):,}")
print(f"Qualifying cutoff (illustrative, 50th pct): {cutoff:.1f}")
