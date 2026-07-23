# ExamShield Analytics — National Examination Authority Database Architecture

**Prepared as:** Production-grade relational database design
**Scope:** Full examination lifecycle — registration through post-exam audit
**Target engine:** PostgreSQL (star-schema-ready OLTP core)

---

## 1. Domain Understanding

A National Examination Authority (modeled on NTA/UPSC/SSC/CBSE-style operations, per the attached research) runs a linear-but-branching lifecycle:

1. **Candidate Onboarding** — a person registers once as a `candidate`, then submits one `application` per examination cycle. Applications require `payment` and `document` verification before they're considered valid.
2. **Center & Seat Allocation** — the authority maintains a hierarchy of `state → district → exam_center → room → seat`. Candidates are matched to a specific seat via an `allocation` record, influenced by their preferences and center capacity.
3. **Pre-Exam Logistics** — `admit_card` generation, `question_paper_set` creation, physical `question_paper_packet` sealing, `transport_log` movement (with GPS/digital-lock evidence), and `storage_record` custody chain at the center.
4. **Exam-Day Operations** — `attendance`, `biometric_verification`, `frisking_record`, `invigilator_assignment`, `cctv_footage` metadata, `booklet_distribution`, and `incident_log` entries, all timestamped and tied to a specific seat/room/session.
5. **Post-Exam Processing** — `omr_sheet` scanning, `raw_response` capture, `answer_key` publication, `answer_key_challenge` handling, `score` computation, and final `result` declaration.
6. **Grievance & Integrity** — `complaint`, `audit`, `investigation`, and `penalty` entities close the loop, feeding back into center/candidate risk scoring.
7. **Cross-cutting concerns** — every table needs an audit trail (who/when/what changed), because malpractice investigations (Vyapam, CBSE 2018, UP Police 2024) hinge on being able to reconstruct exactly what happened and who touched what data.

The design below treats **exam_session** (a specific date+shift+subject combination) as the anchor almost everything else hangs off — this is what most operational and forensic queries ("who sat where during the 2024-02-17 morning shift") need.

---

## 2. Entity List

| # | Entity | Purpose | Why It's Required |
|---|--------|---------|--------------------|
| 1 | `state` | Top-level geography | Center allocation, jurisdiction for FIR/police handoff |
| 2 | `district` | Sub-state geography | Granular allocation, local risk indexing |
| 3 | `city` | City-level capacity pool | UPSC-style city preference matching |
| 4 | `exam_authority` | The issuing body (NTA/UPSC/SSC/CBSE etc.) | Multi-authority platform support |
| 5 | `examination` | A named exam (e.g., "SSC CGL 2026") | Root of exam-specific configuration |
| 6 | `exam_cycle` | A yearly/session instance of an examination | Same exam repeats across years |
| 7 | `subject` | Subject/paper code | Multi-subject exams need per-subject papers/results |
| 8 | `exam_session` | Date + shift + subject instance | Anchor for attendance, papers, incidents |
| 9 | `candidate` | The test-taker | Core identity entity |
| 10 | `candidate_category` | Reservation category (SC/ST/OBC/EWS/General) | Statutory reporting, cutoff logic |
| 11 | `pwbd_status` | Disability accommodation record | Legal accommodation requirement (no center cap) |
| 12 | `application` | One candidate's application to one exam_cycle | Core transactional entity |
| 13 | `application_document` | Uploaded ID/certificate | Verification trail |
| 14 | `document_verification` | Verifier decision on a document | Accountability for rejections |
| 15 | `payment` | Fee transaction | Financial reconciliation |
| 16 | `city_preference` | Candidate's ranked city choices | Drives allocation algorithm |
| 17 | `exam_center` | Physical venue | Allocation target |
| 18 | `center_infrastructure` | CCTV/biometric/power/security ratings | Risk scoring input |
| 19 | `room` | Room inside a center | Seat container |
| 20 | `seat` | Individual seat | Finest allocation unit |
| 21 | `allocation` | Candidate ↔ seat assignment for a session | Links candidate to physical location/time |
| 22 | `admit_card` | Generated hall ticket | Entry credential |
| 23 | `biometric_profile` | Candidate's registered biometric template | Baseline for exam-day matching |
| 24 | `biometric_verification_log` | Exam-day match attempt | Fraud/impersonation detection |
| 25 | `question_paper_set` | A unique paper version | Randomization/leak-isolation unit |
| 26 | `question_paper_packet` | Sealed physical packet | Chain-of-custody unit |
| 27 | `transport_log` | Packet movement record | GPS/route/leak forensics |
| 28 | `storage_facility` | Secure storage location | Custody endpoint |
| 29 | `storage_record` | Packet's stay at a facility | Custody trail |
| 30 | `invigilator` | Staff member assigned to proctor | Personnel accountability |
| 31 | `invigilator_assignment` | Invigilator ↔ room/session link | Coverage-ratio KPI source |
| 32 | `attendance` | Candidate presence record | Legal record of participation |
| 33 | `frisking_record` | Entry security check | Electronic-device detection trail |
| 34 | `cctv_camera` | Physical camera asset | Infrastructure inventory |
| 35 | `cctv_footage` | Footage metadata (not the video itself) | Retention/audit compliance |
| 36 | `question_booklet` | Physical booklet given to a candidate | Distribution/collection tracking |
| 37 | `omr_sheet` | Scanned answer sheet | Result-processing input |
| 38 | `raw_response` | Per-question marked answer | Behavior analytics (pattern-matching) |
| 39 | `answer_key` | Official correct answers per set | Scoring baseline |
| 40 | `answer_key_challenge` | Candidate dispute on a key/question | Grievance handling |
| 41 | `score` | Computed raw/normalized score | Result input |
| 42 | `result` | Final declared outcome | Candidate-facing record |
| 43 | `incident_log` | Any exam-day anomaly | Investigation trigger |
| 44 | `complaint` | Candidate-raised grievance | Post-result dispute handling |
| 45 | `investigation` | Formal probe into an incident | Legal/CBI-style tracking |
| 46 | `penalty` | Disciplinary action outcome | Consequence record |
| 47 | `audit` | Scheduled center compliance review | Preventive control |
| 48 | `audit_finding` | Individual finding within an audit | Granular tracking |
| 49 | `staff` | Generic authority/vendor personnel (superintendents, verifiers, auditors, transport staff) | Shared personnel base table |
| 50 | `notification` | System-generated candidate communication | Admit card/result alerts |
| 51 | `social_media_monitoring_log` | Leak-detection alert from platform scanning | Pre-emptive integrity signal |
| 52 | `audit_trail` | Row-level change log (system-wide) | Forensic reconstruction (DPDP/ALCOA+ compliance) |

