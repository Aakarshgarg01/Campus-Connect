import { createFileRoute } from "@tanstack/react-router";
import { FacultyStudentsPage } from "@/pages/faculty/FacultyPages";
import { AppShell } from "@/components/campus/shell";
import { RoleGuard } from "@/components/campus/guards";
function Page(){return <RoleGuard role="faculty"><AppShell role="faculty"><FacultyStudentsPage/></AppShell></RoleGuard>}
export const Route=createFileRoute("/faculty/students/")({head:()=>({meta:[{title:"Students — CampusConnect"},{name:"description",content:"Review and monitor the current student cohort in CampusConnect."},{property:"og:title",content:"Students — CampusConnect"},{property:"og:description",content:"Review and monitor the current student cohort in CampusConnect."},{property:"og:type",content:"website"},{name:"twitter:card",content:"summary_large_image"}]}),component:Page});
