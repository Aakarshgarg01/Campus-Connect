import { createFileRoute } from "@tanstack/react-router";
import { UploadPage } from "@/pages/faculty/FacultyPages";
import { AppShell } from "@/components/campus/shell";
import { RoleGuard } from "@/components/campus/guards";
function Page(){return <RoleGuard role="faculty"><AppShell role="faculty"><UploadPage/></AppShell></RoleGuard>}
export const Route=createFileRoute("/faculty/upload")({head:()=>({meta:[{title:"Upload — CampusConnect"},{name:"description",content:"CampusConnect academic performance and early-warning workspace."},{property:"og:title",content:"Upload — CampusConnect"},{property:"og:description",content:"CampusConnect academic performance and early-warning workspace."},{property:"og:type",content:"website"},{name:"twitter:card",content:"summary_large_image"}]}),component:Page});