---

## 3. Database Tables

> Convention: all surrogate PKs are `BIGINT GENERATED ALWAYS AS IDENTITY` unless noted. All tables include `created_at TIMESTAMPTZ NOT NULL DEFAULT now()` and `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()` (omitted below per-table for brevity, listed once here to avoid repetition — Section 9 flags this as an intentional convention, not an omission).

### 3.1 Geography & Authority

**`state`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| state_id | SMALLINT IDENTITY | NO | PK | Surrogate key |
| state_name | VARCHAR(100) | NO | UNIQUE | e.g., "Maharashtra" |
| state_code | CHAR(2) | NO | UNIQUE | ISO/GoI code |

**`district`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| district_id | INT IDENTITY | NO | PK | Surrogate key |
| state_id | SMALLINT | NO | FK → state | Parent state |
| district_name | VARCHAR(100) | NO | | District name |
| UNIQUE(state_id, district_name) | | | | Prevents duplicate district per state |

**`city`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| city_id | INT IDENTITY | NO | PK | Surrogate key |
| district_id | INT | NO | FK → district | Parent district |
| city_name | VARCHAR(100) | NO | | City name |
| total_capacity | INT | YES | CHECK (total_capacity >= 0) | Aggregate seat capacity across centers |
| has_capacity_cap | BOOLEAN | NO | DEFAULT true | False for exempt cities (Chennai, Dispur, Kolkata, Nagpur per UPSC model) |

**`exam_authority`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| authority_id | SMALLINT IDENTITY | NO | PK | Surrogate key |
| authority_name | VARCHAR(150) | NO | UNIQUE | e.g., "NTA", "UPSC", "SSC", "CBSE" |
| authority_type | VARCHAR(50) | NO | CHECK IN ('central_govt','state_govt','autonomous_board','international') | Classification |

### 3.2 Examination Definition

**`examination`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| examination_id | INT IDENTITY | NO | PK | Surrogate key |
| authority_id | SMALLINT | NO | FK → exam_authority | Owning authority |
| examination_name | VARCHAR(200) | NO | | e.g., "SSC CGL" |
| examination_mode | VARCHAR(20) | NO | CHECK IN ('paper','cbt','hybrid') | Delivery mode |
| is_recruitment | BOOLEAN | NO | DEFAULT false | Recruitment vs. academic exam |

**`exam_cycle`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| exam_cycle_id | INT IDENTITY | NO | PK | Surrogate key |
| examination_id | INT | NO | FK → examination | Parent exam |
| cycle_year | SMALLINT | NO | CHECK (cycle_year BETWEEN 2000 AND 2100) | Year of this instance |
| cycle_label | VARCHAR(50) | YES | | e.g., "2026 Session 1" |
| registration_open_at | TIMESTAMPTZ | NO | | Registration window start |
| registration_close_at | TIMESTAMPTZ | NO | CHECK (registration_close_at > registration_open_at) | Registration window end |
| UNIQUE(examination_id, cycle_year, cycle_label) | | | | Prevents duplicate cycles |

**`subject`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| subject_id | INT IDENTITY | NO | PK | Surrogate key |
| examination_id | INT | NO | FK → examination | Owning exam |
| subject_code | VARCHAR(20) | NO | | e.g., "ECO", "PHY" |
| subject_name | VARCHAR(150) | NO | | Full name |
| UNIQUE(examination_id, subject_code) | | | | No duplicate codes per exam |

**`exam_session`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| exam_session_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| exam_cycle_id | INT | NO | FK → exam_cycle | Parent cycle |
| subject_id | INT | NO | FK → subject | Subject being tested |
| session_date | DATE | NO | | Exam date |
| shift_code | VARCHAR(10) | NO | CHECK IN ('morning','afternoon','evening') | Shift label |
| start_time | TIME | NO | | Scheduled start |
| end_time | TIME | NO | CHECK (end_time > start_time) | Scheduled end |
| UNIQUE(exam_cycle_id, subject_id, session_date, shift_code) | | | | One session per combo |

### 3.3 Candidate & Application

**`candidate`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| candidate_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| full_name | VARCHAR(150) | NO | | Legal name |
| date_of_birth | DATE | NO | | DOB |
| gender | VARCHAR(20) | NO | CHECK IN ('male','female','other','prefer_not_to_say') | Gender |
| category_id | SMALLINT | NO | FK → candidate_category | Reservation category |
| pwbd_status_id | SMALLINT | YES | FK → pwbd_status | Disability status, nullable if N/A |
| email | VARCHAR(150) | NO | UNIQUE | Login/contact |
| phone_number | VARCHAR(15) | NO | | Contact number |
| photograph_path | TEXT | YES | | Storage path, not raw bytes |
| signature_path | TEXT | YES | | Storage path |
| national_id_type | VARCHAR(30) | NO | CHECK IN ('aadhaar','passport','pan','other') | ID proof type |
| national_id_number_hash | VARCHAR(256) | NO | UNIQUE | **Hashed**, never plaintext (DPDP Act 2023) |
| registered_at | TIMESTAMPTZ | NO | DEFAULT now() | Account creation |

**`candidate_category`** (lookup)
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| category_id | SMALLINT IDENTITY | NO | PK | Surrogate key |
| category_code | VARCHAR(10) | NO | UNIQUE | GEN/SC/ST/OBC/EWS |
| category_name | VARCHAR(100) | NO | | Full label |

