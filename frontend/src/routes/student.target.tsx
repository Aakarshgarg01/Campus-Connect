import { createFileRoute } from "@tanstack/react-router";
import { TargetPage } from "@/pages/student/StudentPages";
import { AppShell } from "@/components/campus/shell";
import { RoleGuard } from "@/components/campus/guards";
function Page(){return <RoleGuard role="student"><AppShell role="student"><TargetPage/></AppShell></RoleGuard>}
export const Route=createFileRoute("/student/target")({head:()=>({meta:[{title:"Target — CampusConnect"},{name:"description",content:"CampusConnect academic performance and early-warning workspace."},{property:"og:title",content:"Target — CampusConnect"},{property:"og:description",content:"CampusConnect academic performance and early-warning workspace."},{property:"og:type",content:"website"},{name:"twitter:card",content:"summary_large_image"}]}),component:Page});
