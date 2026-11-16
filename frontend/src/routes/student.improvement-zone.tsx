import { createFileRoute } from "@tanstack/react-router";
import { ImprovementPage } from "@/pages/student/StudentPages";
import { AppShell } from "@/components/campus/shell";
import { RoleGuard } from "@/components/campus/guards";
function Page(){return <RoleGuard role="student"><AppShell role="student"><ImprovementPage/></AppShell></RoleGuard>}
export const Route=createFileRoute("/student/improvement-zone")({head:()=>({meta:[{title:"Improvement — CampusConnect"},{name:"description",content:"CampusConnect academic performance and early-warning workspace."},{property:"og:title",content:"Improvement — CampusConnect"},{property:"og:description",content:"CampusConnect academic performance and early-warning workspace."},{property:"og:type",content:"website"},{name:"twitter:card",content:"summary_large_image"}]}),component:Page});