**`pwbd_status`** (lookup)
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| pwbd_status_id | SMALLINT IDENTITY | NO | PK | Surrogate key |
| disability_type | VARCHAR(100) | NO | | e.g., "Visual Impairment" |
| accommodation_required | TEXT | YES | | Free-text accommodation notes |
| certificate_reference | VARCHAR(100) | YES | | Certifying authority reference number |

**`application`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| application_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| candidate_id | BIGINT | NO | FK → candidate | Applicant |
| exam_cycle_id | INT | NO | FK → exam_cycle | Exam being applied for |
| application_status | VARCHAR(20) | NO | CHECK IN ('draft','submitted','verified','rejected','withdrawn') DEFAULT 'draft' | Lifecycle state |
| submitted_at | TIMESTAMPTZ | YES | | Submission timestamp |
| ip_address | INET | YES | | Submission IP |
| device_fingerprint | VARCHAR(256) | YES | | Anti-multiple-registration signal |
| UNIQUE(candidate_id, exam_cycle_id) | | | | **One application per candidate per cycle** |

**`application_document`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| application_document_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| application_id | BIGINT | NO | FK → application | Parent application |
| document_type | VARCHAR(50) | NO | CHECK IN ('photo','signature','category_cert','pwbd_cert','id_proof','education_cert') | Document class |
| file_path | TEXT | NO | | Storage path |
| uploaded_at | TIMESTAMPTZ | NO | DEFAULT now() | Upload time |

**`document_verification`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| verification_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| application_document_id | BIGINT | NO | FK → application_document | Document verified |
| verifier_staff_id | BIGINT | NO | FK → staff | Who verified |
| verification_status | VARCHAR(20) | NO | CHECK IN ('approved','rejected','pending') | Outcome |
| rejection_reason | TEXT | YES | | Required if rejected (enforced at app layer) |
| verified_at | TIMESTAMPTZ | NO | DEFAULT now() | Decision timestamp |

**`payment`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| payment_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| application_id | BIGINT | NO | FK → application | Related application |
| transaction_ref | VARCHAR(100) | NO | UNIQUE | Gateway transaction ID |
| amount | NUMERIC(10,2) | NO | CHECK (amount >= 0) | Fee amount |
| gateway_name | VARCHAR(50) | NO | | Payment gateway used |
| payment_status | VARCHAR(20) | NO | CHECK IN ('success','failed','refunded','pending') | Status |
| failure_reason | TEXT | YES | | If failed |
| paid_at | TIMESTAMPTZ | YES | | Success timestamp |

**`city_preference`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| city_preference_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| application_id | BIGINT | NO | FK → application | Related application |
| city_id | INT | NO | FK → city | Preferred city |
| preference_rank | SMALLINT | NO | CHECK (preference_rank BETWEEN 1 AND 3) | 1st/2nd/3rd choice |
| UNIQUE(application_id, preference_rank) | | | | One city per rank |

### 3.4 Center, Room, Seat

**`exam_center`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| exam_center_id | INT IDENTITY | NO | PK | Surrogate key |
| city_id | INT | NO | FK → city | Location |
| center_name | VARCHAR(200) | NO | | Venue name |
| center_code | VARCHAR(20) | NO | UNIQUE | Official code |
| address | TEXT | NO | | Full address |
| building_type | VARCHAR(30) | NO | CHECK IN ('school','college','government_office','private_institute') | Category |
| total_room_count | SMALLINT | YES | CHECK (total_room_count >= 0) | Derived/cached count |

**`center_infrastructure`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| exam_center_id | INT | NO | PK, FK → exam_center | 1:1 with center |
| power_backup_available | BOOLEAN | NO | DEFAULT false | Generator/UPS |
| internet_reliability_score | SMALLINT | YES | CHECK (BETWEEN 0 AND 100) | Ordinal score |
| cctv_camera_count | SMALLINT | NO | DEFAULT 0 | Infrastructure count |
| biometric_device_count | SMALLINT | NO | DEFAULT 0 | Device inventory |
| metal_detector_count | SMALLINT | NO | DEFAULT 0 | Device inventory |
| perimeter_security_rating | SMALLINT | YES | CHECK (BETWEEN 1 AND 5) | Ordinal |
| last_audit_date | DATE | YES | | Most recent audit reference |

**`room`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| room_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| exam_center_id | INT | NO | FK → exam_center | Parent center |
| room_number | VARCHAR(20) | NO | | Room label |
| capacity | SMALLINT | NO | CHECK (capacity > 0) | Max seats |
| cctv_covered | BOOLEAN | NO | DEFAULT false | Coverage flag |
| UNIQUE(exam_center_id, room_number) | | | | **One room number per center** |

**`seat`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| seat_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| room_id | BIGINT | NO | FK → room | Parent room |
| seat_row | VARCHAR(5) | NO | | Row label |
| seat_column | VARCHAR(5) | NO | | Column label |
| seat_number | VARCHAR(10) | NO | | Display number |
| UNIQUE(room_id, seat_number) | | | | **Seat numbers unique within a room** |

### 3.5 Allocation & Admit Card

**`allocation`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| allocation_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| application_id | BIGINT | NO | FK → application | Candidate's application |
| exam_session_id | BIGINT | NO | FK → exam_session | Session allocated to |
| seat_id | BIGINT | NO | FK → seat | Assigned seat |
| allocation_algorithm_version | VARCHAR(20) | NO | | Version tag for reproducibility |
| distance_from_preference_km | NUMERIC(6,2) | YES | | Delta from preferred city |
| allocated_at | TIMESTAMPTZ | NO | DEFAULT now() | Allocation timestamp |
| UNIQUE(application_id, exam_session_id) | | | | One seat per candidate per session |
| UNIQUE(seat_id, exam_session_id) | | | | **One candidate per seat per session** |

