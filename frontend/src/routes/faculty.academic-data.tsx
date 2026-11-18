import { createFileRoute } from "@tanstack/react-router";
import { AcademicDataPage } from "@/pages/faculty/FacultyPages";
import { AppShell } from "@/components/campus/shell";
import { RoleGuard } from "@/components/campus/guards";
function Page() {
  const { student } = Route.useSearch();
  return (
    <RoleGuard role="faculty">
      <AppShell role="faculty">
        <AcademicDataPage {...(student ? { initialStudentId: student } : {})} />
      </AppShell>
    </RoleGuard>
  );
}
export const Route = createFileRoute("/faculty/academic-data")({
  validateSearch: (search: Record<string, unknown>): { student?: number } => {
    const n = Number(search["student"]);
    return Number.isInteger(n) && n > 0 ? { student: n } : {};
  },
  head: () => ({
    meta: [
      { title: "AcademicData — CampusConnect" },
      {
        name: "description",
        content: "CampusConnect academic performance and early-warning workspace.",
      },
      { property: "og:title", content: "AcademicData — CampusConnect" },
      {
        property: "og:description",
        content: "CampusConnect academic performance and early-warning workspace.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Page,
});
