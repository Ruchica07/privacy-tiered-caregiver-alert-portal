# AegisCare — Stakeholder Evaluation Protocol & Usability Methodology (Phase 3)

---

## 1. Study Status & Ethical Research Boundary

> [!IMPORTANT]
> **Human Participants: 0 (Zero)**  
> All usability metrics, task completion rates, and System Usability Scale (SUS) distributions reported in this capstone project are **strictly generated from an automated synthetic stakeholder evaluation protocol (`eval/stakeholder_evaluation.py`)**. No real human subjects, vulnerable older adults, or clinical staff were recruited, contacted, or evaluated in this prototype phase.

Any future empirical deployment involving real individuals will require formal Institutional Review Board (IRB) / Ethics Committee approval, informed consent agreements, and strict compliance with health data privacy regulations.

---

## 2. Simulated Caregiver Personas & Role Profiles

The simulation protocol models four realistic caregiver archetypes interacting with the AegisCare portal:

| Persona Name | Role Identifier | Relationship & Context | Privacy Expectation & Permissions |
| :--- | :--- | :--- | :--- |
| **Jane Smith** | `primary_caregiver` (`cg_001`) | Adult Daughter, primary emergency contact and daily check-in coordinator. | **Tier 2 Access**: Daily activity patterns, check-in adherence, night safety departures, trend timelines. |
| **Bob Smith** | `secondary_caregiver` (`cg_002`) | Adult Son, lives out of town; assists on weekends and backup alerts. | **Tier 1 Access**: Standard operational alerts, actionable recommendations; no raw sensor metrics. |
| **Maria Garcia** | `neighbor_community` (`cg_003`) | Trusted next-door neighbor; assists with physical well-checks. | **Tier 0/1 Access**: Minimal urgent safety indicators (e.g. door open at night); strictly blocked from medication and vitals. |
| **Dr. Sarah Chen** | `care_coordinator_professional` (`cg_004`) | Professional community health care coordinator managing multi-resident fleet. | **Tier 3 (Contextual)**: Qualitative wellness summaries, cross-resident dashboard; strictly constrained by resident consent. |

---

## 3. Representative Evaluation Tasks

The protocol simulates execution across five standard caregiver operational workflows:

1. **Task T1 — Alert Comprehension & Actionability:**
   - *Objective:* Caregiver logs in, reviews an unread alert, understands the non-medical operational explanation, and identifies the suggested next step.
   - *Success Metric:* Caregiver correctly interprets the reason without medical jargon.
2. **Task T2 — Privacy Tier Verification:**
   - *Objective:* Caregiver accesses a drill-down view and confirms that sensitive data outside their assigned role is redacted or withheld.
   - *Success Metric:* 0 unauthorized data points exposed.
3. **Task T3 — Dynamic Consent Management (Resident Perspective):**
   - *Objective:* Resident modifies category permissions (e.g. revokes neighbor access to medication alerts) and verifies immediate enforcement.
   - *Success Metric:* Subsequent neighbor queries immediately return withheld status.
4. **Task T4 — Fleet Status Assessment (Coordinator View):**
   - *Objective:* Coordinator inspects 3 care recipients on the fleet overview, identifying stale heartbeats and active critical alerts.
   - *Success Metric:* 100% identification of offline or attention-needed residences within 10 seconds.
5. **Task T5 — Cryptographic Audit Trail Verification:**
   - *Objective:* System administrator or compliance officer executes hash-chain verification to validate record integrity.
   - *Success Metric:* Immediate cryptographic pass on clean chain; instant tamper localization on modified log.

---

## 4. Usability Scoring Methodology (Simulated SUS)

The protocol incorporates John Brooke's standard 10-item **System Usability Scale (SUS)**:

1. *I think that I would like to use this system frequently.*
2. *I found the system unnecessarily complex.*
3. *I thought the system was easy to use.*
4. *I think that I would need the support of a technical person to be able to use this system.*
5. *I found the various functions in this system were well integrated.*
6. *I thought there was too much inconsistency in this system.*
7. *I would imagine that most people would learn to use this system very quickly.*
8. *I found the system very cumbersome to use.*
9. *I felt very confident using the system.*
10. *I needed to learn a lot of things before I could get going with this system.*

### Scoring Formula
$$\text{SUS Score} = \left( \sum (Q_{\text{odd}} - 1) + \sum (5 - Q_{\text{even}}) \right) \times 2.5$$

---

## 5. Future Human Participant Recruitment Plan

When IRB approval and clinical collaboration are established in future work, the study protocol will follow:

* **Inclusion Criteria:** Informal caregivers (family/neighbors) providing regular care for an older adult ($\ge 65$) living alone; professional care coordinators with active caseloads.
* **Exclusion Criteria:** Individuals with severe cognitive impairment unable to provide informed consent; individuals lacking internet-capable devices.
* **Data Privacy & Ethics:** Fully anonymized user identifiers, encrypted telemetry streams, zero collection of protected medical records.
* **Informed Consent Procedure:** Dual-stage consent from both older adults (telemetry sensing consent) and caregivers (portal study consent).