**`admit_card`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| admit_card_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| allocation_id | BIGINT | NO | FK → allocation, UNIQUE | 1:1 with allocation |
| roll_number | VARCHAR(30) | NO | UNIQUE | Public candidate identifier |
| barcode_value | VARCHAR(100) | NO | UNIQUE | QR/barcode payload |
| generated_at | TIMESTAMPTZ | NO | DEFAULT now() | Generation timestamp |
| first_downloaded_at | TIMESTAMPTZ | YES | | First download |
| download_count | INT | NO | DEFAULT 0 CHECK (download_count >= 0) | Usage tracking |

### 3.6 Biometrics

**`biometric_profile`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| biometric_profile_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| candidate_id | BIGINT | NO | FK → candidate, UNIQUE | 1:1 with candidate |
| template_reference | VARCHAR(256) | NO | | Pointer to encrypted template store (not raw biometric) |
| modality | VARCHAR(20) | NO | CHECK IN ('fingerprint','iris','face','multi_modal') | Capture type |
| captured_at | TIMESTAMPTZ | NO | | Registration capture time |
| retention_expiry_date | DATE | NO | | DPDP-mandated deletion date |

**`biometric_verification_log`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| verification_log_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| allocation_id | BIGINT | NO | FK → allocation | Which sitting |
| device_id | VARCHAR(50) | NO | | Capture device |
| operator_staff_id | BIGINT | YES | FK → staff | Operator on duty |
| match_score | NUMERIC(5,2) | YES | CHECK (BETWEEN 0 AND 100) | Similarity score |
| match_status | VARCHAR(20) | NO | CHECK IN ('match','no_match','error','not_attempted') | Outcome |
| retry_count | SMALLINT | NO | DEFAULT 0 | Retry attempts |
| captured_at | TIMESTAMPTZ | NO | DEFAULT now() | Timestamp |

### 3.7 Question Paper & Logistics

**`question_paper_set`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| set_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| subject_id | INT | NO | FK → subject | Subject covered |
| set_code | VARCHAR(20) | NO | | e.g., "Set-A" |
| version_number | SMALLINT | NO | DEFAULT 1 | Version tracking |
| author_staff_id | BIGINT | NO | FK → staff | Question setter |
| review_status | VARCHAR(20) | NO | CHECK IN ('draft','reviewed','approved') | Workflow state |
| created_at_ts | TIMESTAMPTZ | NO | DEFAULT now() | Creation time |
| UNIQUE(subject_id, set_code, version_number) | | | | No duplicate set/version |

**`question_paper_packet`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| packet_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| set_id | BIGINT | NO | FK → question_paper_set | Contents |
| exam_center_id | INT | NO | FK → exam_center | Destination |
| seal_number | VARCHAR(50) | NO | UNIQUE | Physical seal ID |
| printing_timestamp | TIMESTAMPTZ | NO | | Print time |
| dispatch_timestamp | TIMESTAMPTZ | YES | | Dispatch time |
| digital_lock_code_hash | VARCHAR(256) | YES | | Hashed release code |

**`transport_log`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| transport_log_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| packet_id | BIGINT | NO | FK → question_paper_packet | Cargo |
| vehicle_number | VARCHAR(20) | NO | | Vehicle registration |
| driver_staff_id | BIGINT | YES | FK → staff | Driver |
| escort_staff_id | BIGINT | YES | FK → staff | Security escort |
| gps_lat | NUMERIC(9,6) | YES | | Last known latitude |
| gps_long | NUMERIC(9,6) | YES | | Last known longitude |
| route_deviation_flag | BOOLEAN | NO | DEFAULT false | Deviation alert |
| delivery_confirmed_at | TIMESTAMPTZ | YES | | Delivery timestamp |
| logged_at | TIMESTAMPTZ | NO | DEFAULT now() | Log entry time |

**`storage_facility`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| storage_facility_id | INT IDENTITY | NO | PK | Surrogate key |
| exam_center_id | INT | YES | FK → exam_center | Null if central warehouse |
| facility_name | VARCHAR(150) | NO | | Name/label |
| has_cctv | BOOLEAN | NO | DEFAULT false | Coverage flag |

**`storage_record`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| storage_record_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| packet_id | BIGINT | NO | FK → question_paper_packet | Item stored |
| storage_facility_id | INT | NO | FK → storage_facility | Location |
| entry_timestamp | TIMESTAMPTZ | NO | | Custody start |
| exit_timestamp | TIMESTAMPTZ | YES | CHECK (exit_timestamp > entry_timestamp) | Custody end |
| access_log_ref | TEXT | YES | | Pointer to detailed access log |

### 3.8 Personnel

**`staff`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| staff_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| full_name | VARCHAR(150) | NO | | Name |
| staff_role | VARCHAR(30) | NO | CHECK IN ('invigilator','superintendent','verifier','auditor','driver','escort','operator','question_setter','investigator') | Role class |
| contact_number | VARCHAR(15) | YES | | Contact |
| years_experience | SMALLINT | YES | CHECK (years_experience >= 0) | Experience |
| training_completed_at | DATE | YES | | Last training completion |

**`invigilator_assignment`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| assignment_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| staff_id | BIGINT | NO | FK → staff | Invigilator |
| room_id | BIGINT | NO | FK → room | Assigned room |
| exam_session_id | BIGINT | NO | FK → exam_session | Assigned session |
| attendance_status | VARCHAR(20) | NO | CHECK IN ('present','absent','late') DEFAULT 'present' | Own attendance |
| UNIQUE(staff_id, room_id, exam_session_id) | | | | No duplicate assignment |

### 3.9 Exam-Day Operations

**`attendance`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| attendance_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| allocation_id | BIGINT | NO | FK → allocation, UNIQUE | **Cannot exist without seat allocation** |
| entry_timestamp | TIMESTAMPTZ | YES | | Entry time |
| exit_timestamp | TIMESTAMPTZ | YES | CHECK (exit_timestamp > entry_timestamp) | Exit time |
| attendance_status | VARCHAR(20) | NO | CHECK IN ('present','absent','debarred') | Status |
| absence_reason | TEXT | YES | | If absent |

