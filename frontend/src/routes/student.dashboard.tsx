import { createFileRoute } from "@tanstack/react-router";
import { StudentDashboard } from "@/pages/student/StudentPages";
import { AppShell } from "@/components/campus/shell";
import { RoleGuard } from "@/components/campus/guards";
function Page(){return <RoleGuard role="student"><AppShell role="student"><StudentDashboard/></AppShell></RoleGuard>}
export const Route=createFileRoute("/student/dashboard")({head:()=>({meta:[{title:"Dashboard — CampusConnect"},{name:"description",content:"CampusConnect academic performance and early-warning workspace."},{property:"og:title",content:"Dashboard — CampusConnect"},{property:"og:description",content:"CampusConnect academic performance and early-warning workspace."},{property:"og:type",content:"website"},{name:"twitter:card",content:"summary_large_image"}]}),component:Page});
