# CampusConnect frontend

## Scope
Build a complete, responsive academic early-warning application with mock authentication, student and faculty workspaces, realistic academic data, and a replaceable API service layer.

## Implementation
1. Establish a restrained, professional university design system with strong typography, deliberate spacing, realistic information density, semantic status colors, reusable controls, professional tables, analytical charts, feedback states, and a responsive application shell. The UI must not look AI-generated or like a generic SaaS dashboard. Avoid excessive cards, gradients, glassmorphism, oversized icons, excessive rounded corners, decorative elements, and unnecessary animations. Premium quality should come from typography, spacing, hierarchy, alignment, and information architecture.
2. Add mock authentication with role-aware guards and demo student/faculty sign-in. The selected demo role only simulates a future backend response.
3. Create centralized, internally consistent mock records and API-shaped asynchronous services for auth, student data, faculty data, predictions, and uploads.
4. Build all student screens: overview, performance, prediction history, rule-based improvement zones, target management, simulator, and profile.
5. Build all faculty screens: overview, searchable student table, student detail and monitoring, dynamic academic entry, staged CSV/XLSX upload flow, benchmark, monitoring, and profile.
6. Encode the semester workflow explicitly: Internal 1 upload unlocks stage 1 prediction; Internal 2 upload adds stage 2 while preserving history; targets, benchmarks, and monitoring follow from those predictions.
7. Add loading, empty, error, pending-Internal-2, validation, confirmation, and success states where relevant.
8. Verify navigation, role protection, interactive workflows, table behavior, charts, and desktop/mobile presentation.

## Technical details
- Retain the project’s TanStack Router architecture while fulfilling the requested React/Vite experience; every referenced URL receives its own route.
- Use React Query-compatible mock services so future HTTP calls can replace mock handlers without page rewrites.
- Keep raw marks, calculated display percentages, predictions, targets, benchmarks, and improvement classifications separate.
- Stage 1 prediction consumes overall attendance percentage, Internal 1 performance percentage, and assignment performance percentage.
- Stage 2 prediction consumes overall attendance percentage, Internal 1 performance percentage, Internal 2 performance percentage, and assignment performance percentage.
- Final Exam Score is never a prediction input.
- Daily Study Hours is not used in the CampusConnect prediction workflow.
- Do not assume marks are out of 40 or any fixed maximum; store obtained marks and maximum marks separately and calculate percentages from them.
- Subjects are dynamic; do not hardcode a fixed number of subjects.
- Keep improvement-zone thresholds in a standalone utility using a configurable 10% relative band.
- The simulator calls a mock prediction endpoint abstraction; no regression or fabricated ML formula will be implemented in the browser.
- Internal 2 uploads merge into student-subject records and never overwrite Internal 1.
- Authentication guards are a user-experience layer only; future backend authorization remains authoritative.
- Every prediction is labelled as an estimate, never a guaranteed result.
- Presentation, service/API abstraction, business rules, and mock data remain separate.
- No GenAI, chatbot, study-hours analytics, CGPA prediction, leaderboards, gamification, additional models, fake explanations, or unspecified features.
- CSV/XLSX processing is a frontend preview and validation workflow only; no persistence is implied.