**`frisking_record`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| frisking_record_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| allocation_id | BIGINT | NO | FK → allocation | Candidate frisked |
| operator_staff_id | BIGINT | NO | FK → staff | Frisking staff |
| frisked_at | TIMESTAMPTZ | NO | DEFAULT now() | Timestamp |
| items_detected | TEXT | YES | | Free-text list |
| action_taken | VARCHAR(50) | YES | CHECK IN ('none','confiscated','debarred','reported') | Response |

**`cctv_camera`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| camera_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| room_id | BIGINT | YES | FK → room | Null if covering common areas |
| exam_center_id | INT | NO | FK → exam_center | Owning center |
| installation_date | DATE | YES | | Install date |

**`cctv_footage`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| footage_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| camera_id | BIGINT | NO | FK → cctv_camera | Source camera |
| exam_session_id | BIGINT | YES | FK → exam_session | Session covered |
| file_path | TEXT | NO | | Storage pointer (metadata only) |
| duration_seconds | INT | YES | CHECK (duration_seconds >= 0) | Length |
| retention_expiry_date | DATE | NO | | Mandatory retention rule |

**`question_booklet`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| booklet_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| allocation_id | BIGINT | NO | FK → allocation, UNIQUE | Given to one candidate |
| set_id | BIGINT | NO | FK → question_paper_set | Paper version |
| distributed_at | TIMESTAMPTZ | YES | | Distribution time |
| collected_at | TIMESTAMPTZ | YES | CHECK (collected_at > distributed_at) | Collection time |
| damage_status | VARCHAR(20) | NO | CHECK IN ('none','minor','major') DEFAULT 'none' | Condition |

**`incident_log`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| incident_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| exam_session_id | BIGINT | NO | FK → exam_session | Session context |
| room_id | BIGINT | YES | FK → room | Location, if applicable |
| allocation_id | BIGINT | YES | FK → allocation | Candidate involved, if applicable |
| incident_type | VARCHAR(50) | NO | CHECK IN ('paper_leak','device_found','impersonation','collusion','server_breach','other') | Classification |
| severity | VARCHAR(20) | NO | CHECK IN ('low','medium','high','critical') | Severity |
| description | TEXT | NO | | Details |
| reported_at | TIMESTAMPTZ | NO | DEFAULT now() | Report timestamp |
| resolution_status | VARCHAR(20) | NO | CHECK IN ('open','under_review','resolved') DEFAULT 'open' | Status |

### 3.10 Post-Exam Processing

**`omr_sheet`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| omr_sheet_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| booklet_id | BIGINT | NO | FK → question_booklet, UNIQUE | Source booklet |
| scanned_at | TIMESTAMPTZ | YES | | Scan timestamp |
| scan_quality_score | NUMERIC(5,2) | YES | CHECK (BETWEEN 0 AND 100) | Quality metric |
| manual_verification_flag | BOOLEAN | NO | DEFAULT false | Needs manual check |

**`raw_response`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| response_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| omr_sheet_id | BIGINT | NO | FK → omr_sheet | Parent sheet |
| question_number | SMALLINT | NO | | Question sequence |
| marked_answer | VARCHAR(5) | YES | | Option marked, null if blank |
| time_spent_seconds | INT | YES | CHECK (time_spent_seconds >= 0) | For CBT only |
| UNIQUE(omr_sheet_id, question_number) | | | | One response per question per sheet |

**`answer_key`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| answer_key_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| set_id | BIGINT | NO | FK → question_paper_set | Paper version |
| question_number | SMALLINT | NO | | Question sequence |
| correct_answer | VARCHAR(5) | NO | | Official answer |
| version_number | SMALLINT | NO | DEFAULT 1 | Revision tracking |
| released_at | TIMESTAMPTZ | NO | | Publication time |
| UNIQUE(set_id, question_number, version_number) | | | | Versioned uniqueness |

**`answer_key_challenge`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| challenge_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| allocation_id | BIGINT | NO | FK → allocation | Challenging candidate |
| answer_key_id | BIGINT | NO | FK → answer_key | Key disputed |
| claimed_answer | VARCHAR(5) | NO | | Candidate's claim |
| evidence_path | TEXT | YES | | Supporting document |
| submitted_at | TIMESTAMPTZ | NO | DEFAULT now() | Submission time |
| challenge_status | VARCHAR(20) | NO | CHECK IN ('pending','accepted','rejected') DEFAULT 'pending' | Resolution |
| resolved_at | TIMESTAMPTZ | YES | | Resolution time |

**`score`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| score_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| allocation_id | BIGINT | NO | FK → allocation, UNIQUE | Candidate sitting |
| raw_score | NUMERIC(7,2) | NO | | Unadjusted score |
| normalized_score | NUMERIC(7,2) | YES | | Post-normalization score |
| percentile | NUMERIC(5,2) | YES | CHECK (BETWEEN 0 AND 100) | Percentile rank |
| computed_at | TIMESTAMPTZ | NO | DEFAULT now() | Computation timestamp |

**`result`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| result_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| score_id | BIGINT | NO | FK → score, UNIQUE | Basis for result |
| qualification_status | VARCHAR(20) | NO | CHECK IN ('qualified','not_qualified','withheld') | Outcome |
| cutoff_value | NUMERIC(7,2) | YES | | Applicable cutoff |
| declared_at | TIMESTAMPTZ | NO | DEFAULT now() | Declaration time |

### 3.11 Grievance, Audit & Investigation

**`complaint`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| complaint_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| candidate_id | BIGINT | NO | FK → candidate | Complainant |
| exam_session_id | BIGINT | NO | FK → exam_session | **Must reference valid session** |
| category | VARCHAR(50) | NO | CHECK IN ('allocation','biometric','result','misconduct','infrastructure','other') | Type |
| description | TEXT | NO | | Details |
| evidence_path | TEXT | YES | | Attachment |
| assigned_staff_id | BIGINT | YES | FK → staff | Handling officer |
| status | VARCHAR(20) | NO | CHECK IN ('open','investigating','resolved','dismissed') DEFAULT 'open' | Status |
| submitted_at | TIMESTAMPTZ | NO | DEFAULT now() | Submission time |
| resolved_at | TIMESTAMPTZ | YES | | Resolution time |

