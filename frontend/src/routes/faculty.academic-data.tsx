import { createFileRoute } from "@tanstack/react-router";
import { AcademicDataPage } from "@/pages/faculty/FacultyPages";
import { AppShell } from "@/components/campus/shell";
import { RoleGuard } from "@/components/campus/guards";
function Page(){return <RoleGuard role="faculty"><AppShell role="faculty"><AcademicDataPage/></AppShell></RoleGuard>}
export const Route=createFileRoute("/faculty/academic-data")({head:()=>({meta:[{title:"AcademicData — CampusConnect"},{name:"description",content:"CampusConnect academic performance and early-warning workspace."},{property:"og:title",content:"AcademicData — CampusConnect"},{property:"og:description",content:"CampusConnect academic performance and early-warning workspace."},{property:"og:type",content:"website"},{name:"twitter:card",content:"summary_large_image"}]}),component:Page});
