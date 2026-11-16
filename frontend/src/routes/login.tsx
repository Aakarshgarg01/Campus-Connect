import { createFileRoute } from "@tanstack/react-router";
import { LoginPage } from "@/pages/auth/LoginPage";

export const Route=createFileRoute("/login")({head:()=>({meta:[{title:"Login — CampusConnect"},{name:"description",content:"CampusConnect academic performance and early-warning workspace."},{property:"og:title",content:"Login — CampusConnect"},{property:"og:description",content:"CampusConnect academic performance and early-warning workspace."},{property:"og:type",content:"website"},{name:"twitter:card",content:"summary_large_image"}]}),component:LoginPage});