**`audit`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| audit_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| exam_center_id | INT | NO | FK → exam_center | Subject of audit |
| auditor_staff_id | BIGINT | NO | FK → staff | Conducting auditor |
| audit_date | DATE | NO | | Date conducted |
| severity_overall | VARCHAR(20) | YES | CHECK IN ('none','minor','major','critical') | Rollup severity |
| closure_status | VARCHAR(20) | NO | CHECK IN ('open','closed') DEFAULT 'open' | Status |

**`audit_finding`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| finding_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| audit_id | BIGINT | NO | FK → audit | Parent audit |
| checklist_item | VARCHAR(200) | NO | | What was checked |
| finding_detail | TEXT | YES | | Description |
| severity | VARCHAR(20) | NO | CHECK IN ('none','minor','major','critical') | Severity |
| recommendation | TEXT | YES | | Suggested fix |
| closed_at | TIMESTAMPTZ | YES | | Closure timestamp |

**`investigation`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| investigation_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| incident_id | BIGINT | YES | FK → incident_log | Triggering incident, if any |
| complaint_id | BIGINT | YES | FK → complaint | Triggering complaint, if any |
| lead_staff_id | BIGINT | NO | FK → staff | Lead investigator |
| start_date | DATE | NO | | Start date |
| status | VARCHAR(20) | NO | CHECK IN ('ongoing','closed','referred_to_police') DEFAULT 'ongoing' | Status |
| findings | TEXT | YES | | Summary |
| arrest_count | INT | NO | DEFAULT 0 CHECK (arrest_count >= 0) | Outcome metric |
| CHECK (incident_id IS NOT NULL OR complaint_id IS NOT NULL) | | | | Must have a trigger |

**`penalty`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| penalty_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| investigation_id | BIGINT | NO | FK → investigation | Basis for penalty |
| candidate_id | BIGINT | YES | FK → candidate | If candidate penalized |
| staff_id | BIGINT | YES | FK → staff | If staff penalized |
| penalty_type | VARCHAR(50) | NO | CHECK IN ('debarment','fine','termination','fir_referral','disqualification') | Type |
| effective_date | DATE | NO | | Effective date |
| appeal_status | VARCHAR(20) | YES | CHECK IN ('none','pending','upheld','overturned') DEFAULT 'none' | Appeal state |
| CHECK (candidate_id IS NOT NULL OR staff_id IS NOT NULL) | | | | Must penalize someone |

### 3.12 Notifications & Monitoring

**`notification`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| notification_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| candidate_id | BIGINT | NO | FK → candidate | Recipient |
| notification_type | VARCHAR(30) | NO | CHECK IN ('admit_card','result','payment','alert') | Type |
| sent_at | TIMESTAMPTZ | NO | DEFAULT now() | Send time |
| read_at | TIMESTAMPTZ | YES | | Read receipt |

**`social_media_monitoring_log`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| monitoring_log_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| exam_session_id | BIGINT | YES | FK → exam_session | Session possibly affected |
| platform | VARCHAR(30) | NO | CHECK IN ('telegram','whatsapp','discord','reddit','instagram','facebook','other') | Source platform |
| detected_at | TIMESTAMPTZ | NO | DEFAULT now() | Detection time |
| threat_level | VARCHAR(20) | NO | CHECK IN ('low','medium','high','critical') | Severity |
| evidence_reference | TEXT | YES | | Pointer to captured evidence |
| escalated_to_incident_id | BIGINT | YES | FK → incident_log | Linked incident, if escalated |

### 3.13 System Audit Trail

**`audit_trail`**
| Column | Type | Null | Constraints | Description |
|---|---|---|---|---|
| trail_id | BIGINT IDENTITY | NO | PK | Surrogate key |
| table_name | VARCHAR(100) | NO | | Table changed |
| record_id | BIGINT | NO | | PK of changed row |
| operation_type | VARCHAR(10) | NO | CHECK IN ('INSERT','UPDATE','DELETE') | Operation |
| old_value | JSONB | YES | | Pre-change snapshot |
| new_value | JSONB | YES | | Post-change snapshot |
| changed_by_staff_id | BIGINT | YES | FK → staff | Actor, null if system |
| changed_at | TIMESTAMPTZ | NO | DEFAULT now() | Timestamp |

---

## 4. Relationships

