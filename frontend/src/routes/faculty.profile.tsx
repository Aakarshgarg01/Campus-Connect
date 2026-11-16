import { createFileRoute } from "@tanstack/react-router";
import { FacultyProfilePage } from "@/pages/faculty/FacultyPages";
import { AppShell } from "@/components/campus/shell";
import { RoleGuard } from "@/components/campus/guards";
function Page(){return <RoleGuard role="faculty"><AppShell role="faculty"><FacultyProfilePage/></AppShell></RoleGuard>}
export const Route=createFileRoute("/faculty/profile")({head:()=>({meta:[{title:"Profile — CampusConnect"},{name:"description",content:"CampusConnect academic performance and early-warning workspace."},{property:"og:title",content:"Profile — CampusConnect"},{property:"og:description",content:"CampusConnect academic performance and early-warning workspace."},{property:"og:type",content:"website"},{name:"twitter:card",content:"summary_large_image"}]}),component:Page});