| Relationship | Cardinality | Rationale |
|---|---|---|
| state → district | 1:N | A state contains many districts |
| district → city | 1:N | A district contains many cities |
| city → exam_center | 1:N | A city hosts many centers |
| exam_center → room | 1:N | A center has many rooms |
| room → seat | 1:N | A room has many seats |
| exam_authority → examination | 1:N | One authority runs many named exams |
| examination → exam_cycle | 1:N | Same exam recurs yearly |
| examination → subject | 1:N | Multi-subject exams |
| exam_cycle + subject → exam_session | 1:N | Each cycle/subject can have multiple shifts/dates |
| candidate → application | 1:N | One candidate can apply across different cycles (but only once per cycle — enforced by UNIQUE) |
| application → application_document | 1:N | Multiple documents per application |
| application_document → document_verification | 1:1 | Each document gets one verification decision |
| application → payment | 1:N | Retries create multiple payment attempts |
| application → city_preference | 1:N (max 3) | Up to 3 ranked preferences |
| application + exam_session → allocation | 1:1 (per session) | Application allocated to exactly one seat per session |
| seat + exam_session → allocation | 1:1 | **A seat holds one candidate per session** (enforced by UNIQUE) |
| allocation → admit_card | 1:1 | One hall ticket per sitting |
| candidate → biometric_profile | 1:1 | One baseline template per candidate |
| allocation → biometric_verification_log | 1:N | Retries create multiple attempts |
| subject → question_paper_set | 1:N | Multiple set versions per subject |
| question_paper_set → question_paper_packet | 1:N | One set printed into many sealed packets (one per center) |
| question_paper_packet → transport_log | 1:N | Multiple log entries per leg of a journey |
| question_paper_packet → storage_record | 1:N | Multiple storage stops possible |
| staff → invigilator_assignment | 1:N | One invigilator assigned across sessions |
| room + exam_session → invigilator_assignment | 1:N | Multiple invigilators per room possible |
| allocation → attendance | 1:1 | **Attendance cannot exist without allocation** (enforced by FK + UNIQUE) |
| allocation → frisking_record | 1:1 typical | One frisking event per entry |
| exam_center → cctv_camera | 1:N | Many cameras per center |
| cctv_camera → cctv_footage | 1:N | Many footage segments per camera |
| allocation → question_booklet | 1:1 | One booklet issued per candidate sitting |
| question_booklet → omr_sheet | 1:1 | One scanned sheet per booklet |
| omr_sheet → raw_response | 1:N | Many question responses per sheet |
| question_paper_set → answer_key | 1:N | Multiple questions per set, versioned |
| allocation + answer_key → answer_key_challenge | 1:N | Candidate may raise multiple challenges |
| allocation → score | 1:1 | One computed score per sitting |
| score → result | 1:1 | One result per score |
| exam_session → incident_log | 1:N | Many incidents possible per session |
| candidate → complaint | 1:N | Candidate can raise multiple complaints |
| exam_center → audit | 1:N | Repeated audits over time |
| audit → audit_finding | 1:N | Many findings per audit |
| incident_log / complaint → investigation | 1:N (either) | An investigation must stem from an incident or complaint |
| investigation → penalty | 1:N | Multiple parties penalized per investigation |
| candidate → notification | 1:N | Many notifications over time |
| exam_session → social_media_monitoring_log | 1:N | Many monitoring hits per session |

**Many-to-Many resolved via junctions:** candidate ↔ exam_session is inherently M:N in concept (many candidates, many sessions) but is resolved through `application` → `allocation`, which is the correct normalized junction carrying its own attributes (seat, timestamp, algorithm version).

---

## 5. ER Diagram (Text Form)

```
state
 └── district
      └── city
           ├── exam_center
           │    ├── center_infrastructure (1:1)
           │    ├── room
           │    │    ├── seat
           │    │    └── cctv_camera
           │    ├── question_paper_packet
           │    │    ├── transport_log
           │    │    └── storage_record
           │    └── audit
           │         └── audit_finding
           └── city_preference ← application

exam_authority
 └── examination
      ├── exam_cycle
      │    └── application ← candidate
      │         ├── application_document → document_verification
      │         ├── payment
      │         └── city_preference
      └── subject
           ├── exam_session (via exam_cycle + subject)
           │    ├── allocation ← application, seat
           │    │    ├── admit_card
           │    │    ├── biometric_verification_log
           │    │    ├── attendance
           │    │    ├── frisking_record
           │    │    ├── question_booklet → omr_sheet → raw_response
           │    │    ├── score → result
           │    │    └── answer_key_challenge ← answer_key
           │    ├── invigilator_assignment ← staff
           │    ├── incident_log
           │    └── social_media_monitoring_log
           └── question_paper_set
                ├── question_paper_packet
                └── answer_key

candidate
 ├── biometric_profile
 ├── complaint → investigation → penalty
 └── notification

incident_log / complaint
 └── investigation
      └── penalty

(all tables) ⇢ audit_trail   [system-wide change capture]
```

---

## 6. Data Dictionary (Representative Sample)

> Full data dictionary mirrors every column in Section 3. Below is a representative slice per stage; the pattern (Column / Type / Business Meaning / Example / Allowed Values / Validation / Mandatory) extends identically to every remaining column.

| Column | Type | Business Meaning | Example Value | Allowed Values | Validation Rule | Mandatory |
|---|---|---|---|---|---|---|
| `candidate.national_id_number_hash` | VARCHAR(256) | Irreversible hash of government ID, used for de-duplication without storing PII in plaintext | `9f86d081884c7d65...` | SHA-256 hex digest | Must be unique; raw ID never stored | Yes |
| `application.device_fingerprint` | VARCHAR(256) | Browser/device signature used to flag multiple-registration attempts | `a1b2c3d4e5f6...` | Any hash string | Cross-referenced against other applications same cycle | No |
| `allocation.distance_from_preference_km` | NUMERIC(6,2) | How far the allocated city is from the candidate's top preference | `12.50` | 0.00–9999.99 | Must be ≥ 0 | No |
| `admit_card.barcode_value` | VARCHAR(100) | Unique scannable payload verified at center entry | `EX2026-0098213-A` | Alphanumeric | Must be unique system-wide | Yes |
| `biometric_verification_log.match_status` | VARCHAR(20) | Outcome of exam-day biometric check against registered template | `match` | match / no_match / error / not_attempted | Must be one of allowed values | Yes |
| `question_paper_packet.seal_number` | VARCHAR(50) | Physical tamper-evident seal identifier | `SEAL-2026-004421` | Alphanumeric | Must be unique; scanned at both dispatch and center opening | Yes |
| `transport_log.route_deviation_flag` | BOOLEAN | Whether GPS showed the vehicle deviate from planned route | `false` | true / false | Auto-computed from GPS vs. planned route | Yes |
| `incident_log.severity` | VARCHAR(20) | Analyst-assigned severity of an anomaly | `critical` | low / medium / high / critical | Must be one of allowed values | Yes |
| `answer_key_challenge.challenge_status` | VARCHAR(20) | Current resolution state of a candidate's dispute | `pending` | pending / accepted / rejected | Transitions logged in audit_trail | Yes |
| `investigation.arrest_count` | INT | Number of arrests resulting from this investigation | `7` | ≥ 0 | Cannot be negative | No |
| `social_media_monitoring_log.threat_level` | VARCHAR(20) | Severity of a detected leak-related social media signal | `high` | low / medium / high / critical | Feeds Social Media Threat Index KPI | Yes |

---

## 7. Business Rules

**Registration & Application**
1. One candidate may submit only one application per `exam_cycle` (enforced: `UNIQUE(candidate_id, exam_cycle_id)`).
2. An application cannot move to `verified` status until all required `application_document` rows have an `approved` `document_verification`.
3. A `payment` must be `success` before an application can transition to `submitted`.
4. City preferences are capped at exactly 3 ranked entries per application.

**Center, Room, Seat**
5. One room belongs to exactly one examination center (enforced by FK; no cross-center rooms).
6. Seat numbers must be unique within a room (enforced: `UNIQUE(room_id, seat_number)`).
7. A center's advertised capacity must not be exceeded by cumulative room capacities for any single session (application-layer check, since capacity is dynamic per session).
8. PwBD candidates are exempt from any city-level capacity cap.

**Allocation & Admit Card**
9. A seat can hold only one candidate per exam session (enforced: `UNIQUE(seat_id, exam_session_id)`).
10. Admit cards can only be generated for allocations tied to a `verified` application with a `success` payment.
11. Admit card barcode values must be globally unique and are the sole valid entry credential.

**Exam-Day Operations**
12. Attendance cannot exist without a prior seat allocation (enforced: FK `attendance.allocation_id NOT NULL` + `UNIQUE`).
13. Biometric verification failure does not automatically bar entry; it triggers a manual fallback recorded in `frisking_record.action_taken` or a linked `incident_log` entry.
14. Invigilator-to-candidate ratio should not exceed 30:1 for written exams (JCQ-aligned), computed from `invigilator_assignment` vs. `allocation` counts per room/session.
15. A candidate cannot receive a `question_booklet` without a corresponding `attendance` row marked `present`.

**Post-Exam**
16. An `omr_sheet` must reference exactly one `question_booklet`; a booklet cannot be scanned twice (enforced: `UNIQUE(booklet_id)`).
17. `answer_key_challenge` rows may only be created within the authority-defined challenge window (application-layer, referencing `exam_cycle` configuration).
18. `score.normalized_score` can only be computed after `answer_key` for the relevant `set_id` has moved past its final challenge-resolution date.

**Grievance & Audit**
19. Complaints must reference a valid, existing `exam_session` (enforced: FK NOT NULL).
20. An `investigation` must originate from at least one of `incident_log` or `complaint` (enforced: CHECK constraint requiring at least one to be non-null).
21. A `penalty` must target at least a candidate or a staff member (enforced: CHECK constraint).
22. `audit_finding` severity of `critical` should auto-generate a linked `incident_log` entry (application-layer trigger logic).

**Data Governance**
23. No table stores raw biometric images or unhashed national ID numbers — only hashed values or pointers to encrypted stores, per DPDP Act 2023 principles referenced in the research report.
24. Every INSERT/UPDATE/DELETE on integrity-sensitive tables (`allocation`, `attendance`, `score`, `result`, `answer_key`, `penalty`) is captured in `audit_trail` — non-negotiable for post-incident forensic reconstruction (as required in Vyapam/CBSE-style investigations).
25. `cctv_footage` and `biometric_profile` rows must carry a `retention_expiry_date`; a scheduled job (outside DB scope) purges expired rows.

---

## 8. Design Review

**Strengths**
- The `exam_session` + `allocation` design cleanly separates "who is registered" (`application`) from "who sits where and when" (`allocation`), which is the pattern almost every downstream table (attendance, biometrics, booklets, scores) needs to hang off.
- Chain-of-custody for question papers (`set → packet → transport_log → storage_record`) directly mirrors the leak patterns documented in the report (printing press leaks, transport leaks, center-level leaks), making forensic queries natural.
- Hashing/pointer patterns for PII and biometrics build DPDP/GDPR-style compliance into the schema rather than bolting it on later.

**Missing Entities to Consider Adding Later**
- A dedicated `coaching_center` / `third_party_entity` table — the CBSE 2018 case implicated a tuition teacher; if link analysis across external parties becomes a KPI, this deserves its own entity rather than free-text in `incident_log.description`.
- A `question_bank_item` entity beneath `question_paper_set` if you eventually want item-level randomization (IRT-based, per the international best-practices section) rather than treating each set as monolithic.
- A `device_registry` table for candidate-facing CBT device fingerprinting if the platform later supports computer-based testing modes beyond paper.

**Missing Relationships**
- `staff` currently has no direct link to `exam_center` as a "home base" — worth adding a `staff_center_assignment` table if you need center-level staffing rosters independent of specific sessions.
- `social_media_monitoring_log` links to `incident_log` only via nullable FK; if leak detection becomes a first-class analytics feature, consider a proper many-to-many bridge (`monitoring_log_incident_link`) since one leak signal could plausibly escalate into multiple incidents across centers.

**Scalability Concerns**
- `raw_response` and `audit_trail` will be by far the largest tables (millions of candidates × dozens of questions; billions of change events respectively). Both should be **partitioned** — `raw_response` by `exam_session_id` or date range, `audit_trail` by `changed_at` month — from day one rather than retrofitted later.
- `cctv_footage` stores only metadata (by design) — the actual video stays in object storage (S3-compatible), which is correct; just make sure `file_path` conventions are decided before ingestion starts.

**Normalization Note (see Section 4 rationale)**
- The design is in 3NF throughout: every non-key column depends on the whole primary key (2NF) and nothing but the key (3NF) — e.g., `center_infrastructure` is split out from `exam_center` specifically because infrastructure attributes don't define center identity, they describe it, and change independently.
- One deliberate denormalization candidate: caching `exam_center.total_room_count` and `center_infrastructure.cctv_camera_count` as derived counts (rather than always `COUNT()`-ing child rows) is reasonable for dashboard performance, provided it's maintained via trigger — flagged here so it's a conscious choice, not silent drift.

**Suggested Next Step**
- Given Phase 1 (synthetic data) is done, this schema is ready for DDL generation once you confirm PostgreSQL-specific choices: whether to use native `ENUM` types vs. the `CHECK` constraints shown above (CHECK is more portable and easier to alter — recommended for a portfolio project you'll keep iterating on), and whether `audit_trail` should be a single partitioned table or one per monitored table.
